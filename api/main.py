import asyncio
from contextlib import asynccontextmanager
from datetime import date
import json
import os
import secrets
from typing import Literal
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from api.providers import MAX_LIVE_BYTES, MODEL

from api.core import (
    DATA,
    FIXTURE,
    MAX_BYTES,
    ROOT,
    connect,
    local_token,
    migrate,
    validate_wav,
    wake_worker,
)

TOKEN = local_token()
WEB_PORT = os.getenv("CALLMAP_WEB_PORT", "5175")
ORIGINS = {f"http://localhost:{WEB_PORT}", f"http://127.0.0.1:{WEB_PORT}"}


@asynccontextmanager
async def lifespan(_):
    migrate()
    yield


app = FastAPI(title="CallMap local audio workspace API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(ORIGINS),
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["Content-Disposition"],
)


@app.middleware("http")
async def local_boundary(request: Request, call_next):
    if request.headers.get("host", "").split(":")[0] not in {
        "localhost",
        "127.0.0.1",
        "testserver",
    }:
        return Response("Invalid local host", status_code=400)
    origin = request.headers.get("origin")
    if origin and origin not in ORIGINS:
        return Response("Origin is not allowed", status_code=403)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def authorize(request: Request):
    supplied = request.headers.get("authorization", "")
    if not secrets.compare_digest(supplied.encode(), f"Bearer {TOKEN}".encode()):
        raise HTTPException(
            401, "Enter the local access token printed by scripts/dev.sh."
        )


def recording(db, recording_id, lock=False):
    query = (
        "SELECT * FROM recordings WHERE id=%s FOR UPDATE"
        if lock else "SELECT * FROM recordings WHERE id=%s"
    )
    row = db.execute(
        query,
        (recording_id,),
    ).fetchone()
    if not row:
        raise HTTPException(404, "Recording not found.")
    return row


def public(row):
    return {
        key: value
        for key, value in row.items()
        if key not in {"storage_name", "sha256", "attempt"}
    } | {"fixture": row["sha256"] == FIXTURE["sha256"]}


def create_recording(data, title, provider="fixture"):
    if provider == "gemini":
        if os.getenv("CALLMAP_PROVIDER", "fixture") != "gemini" or not os.getenv(
            "GEMINI_API_KEY"
        ):
            raise HTTPException(
                409,
                "Live Gemini is not configured. Default fixture mode sends no audio externally.",
            )
        if len(data) > MAX_LIVE_BYTES:
            raise HTTPException(413, "Live Gemini inline audio is limited to 10 MiB.")
    try:
        duration, fingerprint = validate_wav(data)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    rid = uuid4()
    name = f"{rid}.wav"
    path = DATA / name
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as output:
        output.write(data)
    try:
        with connect() as db:
            row = db.execute(
                "INSERT INTO recordings (id,title,storage_name,sha256,duration,status,provider) VALUES (%s,%s,%s,%s,%s,'queued',%s) RETURNING *",
                (rid, title, name, fingerprint, duration, provider),
            ).fetchone()
    except Exception:
        path.unlink(missing_ok=True)
        raise
    wake_worker()
    return public(row)


@app.get("/api/health")
def health():
    return {
        "mode": "fixture default; optional Gemini",
        "live_inference": os.getenv("CALLMAP_PROVIDER", "fixture") == "gemini"
        and bool(os.getenv("GEMINI_API_KEY")),
        "live_model": MODEL,
    }


@app.get("/api/recordings", dependencies=[Depends(authorize)])
def list_recordings(
    limit: int = Query(default=100, ge=1, le=100), offset: int = Query(default=0, ge=0)
):
    with connect() as db:
        return [
            public(row)
            for row in db.execute(
                "SELECT * FROM recordings ORDER BY created_at DESC, id LIMIT %s OFFSET %s",
                (limit, offset),
            ).fetchall()
        ]


@app.post("/api/recordings/sample", status_code=201, dependencies=[Depends(authorize)])
def load_sample():
    data = (ROOT / "fixtures/launch-checkin.wav").read_bytes()
    if validate_wav(data)[1] != FIXTURE["sha256"]:
        raise HTTPException(
            409,
            "Sample and manifest fingerprints differ. Restore the committed fixture pair.",
        )
    return create_recording(data, FIXTURE["title"])


@app.post("/api/recordings/upload", status_code=201, dependencies=[Depends(authorize)])
async def upload(
    request: Request,
    title: str = "Uploaded recording",
    provider: Literal["fixture", "gemini"] = "fixture",
):
    title = title.strip()
    if not title or len(title) > 120 or any(ord(c) < 32 for c in title):
        raise HTTPException(
            422, "Give the recording a title of 1–120 printable characters."
        )
    if request.headers.get("content-type", "").split(";")[0] not in {
        "audio/wav",
        "audio/x-wav",
        "application/octet-stream",
    }:
        raise HTTPException(415, "Choose a PCM WAV file, up to 24 MiB and 2 minutes.")
    length = request.headers.get("content-length", "")
    if length.isdigit() and int(length) > MAX_BYTES:
        raise HTTPException(413, "Audio exceeds the 24 MiB limit.")
    data = bytearray()
    try:
        async with asyncio.timeout(20):
            async for chunk in request.stream():
                if len(data) + len(chunk) > MAX_BYTES:
                    raise HTTPException(413, "Audio exceeds the 24 MiB limit.")
                data.extend(chunk)
    except TimeoutError as exc:
        raise HTTPException(
            408, "Upload took longer than 20 seconds. Retry on this local connection."
        ) from exc
    return create_recording(bytes(data), title, provider)


