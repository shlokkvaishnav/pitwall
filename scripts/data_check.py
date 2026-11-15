"""Spec 01 (amendments A1 and A2): check the Jolpica dump for 2022-2025 and the 2026 development races.

Usage: PYTHONPATH=src .venv/bin/python scripts/data_check.py
Writes results/01-data-check.json.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np

from pitwall.data import Jolpica, check_race, load_race
from pitwall.dump import Dump
from pitwall.splits import split_of

ROOT = Path(__file__).resolve().parents[1]
DUMP = ROOT / "data" / "raw" / "jolpica-dump" / "csv"
SEASONS = (2022, 2023, 2024, 2025, 2026)


def rules_for(races: list[dict]) -> dict:
    d1 = [r["lap_coverage"] >= 0.90 for r in races]
    pits = sum(r["n_pitstops"] for r in races)
    pits_ok = sum(r["pitstop_on_known_lap"] * r["n_pitstops"] for r in races)
    drivers = sum(r["n_classified"] for r in races)
    order_ok = sum(r["last_lap_order_match"] * r["n_classified"] for r in races)
    return {
        "n_races": len(races),
        "D1_pass": all(d1),
        "D1_failed": [(r["season"], r["round"]) for r, ok in zip(races, d1) if not ok],
        "D2_pitstops_on_known_lap": pits_ok / pits,
        "D2_pass": pits_ok / pits >= 0.99,
        "D3_last_lap_order_match": order_ok / drivers,
        "D3_pass": order_ok / drivers >= 0.95,
    }


def dump_vs_api(dump: Dump) -> dict:
    """Rule D4: compare the dump with the races that the API cache has."""
    client = Jolpica(ROOT / "data" / "jolpica-cache", min_interval_s=8.0)
    cached = sorted(
        int(p.name.split("_")[1]) for p in client.cache.glob("2026_*_laps.json") if p.name.split("_")[1].isdigit()
    )
    same = total = 0
    for rnd in cached:
        if not all((client.cache / f"2026_{rnd}_{k}.json").exists() for k in ("laps", "pitstops", "results")):
            continue
        api = load_race(client, 2026, rnd).laps.set_index(["driver", "lap"])
        dmp = dump.race(2026, rnd).laps.set_index(["driver", "lap"])
        joined = api.join(dmp, how="left", rsuffix="_dump")
        ok = (joined["position"] == joined["position_dump"]) & (
            (joined["time_s"] - joined["time_s_dump"]).abs() <= 0.001
        )
        same += int(ok.sum())
        total += len(joined)
    frac = same / total if total else float("nan")
    return {"rounds": cached, "rows": total, "match_fraction": frac, "D4_pass": bool(total and frac >= 0.995)}


def main() -> None:
    dump = Dump(DUMP)
    races = {"pretrain": [], "development": []}
    for season in SEASONS:
        for rnd, d in zip(dump.schedule(season)["round"], dump.schedule(season)["date"]):
            split = split_of(d)
            if split == "holdout":
                continue
            r = check_race(dump.race(season, int(rnd)))
            races[split].append(r)
        print(season, "done", flush=True)

    out_rules = {k: rules_for(v) for k, v in races.items()}
    out_rules["D4"] = dump_vs_api(dump)
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True)
    out = {
        "spec": "01-energy-limits-and-data (A1, A2)",
        "commit": sha.stdout.strip(),
        "dump_sha256": "34ae3788503c17931e500c347211efaa534a93fced707ed7788bfe17dd2c4334",
        "rules": out_rules,
        "races": races,
    }
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "01-data-check.json").write_text(json.dumps(out, indent=2, default=lambda x: None))
    print(json.dumps(out_rules, indent=2, default=lambda x: None))
    nan = [r for v in races.values() for r in v if np.isnan(r["lap_coverage"])]
    if nan:
        print("races with no classified laps:", [(r["season"], r["round"]) for r in nan])


if __name__ == "__main__":
    main()
