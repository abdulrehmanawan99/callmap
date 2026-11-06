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

Local Docker is unavailable: its backend fails to resize Docker.raw with permission denied. No Docker disk, user volume, or alternate database runtime was changed. Consequently **the updated integration suite was not executed locally in this pass**.

The existing GitHub Actions workflow runs `pytest api/tests` against dedicated PostgreSQL 17.5/Redis 7.4.3 services and `callmap_test`. It discovers all ten integration cases plus the offline provider/evaluation tests; no live key/call is needed. Remote results must be checked separately after push.

Integration assertions cover upload/auth/origin/object boundaries; real fixture worker/restart; review version conflicts and reviewed-only export; cancellation and deletion; mocked live pipeline provenance; cancellation during transcription; sanitized extraction failure; deletion during extraction; interrupted live jobs fail without replay; removal of a private upload when its database insertion fails; and a four-case real-DB regression for stale transcription/extraction success/failure against a newer attempt with identical status. These new database assertions remain unexecuted locally. They truncate only a configured database ending in `_test`, use temporary audio, and stop their worker subprocesses.

## Prior fixture evidence

On 5 November the previous fixture milestone recorded **9 passed** using real local PostgreSQL/Redis and a real worker, plus a successful frontend build and dependency audits. The 33.8-second mono 22.05 kHz 16-bit WAV was generated using macOS `say`/`afconvert`; its authored manifest is fingerprint gated.

The coordinator previously verified playback/seek, review save/reload, reviewed JSON download, deletion, no JavaScript errors, and no overflow at 390 px. After contrast fixes, desktop/mobile axe WCAG 2 A/AA + 2.1 AA scans reported zero violations. Existing screenshots in `docs/screenshots/` reflect that fixture UI. **The later opt-in/source-evidence/retry additions have passed compilation, but have not received a fresh browser/axe pass here.** Automated axe is not a full accessibility audit.

## Remaining acceptance work

An authorized billing-disabled Gemini project is required to establish actual API/model compatibility and a measured development baseline. Current labels use the authored sample and are not held out; approximate lexical matching requires manual review. Set acceptance thresholds after inspecting real results, then evaluate independent consented/synthetic audio. A second capable provider, live WER/precision/recall/timestamp quality, diarization, production load, hosted deployment, secure erasure, and fresh-checkout end-to-end acceptance are unverified. No claim of full PRD or two-provider acceptance is made.
