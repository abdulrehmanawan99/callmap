# CallMap

A private audio workspace for turning a conversation into a reviewed plan. A cobalt player and waveform sit above a synchronized transcript and editable commitment timeline.

**First fixture milestone**, based on the CallMap section of the portfolio PRD. This is a working local product slice, **not live speech recognition or extraction**. The bundled 33.8-second WAV is genuine synthetic speech generated with macOS `say`. Its authored transcript and four predefined suggestions are returned **only when the uploaded bytes match its SHA-256 fingerprint**. Unrelated valid audio becomes a failed job with a clear provider-unavailable message and no invented transcript.

![CallMap desktop workspace](docs/screenshots/desktop.png)

## Run locally

Prerequisites: Docker Desktop/Compose, Python 3.12+, Node **22.12+ or 24+**, npm. No provider key, model download, global package installation, or paid service is required.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
cd web
npm ci
cd ..
cp .env.example .env
./scripts/dev.sh
```

Open **http://127.0.0.1:5175** and paste the local token printed in the terminal. It is generated into `.data/local-token` with mode 0600, excluded from Git, and retained only in the browser tab's session storage. Terminal scrollback contains that installation token; keep it private. The API uses port **8012**, PostgreSQL **55434**, Redis **6382**; all bind loopback. The start script refuses occupied application ports and never stops unknown processes. Compose owns only `callmap-*` containers and `callmap_callmap_*` volumes. It does not use EvidenceLens ports or data.

The verified development machine has Node 24 at `/Users/apple/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin`; if the shell selects its older system Node, prepend that directory to `PATH` before installation/start. A Python 3.12 interpreter was used to create this repository's independent `.venv`.

1. **Load sample**, or upload `fixtures/launch-checkin.wav` (exact bytes).
2. Watch the persisted job move from queued → fixture transcript → fixture extraction → ready.
3. Play, seek the waveform slider, click transcript segments or **Hear source**. Space toggles playback; J/L seek five seconds outside form controls. Playback speed and follow-audio are adjustable.
4. Correct text, owner, date, and action/question type. **Save draft** persists edits without review. **Accept action** requires an owner; **Review question** keeps an unresolved question explicit. A reviewed question is not a resolved question. Undo review is supported.
5. **Export reviewed** downloads JSON containing only persisted reviewed items and source/provenance. Unsaved edits are excluded. Reloading preserves recordings and reviews; select a recent recording to reopen it.
6. Cancel pending work, or delete a recording and its private WAV/reviews. Deletion requires a UI confirmation. There is no trash or automatic retention.

Uploads: uncompressed PCM WAV only, 0.3–120 seconds, 24 MiB maximum, mono/stereo, 8–48 kHz, 8–32 bits. MP3/M4A are intentionally unsupported in this milestone. The UI shows the latest 100 recordings; the API exposes bounded `limit`/`offset` pagination. Files use generated UUID names in `.data/audio`, never uploaded path names.

Ctrl+C stops this script's API, worker, and Vite; supporting containers/data remain. `docker compose stop` stops only CallMap supporting services. Restart `scripts/dev.sh` after backend changes; Vite reloads frontend edits. Do not use `docker compose down -v` unless deliberately deleting this project's persisted database.

## Checks

```sh
.venv/bin/python -m pytest api/tests/test_core.py -q
# Create once; an existing disposable database can be reused.
docker compose exec -T postgres createdb -U callmap callmap_test
CALLMAP_TEST_DATABASE_URL=postgresql://callmap:callmap_local_only@127.0.0.1:55434/callmap_test \
  .venv/bin/python -m pytest api/tests -q
cd web && npm run build
```

Integration checks **truncate only the explicitly selected `*_test` database**, create temporary private audio files, and start/kill a real worker. They refuse database names that do not end in `_test`. Do not run a second worker against that test database during checks. See [verification](docs/verification.md) for actual results and untested scope.

## Design and limits

React/Vite/TypeScript; four small FastAPI modules; direct psycopg/PostgreSQL persistence; Redis wakeups; private local WAVs. [Architecture and provider boundary](docs/architecture.md), [threat model](docs/threat-model.md), [fixture manifest](fixtures/launch-checkin.json).

A provider must be selected and authorized before arbitrary audio can produce transcripts. Live transcription, extraction, diarization, two-provider portability, WER, extraction precision/recall, and live timestamp quality are **pending**. There are no cloud calls, accounts, customer contact, hosted identity, multitenancy, or background retries of provider failures. This local installation assumes one trusted OS user; it is not a shared/public deployment.
