# Architecture — first fixture milestone

```mermaid
flowchart LR
  UI[React audio workspace :5175] -->|Bearer token via Vite proxy| API[FastAPI :8012]
  API -->|private UUID WAV| Disk[.data/audio]
  API -->|recording + durable queued state| PG[(PostgreSQL :55434)]
  API -. wake hint .-> Redis[(Redis :6382)]
  Redis -. bounded wait .-> Worker[Single fixture worker]
  Worker -->|claim + guarded state transitions| PG
  Manifest[Fingerprint-gated authored fixture v1] --> Worker
  PG -->|segments and reviewed commitments| API
  API -->|reviewed JSON export| UI
```

`api/core.py` owns configuration, database connections, bounded WAV validation, local-token generation, and the small `fixture_for(fingerprint)` provider boundary. `api/main.py` owns HTTP contracts/upload/review/export. `api/worker.py` owns phase transitions. `api/schema.sql` is the idempotent version-1 schema migration, serialized by a transaction advisory lock. PostgreSQL is authoritative; a lost Redis wakeup costs up to one second of polling latency, not a lost recording.

Each job advances `queued → transcribing → extracting → ready`, with cancellation and failure terminal states. Status names represent fixture presentation phases, explicitly labeled in the UI. The two 1.2-second pauses demonstrate job observation; they do not measure model latency. A session advisory lock permits one local worker. On restart, interrupted transcription/extraction returns to queued; completed reviews remain untouched. Row locks/state predicates ensure cancellation/deletion wins future phase transitions and commitment insertion commits atomically with ready. There is no automatic retry of terminal failures; load/upload creates a new recording. Crash recovery is at-least-once processing with guarded writes, not a distributed exactly-once claim.

Edits use a version counter for stale-editor conflicts and always scope item IDs to the recording ID. Actions require an owner when reviewed; a date may remain unspecified. Questions can be reviewed as open questions or explicitly changed to actions. JSON exports contain only persisted reviewed items, plus the source fingerprint and authored provider-version labels. Library queries expose `limit` (1–100) and `offset`; the current UI intentionally loads only the latest 100 recordings.

The browser fetches authorized private audio into an object URL, derives a waveform from decoded PCM, and uses the same audio clock for segment selection. Segment timing is derived from concatenated synthesized utterance lengths, including half-second gaps. Speaker names are authored labels; both voices use Samantha, with no diarization claim.

## Live-provider acceptance pending

There is no live provider implementation or key intake. Before adding one, replace the tiny fixture boundary with a transcription capability accepting validated audio and returning bounded timestamp segments; pass the transcript to a separate structured extraction capability. Validate both outputs against typed contracts, retain source/provider/model/prompt versions, add timeout/output/usage budgets, and keep cancellation predicates between external calls and commits. Do not map unknown audio to the sample manifest.

Test two authorized speech/text configurations when available. Establish transcription WER, timestamp alignment, extraction precision/recall, failure examples, cost and latency baselines on consented/synthetic evaluation audio before setting thresholds. Current fingerprint/fixture checks validate product mechanics only.

## Retention and recovery

Audio, reviews, and jobs persist until explicit deletion. PostgreSQL and Redis have distinct project volumes; private audio resides in the checkout's ignored `.data`. Back up both the PostgreSQL database and audio directory together if needed. A file write happens before the recording transaction; a process kill in that short window can leave an orphan WAV. `scripts/prune_audio.py` lists orphan UUID WAVs by default; `--apply` deletes only listed orphans older than one hour. Run `.venv/bin/python -m scripts.prune_audio` (or add `--apply`) with API/worker stopped. There is no automatic retention, backup, retry scheduler, or production supervisor.
