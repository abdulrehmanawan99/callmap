"""One local worker; durable PostgreSQL jobs, optional Redis wakeups."""

import signal
import time
import uuid

from psycopg.types.json import Jsonb
import redis

from api.core import connect, fixture_for, migrate, REDIS_URL

STOP = False


def stop(*_):
    global STOP
    STOP = True


def process(recording):
    """State predicates make cancellation/deletion win each phase transition."""
    try:
        fixture = fixture_for(recording["sha256"])
        time.sleep(1.2)  # Deliberate fixture presentation delay; no real inference.
        with connect() as db:
            changed = db.execute(
                "UPDATE recordings SET status='extracting', segments=%s, updated_at=now() WHERE id=%s AND status='transcribing' RETURNING id",
                (Jsonb(fixture["segments"]), recording["id"]),
            ).fetchone()
        if not changed or STOP:
            return
        time.sleep(1.2)
        with connect() as db:
            current = db.execute(
                "SELECT status FROM recordings WHERE id=%s FOR UPDATE",
                (recording["id"],),
            ).fetchone()
            if not current or current["status"] != "extracting":
                return
            for item in fixture["commitments"]:
                db.execute(
                    "INSERT INTO commitments (id, recording_id, segment_id, text, owner, due_date, kind) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (
                        uuid.uuid4(),
                        recording["id"],
                        item["segment_id"],
                        item["text"],
                        item["owner"],
                        item["due_date"],
                        item["kind"],
                    ),
                )
            db.execute(
                "UPDATE recordings SET status='ready', updated_at=now() WHERE id=%s",
                (recording["id"],),
            )
    except ValueError as exc:
        with connect() as db:
            db.execute(
                "UPDATE recordings SET status='failed', error=%s, updated_at=now() WHERE id=%s AND status IN ('transcribing','extracting')",
                (str(exc), recording["id"]),
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
                "UPDATE recordings SET status='queued', segments='[]', updated_at=now() WHERE status IN ('transcribing','extracting')"
            )
        wake = redis.Redis.from_url(
            REDIS_URL, socket_connect_timeout=0.5, socket_timeout=2
        )
        print("CallMap fixture worker ready (PostgreSQL authoritative).", flush=True)
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
