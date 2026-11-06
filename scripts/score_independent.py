"""Offline scoring of persisted API outputs against frozen independent labels. No HTTP."""
import argparse
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from api.core import ROOT
from api.providers import Transcript
from scripts.evaluate_live import score

CORPUS = ROOT / 'fixtures/independent'


def assess(reference, result, gates):
    if result['status'] != 'ready':
        return dict(passed=False, failures=['pipeline_not_ready'], status=result['status'])
    transcript = Transcript.model_validate({'segments': result['segments']}).validate_duration(reference['duration'])
    extraction = SimpleNamespace(model_dump=lambda **_: {'commitments': result['commitments']})
    metrics = score(reference, reference, transcript, extraction)
    limits = gates['per_recording']
    failures = []
    checks = {
        'word_error_rate': metrics['wer'] <= limits['normalized_token_wer_max'],
        'mean_timestamp_boundary': metrics['timestamp_mean_boundary_error_seconds'] <= limits['mean_boundary_error_seconds_max'],
        'worst_timestamp_boundary': all(max(e['start_error_seconds'], e['end_error_seconds']) <= limits['single_boundary_error_seconds_max'] for e in metrics['timestamp_errors']),
        'extraction_precision': metrics['extraction']['precision'] >= limits['extraction_precision_min'],
        'extraction_recall': metrics['extraction']['recall'] >= limits['extraction_recall_min'],
        'owner_agreement': metrics['extraction']['owner_matches'] == len(reference['expected']),
        'date_agreement': metrics['extraction']['date_matches'] == len(reference['expected']),
        'no_false_positive_in_empty_case': bool(reference['expected']) or not result['commitments'],
        'exact_source_quotes': all(item['source_quote'] in result['segments'][item['segment_id']]['text'] for item in result['commitments']),
    }
    failures = [name for name, passed in checks.items() if not passed]
    return dict(passed=not failures, failures=failures, checks=checks, metrics=metrics)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, required=True, help='JSON mapping case IDs to persisted API detail objects')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    corpus = json.loads((CORPUS / 'corpus.json').read_text())
    gates = json.loads((CORPUS / corpus['gates']).read_text())
    results = json.loads(args.results.read_text())
    cases = {}
    for filename in corpus['cases']:
        reference = json.loads((CORPUS / filename).read_text())
        if hashlib.sha256((CORPUS / reference['audio']).read_bytes()).hexdigest() != reference['sha256']:
            raise ValueError('Independent corpus source fingerprint mismatch')
        cases[reference['id']] = dict(source_sha256=reference['sha256'], **assess(reference, results[reference['id']], gates))
    report = dict(corpus=corpus['version'], gates_version=gates['version'], scoring_only_no_requests=True, all_gates_passed=all(case['passed'] for case in cases.values()), cases=cases)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
