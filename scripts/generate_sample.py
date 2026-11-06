"""Build a genuine local speech sample; no external inference or downloads."""

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import wave

ROOT = Path(__file__).resolve().parents[1]
LINES = [
    (
        "Maya",
        "Thanks for joining the launch check in. We are aiming for a small pilot, not a public release.",
    ),
    (
        "Leo",
        "I will send the revised onboarding checklist to Maya by November twelfth, twenty twenty six.",
    ),
    (
        "Maya",
        "Great. I will book three customer interviews by November thirteenth, twenty twenty six.",
    ),
    (
        "Leo",
        "The analytics event names still need a decision. Who owns the final review?",
    ),
    (
        "Maya",
        "That is unresolved. Let us leave the owner open until the product review.",
    ),
    (
        "Leo",
        "I will prepare the pilot feedback summary by November sixteenth, twenty twenty six. That is everything from me.",
    ),
]
with tempfile.TemporaryDirectory() as tmp:
    frames = []
    segments = []
    cursor = 0
    rate = 22050
    for i, (speaker, text) in enumerate(LINES):
        aiff, wav = f"{tmp}/{i}.aiff", f"{tmp}/{i}.wav"
        subprocess.run(
            ["/usr/bin/say", "-v", "Samantha", "-r", "170", "-o", aiff, text],
            check=True,
        )
        subprocess.run(
            [
                "/usr/bin/afconvert",
                "-f",
                "WAVE",
                "-d",
                "LEI16@22050",
                "-c",
                "1",
                aiff,
                wav,
            ],
            check=True,
        )
        with wave.open(wav, "rb") as source:
            data = source.readframes(source.getnframes())
        duration = len(data) / 2 / rate
        segments.append(
            dict(
                id=i,
                speaker=speaker,
                text=text,
                start=round(cursor, 3),
                end=round(cursor + duration, 3),
            )
        )
        frames.extend([data, bytes(int(rate * 0.5) * 2)])
        cursor += duration + 0.5
    target = ROOT / "fixtures" / "launch-checkin.wav"
    with wave.open(str(target), "wb") as output:
        output.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        output.writeframes(b"".join(frames))
manifest = {
    "title": "Pilot launch · Thursday check-in",
    "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
    "duration": round(cursor, 3),
    "provenance": "Locally synthesized with macOS say / Samantha. Transcript is authored fixture data, not speech recognition.",
    "segments": segments,
    "commitments": [
        dict(
            segment_id=1,
            text="Send the revised onboarding checklist to Maya",
            owner="Leo",
            due_date="2026-11-12",
            kind="action",
        ),
        dict(
            segment_id=2,
            text="Book three customer interviews",
            owner="Maya",
            due_date="2026-11-13",
            kind="action",
        ),
        dict(
            segment_id=3,
            text="Who owns the final analytics event-name review?",
            owner="",
            due_date=None,
            kind="question",
        ),
        dict(
            segment_id=5,
            text="Prepare the pilot feedback summary",
            owner="Leo",
            due_date="2026-11-16",
            kind="action",
        ),
    ],
}
(ROOT / "fixtures" / "launch-checkin.json").write_text(
    json.dumps(manifest, indent=2) + "\n"
)
print(f"Generated {cursor:.1f}s synthetic WAV; sha256={manifest['sha256']}")
