"""Opt-in synthetic development baseline. Default writes a blocked/no-call report."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time

from api.core import ROOT, validate_wav
from api.providers import Gemini, ProviderError, PROMPT_VERSION


def words(text):
    return re.findall(r"[a-z0-9]+", text.lower())


def wer(reference, hypothesis):
    previous = list(range(len(hypothesis) + 1))
    for i, token in enumerate(reference, 1):
        current = [i]
        for j, other in enumerate(hypothesis, 1):
            current.append(
                min(
                    current[-1] + 1, previous[j] + 1, previous[j - 1] + (token != other)
                )
            )
        previous = current
    return previous[-1] / max(1, len(reference))


def score(reference, labels, transcript, extraction):
    reference_text = " ".join(s["text"] for s in reference["segments"])
    segments = transcript.model_dump()["segments"]
    predicted = extraction.model_dump(mode="json")["commitments"]
    hypothesis = " ".join(s["text"] for s in segments)
    # Transparent lexical matching for this small development fixture, not semantic evaluation.
    remaining = list(predicted)
    matches = []
    for expected in labels["expected"]:
        found = next(
            (
                item
                for item in remaining
                if item["kind"] == expected["kind"]
                and set(expected["keywords"])
                <= set(words(item["text"] + " " + item["source_quote"]))
            ),
            None,
        )
        if found:
            remaining.remove(found)
            matches.append((expected, found))
    errors = []
    for ref in reference["segments"]:
        best = max(
            segments,
            key=lambda segment: (
                len(set(words(ref["text"])) & set(words(segment["text"])))
                / max(1, len(set(words(ref["text"])) | set(words(segment["text"]))))
            ),
        )
        errors.append(
            {
                "reference_segment": ref["id"],
                "start_error_seconds": round(abs(ref["start"] - best["start"]), 3),
                "end_error_seconds": round(abs(ref["end"] - best["end"]), 3),
            }
        )
    tp = len(matches)
    return {
        "wer": round(wer(words(reference_text), words(hypothesis)), 4),
        "extraction": {
            "true_positives": tp,
            "predicted": len(predicted),
            "expected": len(labels["expected"]),
            "precision": tp / len(predicted) if predicted else 0,
            "recall": tp / len(labels["expected"]),
            "date_matches": sum(e["due_date"] == i["due_date"] for e, i in matches),
            "owner_matches": sum(e["owner"] == i["owner"] for e, i in matches),
        },
        "timestamp_errors": errors,
        "timestamp_mean_boundary_error_seconds": round(
            sum(e["start_error_seconds"] + e["end_error_seconds"] for e in errors)
            / (2 * len(errors)),
            3,
        ),
        "method": "Normalized token Levenshtein WER; exact keyword/kind one-to-one extraction matching; best lexical-overlap segment boundary alignment. Review split/merged segments and paraphrases manually.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--allow-external-synthetic-audio",
        action="store_true",
        help="Explicitly authorize exactly two Gemini calls using bundled synthetic audio and its model transcript.",
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / ".local/live-evaluation.json"
    )
    args = parser.parse_args()
    labels = json.loads((ROOT / "fixtures/live-evaluation.json").read_text())
    reference = json.loads(
        (ROOT / "fixtures" / labels["reference_manifest"]).read_text()
    )
    data = (ROOT / "fixtures" / labels["audio"]).read_bytes()
    duration, fingerprint = validate_wav(data)
    report = {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "status": "blocked",
        "live_http_attempts": 0,
        "dataset": labels["version"],
        "split": labels["split"],
        "source_sha256": fingerprint,
        "prompt_version": PROMPT_VERSION,
        "thresholds": None,
        "reason": "Live evaluation not authorized. Run with the explicit external-audio flag and a configured billing-disabled Gemini project.",
    }
    if fingerprint != reference["sha256"]:
        report["reason"] = "Fixture fingerprint mismatch; no external call made."
    elif args.allow_external_synthetic_audio:
        provider = None
        try:
            provider = Gemini()
            started = time.monotonic()
            transcript = provider.transcribe(data, duration)
            extraction = provider.extract(transcript)
            report.update(
                status="measured-development-baseline",
                model=provider.model,
                metrics=score(reference, labels, transcript, extraction),
                usage=provider.usage,
                latency_seconds=round(time.monotonic() - started, 3),
                reason="Development measurement only; no acceptance threshold or held-out pass claim.",
            )
        except ProviderError as exc:
            report["reason"] = str(exc)
        finally:
            if provider is not None:
                report["live_http_attempts"] = provider.http_attempts
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
