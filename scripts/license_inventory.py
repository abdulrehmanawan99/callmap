"""Inventory locked dependency metadata; retain dependencies' distributed notices."""

from datetime import datetime, timezone
from importlib.metadata import distribution
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    python = []
    for line in (ROOT / "requirements.lock").read_text().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        name, version = line.split("==")
        package = distribution(name)
        if package.version != version:
            raise SystemExit(f"Install the locked version of {name} before inventorying.")
        meta = package.metadata
        classifiers = [
            value.removeprefix("License :: ")
            for value in meta.get_all("Classifier", [])
            if value.startswith("License ::")
        ]
        python.append({
            "name": name,
            "version": version,
            "license": meta.get("License-Expression") or classifiers
            or (meta.get("License") or "Review distributed notices").splitlines()[0],
            "notice_files": [
                str(path) for path in package.files or []
                if any(word in str(path).lower() for word in ("license", "copying", "notice"))
            ],
        })
    lock = json.loads((ROOT / "web/package-lock.json").read_text())
    npm = [
        {
            "path": path,
            "version": package.get("version"),
            "license": package.get("license", "Review distributed notices"),
            "development": package.get("dev", False),
            "optional": package.get("optional", False),
        }
        for path, package in sorted(lock["packages"].items()) if path
    ]
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Locked Python and npm dependencies, including development and optional platforms. Metadata inventory, not legal clearance. Distributed notices remain with packages. No project-wide redistribution license has been selected.",
        "python": python,
        "npm": npm,
    }
    (ROOT / "docs/licenses.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"python_packages": len(python), "npm_lock_entries": len(npm)}))


if __name__ == "__main__":
    main()