@app.get("/api/recordings/{recording_id}", dependencies=[Depends(authorize)])
def detail(recording_id: UUID):
    with connect() as db:
        row = recording(db, recording_id)
        items = db.execute(
            "SELECT * FROM commitments WHERE recording_id=%s ORDER BY segment_id",
            (recording_id,),
        ).fetchall()
    return public(row) | {"commitments": items}


@app.get("/api/recordings/{recording_id}/audio", dependencies=[Depends(authorize)])
def audio(recording_id: UUID):
    with connect() as db:
        row = recording(db, recording_id)
    path = DATA / row["storage_name"]
    if not path.is_file():
        raise HTTPException(
            410,
            "Audio is missing from local storage. Delete this recording and load it again.",
        )
    return FileResponse(path, media_type="audio/wav")


@app.post("/api/recordings/{recording_id}/cancel", dependencies=[Depends(authorize)])
def cancel(recording_id: UUID):
    with connect() as db:
        row = recording(db, recording_id, lock=True)
        if row["status"] not in {"queued", "transcribing", "extracting", "cancelled"}:
            raise HTTPException(409, "Only a pending job can be cancelled.")
        db.execute(
            "UPDATE recordings SET status='cancelled', segments='[]', updated_at=now() WHERE id=%s",
            (recording_id,),
        )
    return {"status": "cancelled"}


@app.delete(
    "/api/recordings/{recording_id}", status_code=204, dependencies=[Depends(authorize)]
)
def delete(recording_id: UUID):
    with connect() as db:
        row = recording(db, recording_id, lock=True)
        # Unlink before commit: missing files are tolerated and deletion is retryable.
        (DATA / row["storage_name"]).unlink(missing_ok=True)
        db.execute("DELETE FROM recordings WHERE id=%s", (recording_id,))
    return Response(status_code=204)


@app.post("/api/recordings/{recording_id}/retry", dependencies=[Depends(authorize)])
def retry(recording_id: UUID):
    with connect() as db:
        row = recording(db, recording_id, lock=True)
        if row["status"] not in {"failed", "cancelled"}:
            raise HTTPException(
                409, "Only failed or cancelled jobs can be retried explicitly."
            )
        if row["provider"] == "gemini" and (
            os.getenv("CALLMAP_PROVIDER", "fixture") != "gemini"
            or not os.getenv("GEMINI_API_KEY")
        ):
            raise HTTPException(
                409, "Configure live Gemini before retrying this recording."
            )
        db.execute("DELETE FROM commitments WHERE recording_id=%s", (recording_id,))
        db.execute(
            "UPDATE recordings SET status='queued', attempt=attempt+1, error=NULL, segments='[]', provenance='{}', updated_at=now() WHERE id=%s",
            (recording_id,),
        )
    wake_worker()
    return {"status": "queued"}


class Review(BaseModel):
    text: str = Field(min_length=1, max_length=600)
    owner: str = Field(max_length=100)
    due_date: date | None = None
    kind: Literal["action", "question"]
    accepted: bool
    version: int = Field(ge=1)


@app.patch(
    "/api/recordings/{recording_id}/commitments/{item_id}",
    dependencies=[Depends(authorize)],
)
def review(recording_id: UUID, item_id: UUID, change: Review):
    text, owner = change.text.strip(), change.owner.strip()
    if not text or any(ord(c) < 32 and c not in "\n\t" for c in text + owner):
        raise HTTPException(422, "Use readable text for the commitment and owner.")
    if change.accepted and change.kind == "action" and not owner:
        raise HTTPException(422, "Assign an owner before accepting an action.")
    with connect() as db:
        row = recording(db, recording_id, lock=True)
        if row["status"] != "ready":
            raise HTTPException(409, "Review is available when the recording is ready.")
        item = db.execute(
            "UPDATE commitments SET text=%s, owner=%s, due_date=%s, kind=%s, accepted=%s, version=version+1 WHERE id=%s AND recording_id=%s AND version=%s RETURNING *",
            (
                text,
                owner,
                change.due_date,
                change.kind,
                change.accepted,
                item_id,
                recording_id,
                change.version,
            ),
        ).fetchone()
        if not item:
            raise HTTPException(
                409, "This item changed or no longer exists. Refresh before saving."
            )
    return item


@app.get("/api/recordings/{recording_id}/export", dependencies=[Depends(authorize)])
def export(recording_id: UUID):
    with connect() as db:
        row = recording(db, recording_id)
        if row["status"] != "ready":
            raise HTTPException(409, "Export is available after review becomes ready.")
        items = db.execute(
            "SELECT text,owner,due_date,kind,segment_id,source_quote,date_expression FROM commitments WHERE recording_id=%s AND accepted=true ORDER BY segment_id",
            (recording_id,),
        ).fetchall()
    # JSON download avoids spreadsheet formula injection and active HTML/Markdown.
    payload = {
        "title": row["title"],
        "mode": f"{row['provider']}; human reviewed",
        "provenance": {"source_sha256": row["sha256"], **row["provenance"]},
        "items": items,
    }
    return Response(
        json.dumps(payload, default=str, indent=2),
        media_type="application/json",
        headers={
            "Content-Disposition": 'attachment; filename="callmap-reviewed-items.json"'
        },
    )
