"""Create original labeled synthetic recordings, without network or model calls."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import wave

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'fixtures/independent'
CASES = [
    ('background-only', ["The blue folder contains last month's inventory figures. The wall clock is above the reception desk."], []),
    ('named-calendar', ['Nora will email the shipping summary by December seventh, twenty twenty six.'], [dict(kind='action', keywords=['shipping', 'summary'], owner='Nora', due_date='2026-12-07', reference_segment=0)]),
    ('relative-open', ['I will update the warehouse roster tomorrow.', 'Who approves the replacement labels next Friday?'], [dict(kind='action', keywords=['warehouse', 'roster'], owner='', due_date=None, reference_segment=0), dict(kind='question', keywords=['replacement', 'labels'], owner='', due_date=None, reference_segment=1)]),
]


def main():
    TARGET.mkdir(exist_ok=True)
    manifests = []
    for name, lines, expected in CASES:
        frames, segments, cursor = [], [], 0.0
        rate = 22050
        with tempfile.TemporaryDirectory() as tmp:
            for index, text in enumerate(lines):
                aiff, wav = Path(tmp) / f'{index}.aiff', Path(tmp) / f'{index}.wav'
                subprocess.run(['/usr/bin/say', '-v', 'Samantha', '-r', '170', '-o', str(aiff), text], check=True)
                subprocess.run(['/usr/bin/afconvert', '-f', 'WAVE', '-d', 'LEI16@22050', '-c', '1', str(aiff), str(wav)], check=True)
                with wave.open(str(wav), 'rb') as source:
                    pcm = source.readframes(source.getnframes())
                duration = len(pcm) / 2 / rate
                segments.append(dict(id=index, speaker='Synthetic voice', text=text, start=round(cursor, 3), end=round(cursor + duration, 3)))
                frames.extend([pcm, bytes(int(rate * .5) * 2)])
                cursor += duration + .5
        audio = TARGET / f'{name}.wav'
        with wave.open(str(audio), 'wb') as output:
            output.setparams((1, 2, rate, 0, 'NONE', 'not compressed'))
            output.writeframes(b''.join(frames))
        manifest = dict(id=name, audio=audio.name, sha256=hashlib.sha256(audio.read_bytes()).hexdigest(), duration=round(cursor, 3), segments=segments, expected=expected, provenance='Original synthetic speech: local macOS say Samantha 170 wpm; PCM afconvert; authored labels and word-boundary timing frozen before inference. No speaker-identification label is inferred from voice.')
        (TARGET / f'{name}.json').write_text(json.dumps(manifest, indent=2) + '\n')
        manifests.append(f'{name}.json')
    (TARGET / 'corpus.json').write_text(json.dumps(dict(version='callmap-independent-synthetic-v1', split='prospective independent synthetic cases; frozen before first inference, distinct from development recording', gates='gates.json', cases=manifests), indent=2) + '\n')
    print('Generated three original synthetic cases; no inference made.')


if __name__ == '__main__':
    main()
