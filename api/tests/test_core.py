import hashlib
import io
import struct
import wave

import pytest

from api.core import FIXTURE, ROOT, fixture_for, validate_wav


def wav(seconds=1, rate=8000):
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        audio.writeframes(bytes(int(seconds * rate) * 2))
    return output.getvalue()


def test_bundled_audio_matches_fixture_and_timestamps():
    data = (ROOT / "fixtures/launch-checkin.wav").read_bytes()
    duration, fingerprint = validate_wav(data)
    assert fingerprint == FIXTURE["sha256"] == hashlib.sha256(data).hexdigest()
    assert abs(duration - FIXTURE["duration"]) < 0.01
    assert fixture_for(fingerprint)["segments"]
    end = 0
    for segment in FIXTURE["segments"]:
        assert end <= segment["start"] < segment["end"] <= duration
        end = segment["end"]


def test_unrelated_valid_audio_never_receives_fixture_claims():
    _, fingerprint = validate_wav(wav())
    with pytest.raises(ValueError, match="No live transcription"):
        fixture_for(fingerprint)


@pytest.mark.parametrize(
    "data, message",
    [
        (b"not a wav", "PCM WAV"),
        (wav(0.1), "between"),
        (wav(121), "between"),
        (wav()[:-12], "truncated"),
    ],
)
def test_bounded_parser(data, message):
    with pytest.raises(ValueError, match=message):
        validate_wav(data)


def test_header_cannot_request_unbounded_decode():
    data = bytearray(wav())
    data[40:44] = struct.pack("<I", 2**31)
    with pytest.raises(ValueError, match="between"):
        validate_wav(bytes(data))
