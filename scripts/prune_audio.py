"""Offline orphan cleanup. Stop API/worker first; dry-run is the default."""

import argparse
import time
from uuid import UUID

from api.core import DATA, connect

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--apply", action="store_true")
args = parser.parse_args()
with connect() as db:
    known = {
        row["storage_name"] for row in db.execute("SELECT storage_name FROM recordings")
    }
for path in DATA.glob("*.wav"):
    try:
        UUID(path.stem)
    except ValueError:
        continue
    if path.name not in known and time.time() - path.stat().st_mtime > 3600:
        print(("Deleting " if args.apply else "Would delete ") + path.name)
        if args.apply:
            path.unlink()
