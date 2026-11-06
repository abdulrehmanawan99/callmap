# Verification — 6 November 2026

The local fixture workflow and optional Gemini adapter are implemented. **Live compatibility and quality acceptance remain pending.** No key was read and no live inference, paid call, or model download was made for this work.

## Current local checks

- `.venv/bin/python -m pytest api/tests -q`: **40 passed, 10 skipped**, one upstream Starlette warning about its deprecated httpx TestClient transport. The ten skipped cases require the explicit disposable PostgreSQL database.
- Offline checks cover PCM bounds/fingerprint gating; native Interactions HTTP request shape; timestamp ordering/IDs; exact quotations, explicit owner/date grounding; quota/auth/redirect/timeout/oversized/malformed responses; cancellation of a stalled response-header wait by the total network deadline; no automatic retries; fixture/key/model preflight; evaluation WER and no-call/error report accounting. HTTP responses are mocked: these checks do not establish actual model support.
- `npm run build` with Node 24: strict TypeScript and Vite production build passed; JS **209.37 kB (66.60 kB gzip)**, CSS 19.57 kB (4.82 kB gzip).
- Full `npm audit`: **0 vulnerabilities**. `python -m pip check`: no broken requirements. `pip-audit --disable-pip --no-deps -r requirements.lock` from a disposable audit environment: **no known vulnerabilities found**. Dependency audits are time-specific advisory checks.
- `python -m compileall -q api scripts` and `git diff --check` passed.
- Default `python -m scripts.evaluate_live --output docs/live-evaluation-blocked.json`: **blocked, zero HTTP attempts, no metrics/thresholds**. This is the committed current evaluation result, not a model score.

## PostgreSQL integration boundary

At the initial resume, local Docker was unavailable because its backend could not resize Docker.raw. No Docker disk or user volume was changed. Consequently **the updated integration suite was not executed locally in that offline pass**; the later remote result and restored local startup are recorded below.

The GitHub Actions workflow runs `pytest api/tests` against dedicated PostgreSQL 17.5/Redis 7.4.3 services and `callmap_test`. [Run 42222213675](https://github.com/abdulrehmanawan99/callmap/actions/runs/42222213675) passed **all 50 tests**, including all ten integration cases and the offline provider/evaluation checks. No live key/call was used. The current PR checks remain the source for later commit results.

Integration assertions cover upload/auth/origin/object boundaries; real fixture worker/restart; review version conflicts and reviewed-only export; cancellation and deletion; mocked live pipeline provenance; cancellation during transcription; sanitized extraction failure; deletion during extraction; interrupted live jobs fail without replay; removal of a private upload when its database insertion fails; and a four-case real-DB regression for stale transcription/extraction success/failure against a newer attempt with identical status. These passed on the isolated CI database. Tests truncate only a configured database ending in `_test`, use temporary audio, and stop their worker subprocesses.

After Docker connectivity was restored, the existing source launcher was started against a fresh local CallMap database; UI 5175 and API 8012 returned HTTP 200. Previous Docker volumes were absent from the repaired engine; old filesystem artifacts were not deleted or treated as restored database records.

## Prior fixture evidence

On 5 November the previous fixture milestone recorded **9 passed** using real local PostgreSQL/Redis and a real worker, plus a successful frontend build and dependency audits. The 33.8-second mono 22.05 kHz 16-bit WAV was generated using macOS `say`/`afconvert`; its authored manifest is fingerprint gated.

The revised interface received a fresh real-persistence Chromium workflow in the CI run above: sample playback/seek, disabled unconfigured live-provider opt-in, review save/reload, reviewed-only JSON download with fixture provenance, and deletion passed without JavaScript errors or document overflow. Desktop and 390 px mobile axe WCAG 2 A/AA + 2.1 AA scans reported **zero violations**. Actual screenshots in `docs/screenshots/` were refreshed from that CI artifact and visually inspected. The browser script now also checks opening the exact source quotation. The enabled live-provider UI/model path still needs credentials and actual acceptance. Automated axe is not a full accessibility audit.

## Remaining acceptance work

An authorized billing-disabled Gemini project is required to establish actual API/model compatibility and a measured development baseline. Current labels use the authored sample and are not held out; approximate lexical matching requires manual review. Set acceptance thresholds after inspecting real results, then evaluate independent consented/synthetic audio. A second capable provider, live WER/precision/recall/timestamp quality, diarization, production load, hosted deployment, secure erasure, and fresh-checkout end-to-end acceptance are unverified. No claim of full PRD or two-provider acceptance is made.
