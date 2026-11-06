"""Runs only against the explicitly supplied disposable *_test database."""

import os
import subprocess
import sys
import time

import pytest
from fastapi.testclient import TestClient

from api.core import DATA, connect, migrate
from api.main import app
from api.tests.test_core import wav

pytestmark = pytest.mark.skipif(
    not os.getenv("CALLMAP_TEST_DATABASE_URL"),
    reason="Set CALLMAP_TEST_DATABASE_URL to a disposable *_test database.",
)
HEADERS = {"Authorization": "Bearer integration-test-token-only"}


@pytest.fixture
def client():
    migrate()
    with connect() as db:
        db.execute("TRUNCATE recordings CASCADE")
    with TestClient(app, headers=HEADERS) as client:
        yield client
    with connect() as db:
        db.execute("TRUNCATE recordings CASCADE")
    for path in DATA.glob("*.wav"):
        path.unlink()


def worker():
    return subprocess.Popen(
        [sys.executable, "-m", "api.worker"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )


def wait_for(client, rid, status, timeout=12):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        row = client.get(f"/api/recordings/{rid}").json()
        if row["status"] == status:
            return row
        time.sleep(0.06)
    raise AssertionError(f"Expected {status}; last state: {row}")


def test_auth_origin_upload_and_object_boundaries(client):
    assert (
        client.get(
            "/api/recordings", headers={b"Authorization": b"Bearer \xff"}
        ).status_code
        == 401
    )
    assert (
        client.get(
            "/api/recordings", headers={"Authorization": "Bearer wrong"}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/recordings/sample", headers={"Origin": "https://untrusted.example"}
        ).status_code
        == 403
    )
    assert (
        client.get("/api/recordings", headers={"Host": "attacker.example"}).status_code
        == 400
    )
    assert (
        client.post(
            "/api/recordings/upload",
            content=b"fake",
            headers={"Content-Type": "audio/wav"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/recordings/upload",
            content=wav(),
            headers={"Content-Type": "audio/mpeg"},
        ).status_code
        == 415
    )
    assert client.get("/api/recordings?limit=101").status_code == 422
    assert (
        client.post(
            "/api/recordings/upload",
            content=b"",
            headers={
                "Content-Type": "audio/wav",
                "Content-Length": str(25 * 1024 * 1024),
            },
        ).status_code
        == 413
    )
    assert (
        client.post(
            "/api/recordings/upload?title=%00bad",
            content=wav(),
            headers={"Content-Type": "audio/wav"},
        ).status_code
        == 422
    )
    assert (
        client.get(
            "/api/recordings/00000000-0000-0000-0000-000000000000/audio"
        ).status_code
        == 404
    )


def test_durable_job_review_export_cancellation_and_recovery(client):
    process = worker()
    try:
        rid = client.post("/api/recordings/sample").json()["id"]
        row = wait_for(client, rid, "ready")
        assert len(row["segments"]) == 6 and len(row["commitments"]) == 4
        assert client.get(f"/api/recordings/{rid}/audio").content.startswith(b"RIFF")
        assert client.get(f"/api/recordings/{rid}/export").json()["items"] == []
        item = row["commitments"][0]
        payload = {
            key: item[key] for key in ["text", "owner", "due_date", "kind", "version"]
        }
        payload |= {
            "text": "Send the reviewed onboarding checklist",
            "owner": "Maya",
            "accepted": True,
        }
        route = f"/api/recordings/{rid}/commitments/{item['id']}"
        updated = client.patch(route, json=payload)
        assert updated.status_code == 200
        assert client.patch(route, json=payload).status_code == 409  # stale editor
        payload["version"] = updated.json()["version"]
        assert client.patch(route, json=payload | {"owner": ""}).status_code == 422
        exported = client.get(f"/api/recordings/{rid}/export")
        assert exported.headers["content-disposition"].endswith(
            '"callmap-reviewed-items.json"'
        )
        assert (
            len(exported.json()["items"]) == 1
            and exported.json()["items"][0]["owner"] == "Maya"
        )
        second = client.post("/api/recordings/sample").json()["id"]
        row2 = wait_for(client, second, "ready")
        assert (
            client.patch(
                f"/api/recordings/{second}/commitments/{item['id']}", json=payload
            ).status_code
            == 409
        )
        assert not any(item["accepted"] for item in row2["commitments"])
        cancelled = client.post("/api/recordings/sample").json()["id"]
        assert client.post(f"/api/recordings/{cancelled}/cancel").status_code == 200
        time.sleep(2.6)
        assert (
            client.get(f"/api/recordings/{cancelled}").json()["status"] == "cancelled"
        )
        assert client.get(f"/api/recordings/{cancelled}").json()["commitments"] == []
        arbitrary = client.post(
            "/api/recordings/upload?title=Unrelated",
            content=wav(),
            headers={"Content-Type": "audio/wav"},
        ).json()["id"]
        failed = wait_for(client, arbitrary, "failed")
        assert (
            failed["segments"] == []
            and failed["commitments"] == []
            and "No live transcription" in failed["error"]
        )
        recovery = client.post("/api/recordings/sample").json()["id"]
        wait_for(client, recovery, "transcribing")
        process.kill()
        process.wait(timeout=5)
        process = worker()
        recovered = wait_for(client, recovery, "ready")
        assert len(recovered["commitments"]) == 4  # restart does not duplicate items
        # A new client reads the persisted review after worker restart.
        assert (
            client.get(f"/api/recordings/{rid}").json()["commitments"][0]["owner"]
            == "Maya"
        )
        with connect() as db:
            name = db.execute(
                "SELECT storage_name FROM recordings WHERE id=%s", (rid,)
            ).fetchone()["storage_name"]
        assert client.delete(f"/api/recordings/{rid}").status_code == 204
        assert not (DATA / name).exists()
        assert client.get(f"/api/recordings/{rid}").status_code == 404
        with connect() as db:
            assert (
                db.execute(
                    "SELECT count(*) AS n FROM commitments WHERE recording_id=%s",
                    (rid,),
                ).fetchone()["n"]
                == 0
            )
    finally:
        process.terminate()
        process.wait(timeout=5)


def test_live_pipeline_persistence_and_cancel_publish_guard(client, monkeypatch):
    import httpx
    from api import worker as jobs
    from api.providers import Gemini
    from api.tests.test_providers import TRANSCRIPT, ITEM, reply

    monkeypatch.setenv("CALLMAP_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-never-real")
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            200, json=reply(TRANSCRIPT if len(calls) % 2 else {"commitments": [ITEM]})
        )

    monkeypatch.setattr(
        jobs,
        "Gemini",
        lambda: Gemini(httpx.AsyncClient(transport=httpx.MockTransport(handler))),
    )

    def claim(rid):
        with connect() as db:
            return db.execute(
                "UPDATE recordings SET status='transcribing' WHERE id=%s RETURNING *",
                (rid,),
            ).fetchone()

    rid = client.post(
        "/api/recordings/upload?provider=gemini",
        content=wav(),
        headers={"Content-Type": "audio/wav"},
    ).json()["id"]
    jobs.process(claim(rid))
    row = client.get(f"/api/recordings/{rid}").json()
    assert row["status"] == "ready" and row["provider"] == "gemini" and len(calls) == 2
    assert row["commitments"][0]["source_quote"] == ITEM["source_quote"]
    assert (
        row["provenance"]["model"] == "gemini-3.8-flash"
        and len(row["provenance"]["usage"]) == 2
    )
    assert client.post(f"/api/recordings/{rid}/retry").status_code == 409
    # Cancellation during the HTTP call must suppress transcript/extraction publication.
    cancelled = client.post(
        "/api/recordings/upload?provider=gemini",
        content=wav(),
        headers={"Content-Type": "audio/wav"},
    ).json()["id"]

    def cancelling(request):
        client.post(f"/api/recordings/{cancelled}/cancel")
        return httpx.Response(200, json=reply(TRANSCRIPT))

    monkeypatch.setattr(
        jobs,
        "Gemini",
        lambda: Gemini(httpx.AsyncClient(transport=httpx.MockTransport(cancelling))),
    )
    jobs.process(claim(cancelled))
    row = client.get(f"/api/recordings/{cancelled}").json()
    assert (
        row["status"] == "cancelled"
        and row["segments"] == []
        and row["commitments"] == []
    )
    # Explicit retry is persisted; fixture jobs still never opt into Gemini implicitly.
    assert client.post(f"/api/recordings/{cancelled}/retry").status_code == 200
    assert client.get(f"/api/recordings/{cancelled}").json()["status"] == "queued"
    sample = client.post("/api/recordings/sample").json()
    assert sample["provider"] == "fixture"


def test_live_error_and_deletion_during_extraction_never_publish(client, monkeypatch):
    import httpx
    from api import worker as jobs
    from api.providers import Gemini
    from api.tests.test_providers import TRANSCRIPT, ITEM, reply

    # The environment default cannot silently turn fixture requests into external calls.
    monkeypatch.setenv("CALLMAP_PROVIDER", "fixture")
    assert (
        client.post(
            "/api/recordings/upload?provider=gemini",
            content=wav(),
            headers={"Content-Type": "audio/wav"},
        ).status_code
        == 409
    )
    monkeypatch.setenv("CALLMAP_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-never-real")

    def create_and_claim():
        rid = client.post(
            "/api/recordings/upload?provider=gemini",
            content=wav(),
            headers={"Content-Type": "audio/wav"},
        ).json()["id"]
        with connect() as db:
            row = db.execute(
                "UPDATE recordings SET status='transcribing' WHERE id=%s RETURNING *",
                (rid,),
            ).fetchone()
        return rid, row

    rid, row = create_and_claim()
    calls = []

    def quota(request):
        calls.append(1)
        return (
            httpx.Response(200, json=reply(TRANSCRIPT))
            if len(calls) == 1
            else httpx.Response(429, json={"private": "test-key-never-real"})
        )

    monkeypatch.setattr(
        jobs,
        "Gemini",
        lambda: Gemini(httpx.AsyncClient(transport=httpx.MockTransport(quota))),
    )
    jobs.process(row)
    result = client.get(f"/api/recordings/{rid}").json()
    assert (
        result["status"] == "failed"
        and result["commitments"] == []
        and "quota" in result["error"]
        and "test-key" not in result["error"]
    )
    assert len(calls) == 2
    deleted, row = create_and_claim()
    calls.clear()

    def deleting(request):
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(200, json=reply(TRANSCRIPT))
        assert client.delete(f"/api/recordings/{deleted}").status_code == 204
        return httpx.Response(200, json=reply({"commitments": [ITEM]}))

    monkeypatch.setattr(
        jobs,
        "Gemini",
        lambda: Gemini(httpx.AsyncClient(transport=httpx.MockTransport(deleting))),
    )
    jobs.process(row)
    assert client.get(f"/api/recordings/{deleted}").status_code == 404
    with connect() as db:
        assert (
            db.execute(
                "SELECT count(*) AS n FROM commitments WHERE recording_id=%s",
                (deleted,),
            ).fetchone()["n"]
            == 0
        )


def test_live_restart_fails_interrupted_job_without_replay(client, monkeypatch):
    monkeypatch.setenv("CALLMAP_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-never-real")
    rid = client.post(
        "/api/recordings/upload?provider=gemini", content=wav(),
        headers={"Content-Type": "audio/wav"},
    ).json()["id"]
    with connect() as db:
        db.execute("UPDATE recordings SET status='extracting' WHERE id=%s", (rid,))
    # Recovery must fail before invoking a provider, even with live configuration removed.
    monkeypatch.setenv("CALLMAP_PROVIDER", "fixture")
    monkeypatch.delenv("GEMINI_API_KEY")
    process = worker()
    try:
        result = wait_for(client, rid, "failed")
        assert "interrupted" in result["error"] and result["commitments"] == []
        time.sleep(1.2)
        assert client.get(f"/api/recordings/{rid}").json()["status"] == "failed"
        assert client.post(f"/api/recordings/{rid}/retry").status_code == 409
    finally:
        process.terminate()
        process.wait(timeout=5)


def test_database_insert_failure_removes_private_upload(client, monkeypatch):
    from api import main

    before = set(DATA.glob("*.wav"))

    def unavailable():
        raise RuntimeError("Synthetic database failure")

    monkeypatch.setattr(main, "connect", unavailable)
    with pytest.raises(RuntimeError, match="Synthetic database failure"):
        client.post("/api/recordings/upload", content=wav(), headers={"Content-Type": "audio/wav"})
    assert set(DATA.glob("*.wav")) == before


@pytest.mark.parametrize("phase,fail", [("transcribing", False), ("transcribing", True), ("extracting", False), ("extracting", True)])
def test_stale_attempt_cannot_publish_or_fail_same_status_successor(client, monkeypatch, phase, fail):
    import httpx
    from api import worker as jobs
    from api.providers import Gemini
    from api.tests.test_providers import TRANSCRIPT, ITEM, reply

    monkeypatch.setenv("CALLMAP_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-never-real")
    rid = client.post(
        "/api/recordings/upload?provider=gemini", content=wav(),
        headers={"Content-Type": "audio/wav"},
    ).json()["id"]
    with connect() as db:
        old = db.execute(
            "UPDATE recordings SET status='transcribing', attempt=attempt+1 WHERE id=%s RETURNING *", (rid,)
        ).fetchone()
    calls, successor = [], []

    def handler(request):
        calls.append(1)
        target_call = 1 if phase == "transcribing" else 2
        if len(calls) == target_call:
            # Simulate recovery/reclaim while the old HTTP request remains in flight.
            # The new generation deliberately has exactly the same workflow status.
            with connect() as db:
                successor.append(db.execute(
                    "UPDATE recordings SET attempt=attempt+1 WHERE id=%s RETURNING *", (rid,)
                ).fetchone())
            if fail:
                return httpx.Response(429)
        return httpx.Response(200, json=reply(TRANSCRIPT if len(calls) == 1 else {"commitments": [ITEM]}))

    monkeypatch.setattr(jobs, "Gemini", lambda: Gemini(httpx.AsyncClient(transport=httpx.MockTransport(handler))))
    jobs.process(old)
    assert len(calls) == (1 if phase == "transcribing" else 2)
    with connect() as db:
        current = db.execute("SELECT * FROM recordings WHERE id=%s", (rid,)).fetchone()
        count = db.execute("SELECT count(*) AS n FROM commitments WHERE recording_id=%s", (rid,)).fetchone()["n"]
    assert current == successor[0] and current["status"] == phase
    assert count == 0
    assert not jobs.still_active(rid, phase, old["attempt"])
