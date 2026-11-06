# Independent synthetic evaluation — 6 November 2026

Quality acceptance is **blocked by provider availability**. This run adds no independent quality scores and does not replace the earlier successful [development baseline](live-validation.md).

## Frozen plan and sources

Commit `31f1d6b` froze [numeric gates](../fixtures/independent/gates.json) **before generating the audio or making inference requests**. The prior development result (WER 0.1444, mean boundary error 0.251 seconds) informed these limits:

- Each recording: normalized token WER ≤0.25; mean timestamp boundary error ≤0.75 seconds and every individual boundary error ≤1.5 seconds.
- Exact keyword/kind extraction precision and recall 1.0, all expected owner/date values correct, and zero false commitments on the negative case.
- Relative dates remain null calendar dates and ambiguous first-person speakers remain unassigned. No invented named owner or absolute date is acceptable.

Commit `e017551` froze the original [corpus manifests and WAVs](../fixtures/independent/corpus.json) before their first live request. These are distinct from the authored development recording: background statements with no commitments; a named actor and fully explicit date; and an unnamed first-person commitment plus an unresolved question with relative dates. Local macOS `say` (Samantha, 170 wpm) and `afconvert` produced mono 22.05 kHz 16-bit PCM. The manifests retain original text, exact SHA-256, expected items and measured synthesized-utterance boundaries. They are prospective independent synthetic cases, not a representative human-speech benchmark.

WER keeps literal normalized tokens, so spoken words versus numeric date formatting can increase it even when the date means the same thing. That is reported, never normalized away after seeing an output. Timestamp alignment uses lexical segment overlap and requires manual inspection of split/merged utterances. For zero expected items and zero predictions, precision/recall are defined as 1; a separate exact-zero-prediction check enforces the negative case.

## Actual bounded attempt

The existing private API and measured worker were checked to belong to CallMap and report exact `gemini-3.5-flash-lite`; there were no pending jobs. One explicit `provider=gemini` upload sent the 6.131-second `background-only` synthetic WAV. Its **first transcription request returned HTTP503 `service_unavailable` / high demand** after 4.694 seconds of app time. The worker marked it failed with no transcript, commitments or usage. Provider token usage is unknown, not zero.

The run stopped immediately. **One new generation request occurred**, below the six-request maximum. Extraction and both remaining recordings were not attempted; no automatic/manual retry, alternative model, key change or billing change followed. The failed synthetic recording remains in the local library. Raw private observations remain under ignored `.local/independent-*`; no secret, raw provider error body or key is committed.

[Machine-readable gate report](independent-evaluation.json) records zero measured cases out of three, the first pipeline failure, two explicitly not-attempted cases and `quality_acceptance=not_established`. A failed availability check is not a failed or passed speech-quality measurement. The predeclared labels and gates remain unchanged.

## Reproduce without spending quota

```sh
# Default is offline: lists pending/previously attempted cases, makes no HTTP request.
.venv/bin/python -m scripts.evaluate_independent
# Offline scoring reads already persisted API results; makes no provider call.
.venv/bin/python -m scripts.score_independent \
  --results .local/independent-api-results.json \
  --output .local/independent-gates.json
```

The runner's explicit `--allow-external-synthetic-audio` flag is reserved for a newly authorized future run after service availability changes. It uses only the fixed loopback API and existing server-side exact-model configuration. It checkpoints the recording ID before polling, skips every previously attempted case (including failures), waits at most 140 seconds per job, and stops on the first failure/cancellation. It never retries or resets the saved results. Retain the same results file; changing/removing it can lose the record of prior external sends. No further live invocation is authorized as part of this completed attempt.

The HTTP503 UI error is now a fixed actionable temporary-unavailability message, with a regression proving one request and no retry. Offline scorer checks cover empty ground truth, invented owners/dates, unmeasured cases and source fingerprints. Broader quality, noisy speech, diarization and a second provider remain unverified; a second provider is outside the exact-model authorization.
