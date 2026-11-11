# CallMap

Turn a recorded conversation into a reviewed list of action items, without losing track of who said what and where.

## Problem and user

After a check-in call, someone has to scrub through the audio to work out what was promised, by whom and by when. Automatic summaries are fast but hard to trust. CallMap is for the person who owns that follow-up: it keeps the audio, the transcript and each suggested commitment side by side, every suggestion points to its exact source quote, and nothing counts as reviewed until a person accepts it.

It runs locally for one trusted user. The default mode is fully offline; an optional Gemini mode transcribes and extracts suggestions from WAVs you explicitly opt in.

## Features

- Audio player with waveform, playback speed, follow-audio and keyboard controls (Space play/pause, J/L seek 5 s).
- Transcript segments synced to the audio; click a segment or **Hear source** to jump to it.
- Editable commitment timeline: fix text, owner, date and action/question type; **Save draft**, **Accept action** (requires an owner), **Review question**, undo review.
- Durable jobs in PostgreSQL with Redis wake-ups: queued → transcript → extraction → ready, plus cancel, retry and worker-restart recovery.
- **Export reviewed** downloads JSON containing only persisted reviewed items, with source and provider provenance.
- Private local storage: uploads get generated names under `.data/audio`; deleting a recording removes its WAV and reviews.
- Bundled offline fixture (a 33.8 s synthetic WAV) so the full workflow runs with no API key.
- Optional Gemini 3.5 Flash-Lite path with per-upload consent, strict output validation and no automatic retries.

## Screenshots

| Desktop | Mobile |
| --- | --- |
| ![CallMap desktop workspace with player, transcript and reviewed commitment](docs/screenshots/desktop.png) | ![CallMap mobile layout](docs/screenshots/mobile.png) |

## Quick start (fixture mode, no key)

Prerequisites: Docker with Compose, Python **3.12 or newer**, Node **22.12+ or 24+** with npm. Check with `python3 --version` and `node --version`. If `python3` is older than 3.12, install a newer Python and use that interpreter (for example `python3.12` or `python3.13`) in the first command.

```sh
git clone https://github.com/abdulrehmanawan99/callmap.git
cd callmap
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
(cd web && npm ci)
cp .env.example .env
./scripts/dev.sh
```

`scripts/dev.sh` starts PostgreSQL and Redis with Docker Compose, applies migrations, prints a local access token, and runs the API, worker and web app. Open **http://127.0.0.1:5175** and paste the token (it is stored in `.data/local-token`; keep it private). Ctrl+C stops the app processes; the database containers keep running (`docker compose stop` stops them).

Then try the sample:

1. Click **Load sample**. The job moves from queued to ready in a few seconds.
2. Play the audio, click transcript segments, open **Exact source quotation** on a suggestion.
3. Type an owner on an action and click **Accept action**.
4. Click **Export reviewed** to download the reviewed items as JSON.

Everything binds to 127.0.0.1. Default ports are web 5175, API 8012, PostgreSQL 55434 and Redis 6382. To change them, edit `CALLMAP_WEB_PORT`, `CALLMAP_API_PORT`, `CALLMAP_PG_PORT` and `CALLMAP_REDIS_PORT` in `.env`. To run a second independent copy, also change `COMPOSE_PROJECT_NAME`.

Uploads must be uncompressed PCM WAV: 0.3 to 120 seconds, mono or stereo, 8 to 48 kHz, at most 24 MiB (10 MiB in Gemini mode). MP3 and M4A are not supported. In fixture mode, only the bundled sample (`fixtures/launch-checkin.wav`) produces a transcript; other WAVs fail with a clear message rather than showing made-up content.

## Use your own Gemini key

Live mode sends the audio of the uploads you opt in to Google. Use only synthetic audio, or recordings everyone in them has agreed to share.

1. Create an API key in Google AI Studio, in a project **with billing disabled**, so usage stays on the free tier. CallMap cannot check the project's billing status, never falls back to paid capacity, and does not retry quota errors.
2. Stop `scripts/dev.sh` if it is running.
3. In `.env`, set `CALLMAP_PROVIDER=gemini` and keep `CALLMAP_GEMINI_MODEL=gemini-3.5-flash-lite` (the only model accepted).
4. Export the key in the same shell, without saving it in a file you might commit, then start the app:

   ```sh
   read -rs GEMINI_API_KEY && export GEMINI_API_KEY
   ./scripts/dev.sh
   ```

