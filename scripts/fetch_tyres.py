"""Download the TracingInsights race lap files for 2022 to 2025 and the 2026 development races (no holdout races).

Usage: PYTHONPATH=src .venv/bin/python scripts/fetch_tyres.py
Writes data/raw/tracinginsights/<year>/<round>.json and data/raw/tracinginsights/manifest.json (SHA-256 of each file).
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.request
from pathlib import Path

from pitwall.dump import Dump
from pitwall.lapmodel import PRETRAIN_SEASONS
from pitwall.splits import split_of
from pitwall.tyres import url

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "tracinginsights"


def main() -> None:
    dump = Dump(ROOT / "data" / "raw" / "jolpica-dump" / "csv")
    manifest = {}
    for year in (*PRETRAIN_SEASONS, 2026):
        for _, r in dump.schedule(year).iterrows():
            if split_of(r["date"]) == "holdout":
                continue  # the holdout lock: we do not download these races
            path = OUT / str(year) / f"{int(r['round']):02d}.json"
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                req = urllib.request.Request(url(year, r["name"]), headers={"User-Agent": "pitwall-research"})
                with urllib.request.urlopen(req, timeout=60) as resp:
                    path.write_bytes(resp.read())
                time.sleep(0.5)
            manifest[f"{year}/{int(r['round']):02d}"] = {
                "name": r["name"],
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            print(year, int(r["round"]), r["name"], flush=True)
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(len(manifest), "files")


if __name__ == "__main__":
    main()
