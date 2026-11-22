"""Spec 20: simulator C (spec 15 hazard + spec 16 overtaking + pit reaction) against simulator B and the grid.

Usage: PYTHONPATH=src:scripts .venv/bin/python scripts/race_sim_c.py   (development: 2026 rounds 4 to 12)
Writes results/20-simulator-c-dev.json. The test on rounds 19 to 23 is added with spec 13 in December.
"""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
from race_sim_b import evaluate, history, score
from sc_hazard import dev_rows

from pitwall.dump import Dump
from pitwall.hazard import Models as HazardModels
from pitwall.hazard import race_rows
from pitwall.overtake import Models as OvertakeModels
from pitwall.pace import fit, qualifying_gap
from pitwall.sim import inputs_from_history
from pitwall.strategy_env import Race, World, history_policy

ROOT = Path(__file__).resolve().parents[1]
ROUNDS = list(range(4, 13))
RUNS = 2000


def simulate_c(world: World, runs: int, seed: int = 0) -> np.ndarray:
    """Finishing positions (runs, D) with every car on its plan (the ego car too)."""
    out = np.empty((runs, len(world.inp.drivers)), int)
    for i in range(runs):
        r = Race(world, seed * 1_000_000 + i, retirements=True)
        while not r.done():
            r.step(history_policy(r))
        out[i] = r.finish_positions()
    return out


def main() -> None:
    dump = Dump(ROOT / "data" / "raw" / "jolpica-dump" / "csv")
    races, stats, rows = history(dump, list(range(1, 13)))
    hz = dev_rows(dump)
    pairs = pd.read_csv(ROOT / "data" / "derived" / "pair_laps.csv.gz")
    recs = []
    for k in ROUNDS:
        t0 = time.time()
        before_hz = (hz["season"] < 2026) | (hz["round"] < k)
        before_pairs = (pairs["season"] < 2026) | (pairs["round"] < k)
        hazard, overtake = HazardModels(hz[before_hz]), OvertakeModels(pairs[before_pairs])
        rec, _ = evaluate(dump, races, stats, rows, k)  # simulator B and the grid, spec 06 code
        hist_keys = [key for key in stats if key[0] < 2026 or key[1] < k]
        pf = fit(rows[rows["season"].lt(2026) | rows["round"].lt(k)])
        res = races[(2026, k)].results
        laps = int(res["laps"].max())
        cid = stats[(2026, k)].circuit_id
        base = inputs_from_history([stats[x] for x in hist_keys], cid, res[["driver", "grid"]], laps)
        q = qualifying_gap(dump.qualifying(2026, k), base.drivers)
        inp = replace(base, pace=pf.predict(q, base.pace), pace_shock_s=pf.sigma_r)
        h = np.concatenate([[0.0], hazard.predict(race_rows({}, laps, season=2026, round=k, circuit_id=cid))["M2"]])
        world = World(inp, h, overtake, cid)
        hist = pd.concat([races[key].results for key in hist_keys], ignore_index=True)
        hist["podium"] = hist["classified"] & (hist["position"] <= 3)
        freq = hist[hist["grid"] > 0].groupby("grid")["podium"].mean()
        y = res.set_index("driver").reindex(inp.drivers)
        p_grid = np.array([freq.get(g, 0.0) if g > 0 else 0.0 for g in y["grid"]])
        s = score(simulate_c(world, RUNS), inp.drivers, res, p_grid)
        recs.append(
            {
                "round": k,
                "name": rec["name"],
                "spearman_C": s["spearman"],
                "brier_C": s["brier"],
                "spearman_B": rec["spearman_B"],
                "brier_B": rec["brier_B"],
                "spearman_grid": rec["spearman_grid"],
                "brier_grid": rec["brier_grid"],
            }
        )
        print(
            {k2: (round(v, 4) if isinstance(v, float) else v) for k2, v in recs[-1].items()},
            f"{time.time() - t0:.0f} s",
            flush=True,
        )
    df = pd.DataFrame(recs)
    means = {c: float(df[c].mean()) for c in df.columns if c.startswith(("spearman", "brier"))}
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    out = {
        "spec": "20-simulator-c",
        "section": "4 development",
        "commit": sha,
        "runs": RUNS,
        "means": means,
        "races": recs,
    }
    (ROOT / "results" / "20-simulator-c-dev.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(means, indent=2))


if __name__ == "__main__":
    main()
