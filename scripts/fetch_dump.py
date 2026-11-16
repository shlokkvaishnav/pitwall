"""Download the Jolpica free delayed CSV dump and check its SHA-256 (spec 01, amendment A2).

Usage: PYTHONPATH=src python scripts/fetch_dump.py [--accept-new-dump]
Jolpica replaces the delayed dump over time. Our results use the dump of 2026-11-01 (SHA-256 below).
A newer dump has more races. The holdout lock stays. But the development results can change a little.
Thus, the script stops if the hash is different, unless you pass --accept-new-dump.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
import zipfile
from pathlib import Path

URL = "https://api.jolpi.ca/data/dumps/download/delayed/?dump_type=csv"
PINNED_SHA256 = "34ae3788503c17931e500c347211efaa534a93fced707ed7788bfe17dd2c4334"
OUT = Path(__file__).resolve().parents[1] / "data" / "raw" / "jolpica-dump"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--accept-new-dump", action="store_true")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    zpath = OUT / "dump.zip"
    if not zpath.exists():
        req = urllib.request.Request(URL, headers={"User-Agent": "pitwall-research"})
        with urllib.request.urlopen(req, timeout=300) as resp:
            zpath.write_bytes(resp.read())
    digest = sha256(zpath)
    if digest != PINNED_SHA256:
        msg = f"dump SHA-256 is {digest}, the results use {PINNED_SHA256}"
        if not args.accept_new_dump:
            sys.exit(msg + ". Pass --accept-new-dump to continue with this dump.")
        print("warning:", msg)
    if not (OUT / "csv").exists():
        with zipfile.ZipFile(zpath) as z:
            z.extractall(OUT / "csv")
    print("dump ready:", digest)


if __name__ == "__main__":
    main()
