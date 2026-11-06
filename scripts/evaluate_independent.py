"""Explicit one-pass API/worker evaluation. Default is an offline plan, never inference."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time

import httpx

from api.core import ROOT
from api.providers import MODEL

CORPUS = ROOT / 'fixtures/independent'


def save(path, results):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as output:
        output.write(json.dumps(results, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--allow-external-synthetic-audio', action='store_true', help='Authorize at most six generation requests across the three fixed synthetic cases, through the local API/worker.')
    parser.add_argument('--results', type=Path, default=ROOT / '.local/independent-api-results.json')
    args = parser.parse_args()
    corpus = json.loads((CORPUS / 'corpus.json').read_text())
    results = json.loads(args.results.read_text()) if args.results.exists() else {}
    pending = []
    for filename in corpus['cases']:
        reference = json.loads((CORPUS / filename).read_text())
        data = (CORPUS / reference['audio']).read_bytes()
        if hashlib.sha256(data).hexdigest() != reference['sha256']:
            raise SystemExit('Corpus fingerprint mismatch; no upload made.')
        if reference['id'] not in results:
            pending.append((reference, data))
    if not args.allow_external_synthetic_audio:
        print(json.dumps(dict(mode='offline_plan_no_requests', pending=[reference['id'] for reference, _ in pending], previously_attempted=list(results), model=MODEL, maximum_remaining_generation_requests=2 * len(pending)), indent=2))
        return
    # Only loopback API; the private key remains in the existing server/worker environment.
    token = (ROOT / '.data/local-token').read_text().strip()
    with httpx.Client(base_url='http://127.0.0.1:8012', headers={'Authorization': 'Bearer ' + token}, timeout=10, trust_env=False) as api:
        health = api.get('/api/health').json()
        if not health.get('live_inference') or health.get('live_model') != MODEL:
            raise SystemExit('Exact authorized model is not configured; no upload made.')
        for reference, data in pending:
            response = api.post('/api/recordings/upload', params={'provider': 'gemini', 'title': 'Independent synthetic evaluation: ' + reference['id']}, headers={'Content-Type': 'audio/wav'}, content=data)
            if response.status_code != 201:
                raise SystemExit('Local API refused the upload; stopped without retry.')
            submitted = response.json()
            rid = submitted['id']
            # Persist before waiting: a harness crash must not resubmit that case.
            results[reference['id']] = submitted
            save(args.results, results)
            deadline = time.monotonic() + 140
            result = None
            while time.monotonic() < deadline:
                response = api.get('/api/recordings/' + rid)
                response.raise_for_status()
                result = response.json()
                if result['status'] in {'ready', 'failed', 'cancelled'}:
                    break
                time.sleep(.25)
            else:
                api.post('/api/recordings/' + rid + '/cancel').raise_for_status()
                result = api.get('/api/recordings/' + rid).json()
            results[reference['id']] = result
            save(args.results, results)
            print(json.dumps(dict(case=reference['id'], recording_id=rid, status=result['status'])), flush=True)
            if result['status'] != 'ready':
                print('Stopped after first failure/cancellation; remaining cases untouched. No retry.')
                return


if __name__ == '__main__':
    main()
