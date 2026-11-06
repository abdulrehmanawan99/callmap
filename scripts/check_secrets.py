"""Scan project text and built bundles without printing matched credential values."""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "openai_key": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}"),
    "github_token": re.compile(r"\b(?:ghp_|github_pat_)[A-Za-z0-9_]{30,}"),
    "google_key": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    "aws_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--include-build", action="store_true")
    args = parser.parse_args()
    paths = {
        ROOT / value.decode()
        for value in subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT
        ).split(b"\0") if value
    }
    if args.include_build:
        paths.update(path for path in (ROOT / "web/dist").rglob("*") if path.is_file())
    # Optional coordinator check: never read a key file or print this value.
    exact = os.getenv("SECRET_SCAN_VALUE", "")
    findings = []
    scanned = 0
    for path in sorted(paths):
        if not path.is_file():
            continue
        data = path.read_bytes()
        if b"\x00" in data:
            continue
        text = data.decode("utf-8", errors="replace")
        scanned += 1
        for name, pattern in PATTERNS.items():
            if pattern.search(text):
                findings.append({"file": str(path.relative_to(ROOT)), "pattern": name})
        if exact and exact in text:
            findings.append({"file": str(path.relative_to(ROOT)), "pattern": "supplied_value"})
    print(json.dumps({"state": "failed" if findings else "passed", "text_files": scanned, "findings": findings}))
    raise SystemExit(bool(findings))


if __name__ == "__main__":
    main()
