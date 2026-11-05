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
