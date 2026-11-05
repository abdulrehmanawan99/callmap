# Verification — 5 November 2026

This records the **first fixture milestone**, not completion of the full portfolio PRD or live AI acceptance.

Executed locally:

- Generated a genuine **33.8-second, mono, 22.05 kHz, 16-bit PCM WAV** using macOS `say` (Samantha) and `afconvert`. Its committed manifest contains text/timestamps and SHA-256. No downloaded model or provider call.
- `docker compose up -d --wait`: dedicated PostgreSQL 17.5 and Redis 7.4.3 containers started and became healthy. Only ports 55434/6382 and `callmap_*` volumes used.
- `CALLMAP_TEST_DATABASE_URL=…/callmap_test .venv/bin/python -m pytest api/tests -q`: **9 passed** in 16.51 seconds after patched dependency updates. One upstream Starlette warning about the future `httpx2` TestClient transport; no test failure. Tests use a separate disposable database and real worker subprocess, not a mocked queue/database.
- Domain coverage: exact sample fingerprint/timing consistency; arbitrary PCM cannot use fixture; duration/type/truncation/forged huge-frame bounds.
- Integration coverage: auth and hostile Origin/Host; upload failures; sample → real worker → six segments/four items; private playable RIFF bytes; edit/accept/export; stale-review and cross-recording item conflicts; cancellation; unrelated-audio failure with zero claims; forced worker kill/restart with no duplicate commitments; persistence across worker restart; WAV removal and cascading review deletion.
- `npm run build`: TypeScript strict/no-unused checks and Vite production build passed. Main bundle approximately 208 kB (66 kB gzip). No runtime CDN/font dependency.
- `python -m pip check`: no broken requirements.
- `npm audit`: initial Vite dev-server advisories fixed by exact pin 7.3.7; final audit reports zero vulnerabilities. FastAPI/Starlette updated to 0.162.0/1.10.0. `pip-audit` initially flagged pytest 8.3.5; upgraded to 9.0.3; final Python dependency audit reports no known vulnerabilities.
- A GitHub Actions workflow is included for PostgreSQL/Redis integration tests, frontend build, and npm audit. It has not been executed remotely in this milestone.
- Started API/worker/Vite using `scripts/dev.sh`; HTTP health endpoint reports fixture mode, UI returns HTTP 200.

Coordinator browser verification passed the core workflow: genuine playback and timestamp seek; review save/reload persistence; reviewed-only JSON download; deletion; no JavaScript errors; and no document overflow at 390 px. Real screenshots are in `docs/screenshots/desktop.png` and `mobile.png`. Initial axe scans found serious muted-text contrast issues. After the palette correction and patched-stack restart, final desktop and 390 px mobile axe WCAG 2 A/AA + 2.1 AA scans reported **zero violations**, with the core workflow rechecked and screenshots refreshed. Automated axe checks do not replace a complete accessibility audit. This agent's separate CUA attempt was unavailable; browser findings above come from the coordinator's actual browser run.

No WER, real extraction precision/recall, diarization, model compatibility, model latency, production load, public deployment, container-image security scan or complete license inventory, secure erasure, or fresh-checkout end-to-end acceptance is claimed. Current fixture dates are explicit authored dates in November 2026, not relative-date inference. The PRD's two-provider and live-media acceptance remains pending a selected authorized speech/text provider.
