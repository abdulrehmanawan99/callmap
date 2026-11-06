"""Small persistence, media-validation, and fixture-provider boundaries."""

import hashlib
import io
import json
import os
from pathlib import Path
import secrets
import wave

import psycopg
from psycopg.rows import dict_row
import redis

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.getenv("CALLMAP_DATA_DIR", str(ROOT / ".data/audio"))).resolve()
DATA.mkdir(parents=True, exist_ok=True, mode=0o700)
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://callmap:callmap_local_only@127.0.0.1:55434/callmap"
)
REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6382/0")
MAX_BYTES = 24 * 1024 * 1024
FIXTURE = json.loads((ROOT / "fixtures/launch-checkin.json").read_text())


def local_token():
    configured = os.getenv("CALLMAP_LOCAL_TOKEN")
    if configured:
        return configured
    path = ROOT / ".data/local-token"
    path.parent.mkdir(mode=0o700, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return path.read_text().strip()
    token = secrets.token_urlsafe(32)
    with os.fdopen(fd, "w") as output:
        output.write(token)
    return token


def connect():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row, connect_timeout=5)


def migrate():
    with connect() as db:
        db.execute("SELECT pg_advisory_xact_lock(84120478)")
        db.execute((ROOT / "api/schema.sql").read_text())


def wake_worker():
    # PostgreSQL is the durable queue; Redis only reduces polling latency.
    try:
        redis.Redis.from_url(
            REDIS_URL, socket_connect_timeout=0.3, socket_timeout=0.3
        ).lpush("callmap:wake", "1")
    except redis.RedisError:
        pass


def validate_wav(data: bytes):
    if len(data) > MAX_BYTES:
        raise ValueError("Audio exceeds the 24 MiB limit.")
    if not data.startswith(b"RIFF") or data[8:12] != b"WAVE":
        raise ValueError(
            "Upload an uncompressed PCM WAV file. MP3, M4A, and renamed files are not supported."
        )
    try:
        with wave.open(io.BytesIO(data), "rb") as audio:
            channels, width, rate, frames = (
                audio.getnchannels(),
                audio.getsampwidth(),
                audio.getframerate(),
                audio.getnframes(),
            )
            if (
                channels not in (1, 2)
                or width not in (1, 2, 3, 4)
                or not 8000 <= rate <= 48000
            ):
                raise ValueError(
                    "Use mono or stereo PCM WAV, 8–48 kHz, with 8–32 bit samples."
                )
            duration = frames / rate
            if not 0.3 <= duration <= 120:
                raise ValueError("Audio must be between 0.3 seconds and 2 minutes.")
            if len(audio.readframes(frames)) != frames * channels * width:
                raise ValueError("The WAV data is truncated. Export the file again.")
    except (wave.Error, EOFError) as exc:
        raise ValueError(
            "Invalid or compressed WAV. Export uncompressed PCM WAV and try again."
        ) from exc
    return duration, hashlib.sha256(data).hexdigest()


def fixture_for(fingerprint: str):
    if fingerprint != FIXTURE["sha256"]:
        raise ValueError(
            "No live transcription provider is configured. Only the exact bundled synthetic sample supports fixture transcription."
        )
    return FIXTURE