5. Reload the page, tick **Send the next uploaded WAV to Gemini**, then upload a WAV (10 MiB and 120 s at most). The checkbox resets after each upload. **Load sample** always stays offline.
6. Review every suggestion. The model leaves unclear owners blank and keeps relative dates such as "next Friday" unresolved, so add owners and dates yourself before accepting.

To go back to offline mode, set `CALLMAP_PROVIDER=fixture` (or unset the key) and restart. Request limits, timeouts and the validation contract are described in [docs/live-provider.md](docs/live-provider.md).

## Tests

Unit and contract tests run offline. The integration tests need a dedicated database whose name ends in `_test`. They truncate it, so never point them at the app database.

```sh
.venv/bin/python -m pytest api/tests -q        # integration tests skip without a test database
docker compose exec -T postgres createdb -U callmap callmap_test   # once
CALLMAP_TEST_DATABASE_URL=postgresql://callmap:callmap_local_only@127.0.0.1:55434/callmap_test \
  .venv/bin/python -m pytest api/tests -q
(cd web && npm run build)
```

Offline evaluation scripts (they make no provider calls):

```sh
.venv/bin/python -m scripts.evaluate_live          # writes a "blocked" report, no requests
.venv/bin/python -m scripts.evaluate_independent   # lists the plan, no requests
.venv/bin/python -m scripts.score_independent \
  --results docs/independent-final-results.json --output .local/independent-final.json
```

The scorer exits 1 on that file because one case fails (see Limitations). CI runs the tests, the build, dependency and secret checks, and a Chromium run of the fixture workflow with accessibility scans.

## Limitations

- **Independent quality is not established.** On three new synthetic recordings with gates frozen before inference, Gemini passes **2 of 3 cases**. The named-owner/date case fails strict checks: the model wrote "Norah" for the spoken "Nora" and formatted the spoken date as digits, so owner agreement and word error rate both fail. See [independent validation](docs/independent-validation.md).
- Measurements so far use short synthetic speech from one voice. There is no evaluation on real, noisy or multi-speaker calls, and no speaker diarization.
- One provider only (Gemini 3.5 Flash-Lite). No accounts, no hosted deployment, no cloud storage; it assumes a single trusted OS user.
- WAV only. No automatic retention or trash; deletion is permanent.

## Troubleshooting

- **`Port 8012 is occupied` (or 5175):** another process is using it. Stop your earlier CallMap run, or set `CALLMAP_API_PORT` / `CALLMAP_WEB_PORT` in `.env`. The script never stops other processes.
- **`docker compose up` fails with "port is already allocated":** set `CALLMAP_PG_PORT` / `CALLMAP_REDIS_PORT` in `.env`.
- **`Install dependencies first`:** create `.venv` and run `npm ci` in `web/` as shown above.
- **Vite or npm complains about the Node version:** install Node 22.12+ or 24+.
- **`pip install` fails or `python3 -m venv` uses an old Python:** create the venv with Python 3.12 or newer.
- **The page rejects the token:** copy it again from the terminal or from `.data/local-token`.
- **An uploaded WAV fails in fixture mode:** expected. Fixture mode only knows the bundled sample; use Gemini mode for other audio.
- **Gemini job fails with a temporary-unavailability or quota error:** wait and click **Retry**. Retrying sends the audio again.
- **Start over with an empty database:** `docker compose down -v` deletes this project's database and Redis volumes. Also delete `.data/audio` if you want to remove stored WAVs.

## Docs

- [Architecture, provider boundary and decisions](docs/architecture.md)
- [Threat model](docs/threat-model.md)
- [Gemini setup, limits and evaluation](docs/live-provider.md)
- [Development live validation](docs/live-validation.md)
- [Independent synthetic evaluation](docs/independent-validation.md)
- [Verification record](docs/verification.md)
- [Release checks and attribution](docs/release-checks.md), [release notes](docs/release-notes.md)
- [Fixture manifest](fixtures/launch-checkin.json)
