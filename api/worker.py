"""One local worker; durable PostgreSQL jobs, optional Redis wakeups."""

import hashlib
import signal
import time
import uuid

from psycopg.types.json import Jsonb
import redis

from api.core import DATA, connect, fixture_for, migrate, REDIS_URL
from api.providers import Gemini, ProviderError, PROMPT_VERSION, API_REVISION

STOP = False


def stop(*_):
    global STOP
    STOP = True


def still_active(recording_id, status):
    if STOP:
        return False
    with connect() as db:
        row = db.execute(
            "SELECT status FROM recordings WHERE id=%s", (recording_id,)
        ).fetchone()
    return bool(row and row["status"] == status)


def process(recording):
    """No external calls for fixture jobs; cancellation wins all result writes."""
    rid = recording["id"]
    try:
        if not still_active(rid, "transcribing"):
            return
        if recording["provider"] == "gemini":
            path = DATA / recording["storage_name"]
            if not path.is_file():
                raise ProviderError(
                    "Private audio is missing. Upload it again; no provider call was made."
                )
            data = path.read_bytes()
            if hashlib.sha256(data).hexdigest() != recording["sha256"]:
                raise ProviderError(
                    "Stored audio fingerprint changed. Upload the original again; no provider call was made."
                )
            provider = Gemini()
            if not still_active(rid, "transcribing"):
                return
            transcript = provider.transcribe(data, recording["duration"])
            segments = transcript.model_dump()["segments"]
            provenance = {
                "provider": "gemini",
                "model": provider.model,
                "api_revision": API_REVISION,
                "prompt_version": PROMPT_VERSION,
                "live_inference": True,
                "usage": provider.usage,
            }
        else:
            fixture = fixture_for(recording["sha256"])
            time.sleep(1.2)
            segments = fixture["segments"]
            provenance = {
                "provider": "fixture",
                "transcription": "authored-fixture-v1",
                "extraction": "authored-fixture-v1",
                "live_inference": False,
            }
        with connect() as db:
            changed = db.execute(
                "UPDATE recordings SET status='extracting', segments=%s, provenance=%s, updated_at=now() WHERE id=%s AND status='transcribing' RETURNING id",
                (Jsonb(segments), Jsonb(provenance), rid),
            ).fetchone()
        if not changed or not still_active(rid, "extracting"):
            return
        if recording["provider"] == "gemini":
            commitments = [
                item.model_dump(mode="json")
                for item in provider.extract(transcript).commitments
            ]
            provenance["usage"] = provider.usage
        else:
            time.sleep(1.2)
            commitments = [
                dict(
                    item,
                    source_quote=segments[item["segment_id"]]["text"],
                    date_expression="",
                )
                for item in fixture["commitments"]
            ]
        with connect() as db:
            current = db.execute(
                "SELECT status FROM recordings WHERE id=%s FOR UPDATE", (rid,)
            ).fetchone()
            if STOP or not current or current["status"] != "extracting":
                return
            for item in commitments:
                db.execute(
                    "INSERT INTO commitments (id,recording_id,segment_id,text,owner,due_date,kind,source_quote,date_expression) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        uuid.uuid4(),
                        rid,
                        item["segment_id"],
                        item["text"],
                        item["owner"],
                        item["due_date"],
                        item["kind"],
                        item["source_quote"],
                        item["date_expression"],
                    ),
                )
            db.execute(
                "UPDATE recordings SET status='ready', provenance=%s, updated_at=now() WHERE id=%s",
                (Jsonb(provenance), rid),
            )
    except (ValueError, OSError) as exc:
        message = (
            str(exc)
            if isinstance(exc, ValueError)
            else "Private audio could not be read. Retry explicitly or upload again."
        )
        with connect() as db:
            db.execute(
                "UPDATE recordings SET status='failed', error=%s, updated_at=now() WHERE id=%s AND status IN ('transcribing','extracting')",
                (message, rid),
            )


def run():
    migrate()
    # Session lock prevents two workers from resetting one another's live jobs.
    with connect() as leader:
        if not leader.execute(
            "SELECT pg_try_advisory_lock(84120477) AS acquired"
        ).fetchone()["acquired"]:
            raise SystemExit("A CallMap worker already holds the local worker lock.")
        leader.commit()
        with connect() as db:
            db.execute(
                "UPDATE recordings SET status='queued', segments='[]', updated_at=now() WHERE provider='fixture' AND status IN ('transcribing','extracting')"
            )
        with connect() as db:
            db.execute(
                "UPDATE recordings SET status='failed', error='Live job was interrupted. Retry explicitly; the prior provider request may have completed.', updated_at=now() WHERE provider='gemini' AND status IN ('transcribing','extracting')"
            )
        wake = redis.Redis.from_url(
            REDIS_URL, socket_connect_timeout=0.5, socket_timeout=2
        )
        print(
            "CallMap worker ready (fixture default, live opt-in) (PostgreSQL authoritative).",
            flush=True,
        )
        while not STOP:
            # Verify ownership session still lives before claiming more work.
            leader.execute("SELECT 1")
            leader.commit()
            with connect() as db:
                row = db.execute(
                    "SELECT * FROM recordings WHERE status='queued' ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1"
                ).fetchone()
                if row:
                    db.execute(
                        "UPDATE recordings SET status='transcribing', updated_at=now() WHERE id=%s",
                        (row["id"],),
                    )
            if row:
                process(row)
            else:
                try:
                    wake.blpop("callmap:wake", timeout=1)
                except redis.RedisError:
                    time.sleep(1)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    run()
