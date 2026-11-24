"""Speed of the fast simulator against the one-race-at-a-time simulator C, on the same three race inputs.

Usage: PYTHONPATH=src:scripts .venv/bin/python scripts/bench_sim.py
Writes results/bench-sim.json. Times depend on the machine (recorded in the file). The inputs are the spec 18 worlds
(2026 rounds 4, 8 and 12, development races). Both simulators run every car on its plan, with retirements.
"""

from __future__ import annotations

import json
import platform
import subprocess
import time
from pathlib import Path

import numpy as np
from race_sim_c import simulate_c
from rl_strategy import build_worlds

from pitwall.dump import Dump
from pitwall.fastsim import simulate

ROOT = Path(__file__).resolve().parents[1]
OLD_RUNS, NEW_RUNS = 200, 2000
CHECK_OLD, CHECK_NEW = 400, 4000


def main() -> None:
    worlds = build_worlds(Dump(ROOT / "data" / "raw" / "jolpica-dump" / "csv"))
    recs = []
    for k, w in worlds.items():
        t0 = time.perf_counter()
        simulate_c(w, OLD_RUNS, seed=1)
        old_s = time.perf_counter() - t0
        t0 = time.perf_counter()
        simulate(w, NEW_RUNS, seed=1)
        cold_s = time.perf_counter() - t0  # first call: the tree memo is empty
        t0 = time.perf_counter()
        simulate(w, NEW_RUNS, seed=2)
        warm_s = time.perf_counter() - t0
        rec = {
            "round": k,
            "laps": w.inp.laps,
            "cars": len(w.inp.drivers),
            "old_races_per_s": OLD_RUNS / old_s,
            "new_races_per_s_first_call": NEW_RUNS / cold_s,
            "new_races_per_s": NEW_RUNS / warm_s,
            "new_ms_per_2000_races": 1000 * warm_s,
        }
        recs.append(rec)
        print({a: round(b, 1) for a, b in rec.items()}, flush=True)

    # same distribution on real inputs: mean finishing position per car, old against new
    w = worlds[4]
    old = simulate_c(w, CHECK_OLD, seed=3)
    new = simulate(w, CHECK_NEW, seed=3).positions
    se = np.sqrt(old.var(0) / len(old) + new.var(0) / len(new))
    z = (old.mean(0) - new.mean(0)) / np.maximum(se, 1e-9)
    others = np.arange(len(z)) != w.ego
    check = {
        "round": 4,
        "old_runs": CHECK_OLD,
        "new_runs": CHECK_NEW,
        "max_abs_z_other_cars": float(np.abs(z[others]).max()),
        "z_ego_car": float(z[w.ego]),
        "max_abs_diff_podium_chance": float(np.abs((old <= 3).mean(0) - (new <= 3).mean(0)).max()),
        "note": "In simulator C the ego car decides before the lap's safety-car draw (one lap later than the others); "
        "the fast simulator treats it like every other car.",
    }
    speed = float(np.mean([r["new_races_per_s"] for r in recs]) / np.mean([r["old_races_per_s"] for r in recs]))
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True)
    out = {
        "commit": sha.stdout.strip(),
        "machine": {"platform": platform.platform(), "processor": platform.processor(), "numpy": np.__version__},
        "speedup_mean": speed,
        "races": recs,
        "same_distribution": check,
    }
    (ROOT / "results" / "bench-sim.json").write_text(json.dumps(out, indent=2))
    print(json.dumps({"speedup_mean": speed, "same_distribution": check}, indent=2))


if __name__ == "__main__":
    main()
