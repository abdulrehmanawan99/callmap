"""Evaluation authorization and reporting must not create inference evidence."""

import json
import sys

import httpx
import pytest

from api.providers import Gemini
from scripts import evaluate_live


@pytest.mark.parametrize("allow,configured,attempts", [(False, True, 0), (True, False, 0), (True, True, 1)])
def test_blocked_evaluation_counts_only_http_attempts(monkeypatch, tmp_path, allow, configured, attempts):
    monkeypatch.setenv("CALLMAP_PROVIDER", "gemini")
    monkeypatch.setenv("CALLMAP_GEMINI_MODEL", "gemini-3.5-flash-lite")
    if configured:
        monkeypatch.setenv("GEMINI_API_KEY", "test-key-never-real")
    else:
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(429, json={"private": "test-key-never-real"})

    monkeypatch.setattr(evaluate_live, "Gemini", lambda: Gemini(httpx.AsyncClient(transport=httpx.MockTransport(handler))))
    output = tmp_path / "report.json"
    monkeypatch.setattr(sys, "argv", ["evaluate_live", "--output", str(output)] + (["--allow-external-synthetic-audio"] if allow else []))
    evaluate_live.main()
    report = json.loads(output.read_text())
    assert report["status"] == "blocked"
    assert report["live_http_attempts"] == len(calls) == attempts
    assert "metrics" not in report and report["thresholds"] is None
    assert "test-key" not in output.read_text()


def test_empty_ground_truth_scores_no_predictions_and_flags_hallucination():
    from types import SimpleNamespace
    from api.providers import Transcript
    from scripts.evaluate_live import score
    from api.tests.test_providers import TRANSCRIPT, ITEM

    reference = dict(TRANSCRIPT, expected=[])
    transcript = Transcript.model_validate(TRANSCRIPT)
    clean = score(reference, reference, transcript, SimpleNamespace(model_dump=lambda **_: {'commitments': []}))
    assert clean['extraction']['precision'] == clean['extraction']['recall'] == 1
    false_positive = score(reference, reference, transcript, SimpleNamespace(model_dump=lambda **_: {'commitments': [ITEM]}))
    assert false_positive['extraction']['precision'] == 0
    assert false_positive['extraction']['predicted'] == 1
