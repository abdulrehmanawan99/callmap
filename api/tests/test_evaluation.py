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


def test_independent_gates_reject_invented_owner_and_calendar_date():
    from scripts.score_independent import assess, CORPUS
    reference = json.loads((CORPUS / 'relative-open.json').read_text())
    gates = json.loads((CORPUS / 'gates.json').read_text())
    items = [dict(text=' '.join(item['keywords']), kind=item['kind'], segment_id=item['reference_segment'], source_quote=reference['segments'][item['reference_segment']]['text'], owner=item['owner'], due_date=item['due_date']) for item in reference['expected']]
    result = dict(status='ready', segments=reference['segments'], commitments=items)
    assert assess(reference, result, gates)['passed']
    items[0] |= dict(owner='Invented person', due_date='2026-12-08')
    assessment = assess(reference, result, gates)
    assert not assessment['passed']
    assert {'owner_agreement', 'date_agreement'} <= set(assessment['failures'])


def test_independent_corpus_fingerprints_and_nonempty_pcm():
    import hashlib
    from api.core import validate_wav
    from scripts.score_independent import CORPUS
    corpus = json.loads((CORPUS / 'corpus.json').read_text())
    for filename in corpus['cases']:
        reference = json.loads((CORPUS / filename).read_text())
        audio = (CORPUS / reference['audio']).read_bytes()
        duration, fingerprint = validate_wav(audio)
        assert fingerprint == reference['sha256'] == hashlib.sha256(audio).hexdigest()
        assert abs(duration - reference['duration']) < .002


@pytest.mark.parametrize('status', ['failed', 'not_attempted'])
def test_independent_unmeasured_cases_never_receive_quality_scores(status):
    from scripts.score_independent import assess, CORPUS
    reference = json.loads((CORPUS / 'background-only.json').read_text())
    gates = json.loads((CORPUS / 'gates.json').read_text())
    result = assess(reference, {'status': status}, gates)
    assert not result['passed'] and 'metrics' not in result
    assert result['status'] == status


def test_independent_runner_default_is_offline_and_skips_attempted_cases(monkeypatch, tmp_path, capsys):
    from scripts import evaluate_independent
    results = tmp_path / 'results.json'
    results.write_text(json.dumps({'background-only': {'status': 'failed'}}))
    monkeypatch.setattr(sys, 'argv', ['evaluate_independent', '--results', str(results)])

    def forbidden(*args, **kwargs):
        raise AssertionError('Offline evaluation plan must never open HTTP')

    monkeypatch.setattr(evaluate_independent.httpx, 'Client', forbidden)
    evaluate_independent.main()
    plan = json.loads(capsys.readouterr().out)
    assert plan['pending'] == ['named-calendar', 'relative-open']
    assert plan['previously_attempted'] == ['background-only']
    assert plan['maximum_remaining_generation_requests'] == 4


@pytest.mark.parametrize('patch', [
    {'source_quote': ''}, {'source_quote': '   '}, {'source_quote': None},
    {'source_quote': 42}, {'segment_id': -1}, {'segment_id': 99},
    {'segment_id': True}, {'segment_id': '0'}, {'segment_id': 0.0},
])
def test_independent_source_check_rejects_malformed_quote_or_id(patch):
    from scripts.score_independent import assess, CORPUS
    reference = json.loads((CORPUS / 'named-calendar.json').read_text())
    gates = json.loads((CORPUS / 'gates.json').read_text())
    expected = reference['expected'][0]
    item = dict(text=' '.join(expected['keywords']), kind=expected['kind'],
                owner=expected['owner'], due_date=expected['due_date'],
                segment_id=0, source_quote=reference['segments'][0]['text'])
    result = dict(status='ready', segments=reference['segments'], commitments=[item | patch])
    assessment = assess(reference, result, gates)
    assert not assessment['passed']
    assert assessment['checks']['exact_source_quotes'] is False


@pytest.mark.parametrize('mode,exit_code', [('pass', 0), ('fail', 1), ('partial-fail', 1), ('empty', 2)])
def test_independent_score_cli_exit_statuses(tmp_path, mode, exit_code):
    import subprocess
    from api.core import ROOT
    from scripts.score_independent import CORPUS
    results = {}
    if mode != 'empty':
        for filename in json.loads((CORPUS / 'corpus.json').read_text())['cases']:
            reference = json.loads((CORPUS / filename).read_text())
            items = [dict(text=' '.join(item['keywords']), kind=item['kind'],
                          owner=item['owner'], due_date=item['due_date'],
                          segment_id=item['reference_segment'],
                          source_quote=reference['segments'][item['reference_segment']]['text'])
                     for item in reference['expected']]
            results[reference['id']] = dict(status='ready', segments=reference['segments'], commitments=items)
        if mode in {'fail', 'partial-fail'}:
            results['named-calendar']['commitments'][0]['owner'] = 'Invented owner'
        if mode == 'partial-fail':
            results = {'named-calendar': results['named-calendar']}
    source, output = tmp_path / 'results.json', tmp_path / 'report.json'
    source.write_text(json.dumps(results))
    process = subprocess.run(
        [sys.executable, '-m', 'scripts.score_independent', '--results', str(source), '--output', str(output)],
        cwd=ROOT, capture_output=True, text=True, timeout=10,
    )
    assert process.returncode == exit_code, process.stderr
    report = json.loads(output.read_text())
    assert report['scoring_only_no_requests'] is True
    if mode == 'empty':
        assert report['quality_acceptance'] == 'not_established'
        assert report['measured_cases'] == 0
        assert all(case['status'] == 'not_attempted' and 'metrics' not in case for case in report['cases'].values())
    if mode == 'partial-fail':
        assert report['quality_acceptance'] == 'failed_frozen_gates'
        assert report['measured_cases'] == 1
