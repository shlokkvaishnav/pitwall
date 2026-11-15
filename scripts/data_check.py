"""Spec 01 (amendment A1): check Jolpica data for the 2026 development races.

Usage: PYTHONPATH=src .venv/bin/python scripts/data_check.py
Writes results/01-data-check.json.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from pitwall.data import Jolpica, check_race, load_race, schedule
from pitwall.splits import split_of

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    client = Jolpica(ROOT / "data" / "jolpica-cache")
    sched = schedule(client, 2026)
    dev = sched[[split_of(d) == "development" for d in sched["date"]]]
    races = []
    for rnd in dev["round"]:
        r = check_race(load_race(client, 2026, int(rnd)))
        races.append(r)
        print(json.dumps(r), flush=True)

    d1 = [r["lap_coverage"] >= 0.90 for r in races]
    pits = sum(r["n_pitstops"] for r in races)
    pits_ok = sum(r["pitstop_on_known_lap"] * r["n_pitstops"] for r in races)
    drivers = sum(r["n_classified"] for r in races)
    order_ok = sum(r["last_lap_order_match"] * r["n_classified"] for r in races)
    rules = {
        "D1_lap_coverage_ge_0.90_all_races": all(d1),
        "D1_failed_rounds": [r["round"] for r, ok in zip(races, d1) if not ok],
        "D2_pitstops_on_known_lap": pits_ok / pits,
        "D2_pass": pits_ok / pits >= 0.99,
        "D3_last_lap_order_match": order_ok / drivers,
        "D3_pass": order_ok / drivers >= 0.95,
    }
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True)
    out = {"spec": "01-energy-limits-and-data (A1)", "commit": sha.stdout.strip(), "rules": rules, "races": races}
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "01-data-check.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(rules, indent=2))


if __name__ == "__main__":
    main()
