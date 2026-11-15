"""Spec 05: test the race simulator before each race, on 2026 development rounds 4 to 12.

Usage: PYTHONPATH=src .venv/bin/python scripts/race_sim.py
Writes results/05-race-simulator.json.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from pitwall.dump import Dump
from pitwall.lapmodel import PRETRAIN_SEASONS, development_rounds
from pitwall.sim import inputs_from_history, race_stats, simulate

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    dump = Dump(ROOT / "data" / "raw" / "jolpica-dump" / "csv")
    races, stats = {}, {}
    for season in (*PRETRAIN_SEASONS, 2026):
        sched = dump.schedule(season)
        rounds = development_rounds(dump) if season == 2026 else [int(r) for r in sched["round"]]
        for rnd in rounds:
            cid = int(sched.loc[sched["round"] == rnd, "circuit_id"].iloc[0])
            race = dump.race(season, rnd)
            races[(season, rnd)] = race
            stats[(season, rnd)] = race_stats(race, cid)
    print("history ready:", len(stats), "races", flush=True)

    per_race, probs, outcomes = [], [], []
    for k in [r for r in development_rounds(dump) if r >= 4]:
        hist_keys = [key for key in stats if key[0] < 2026 or key[1] < k]
        history = [stats[key] for key in hist_keys]
        race = races[(2026, k)]
        res = race.results.copy()
        inp = inputs_from_history(history, stats[(2026, k)].circuit_id, res[["driver", "grid"]], int(res["laps"].max()))
        pos = simulate(inp, runs=2000, seed=0)
        mean_pos = pd.Series(pos.mean(0), index=inp.drivers)
        p_podium = pd.Series((pos <= 3).mean(0), index=inp.drivers)

        cls = res[res["classified"]].set_index("driver")
        grid_rank = pd.Series(np.arange(1, len(inp.drivers) + 1), index=inp.drivers)
        rho_sim = spearmanr(mean_pos[cls.index], cls["position"]).statistic
        rho_grid = spearmanr(grid_rank[cls.index], cls["position"]).statistic

        # grid baseline: podium frequency for each grid position in the history races
        hist = pd.concat([races[key].results for key in hist_keys], ignore_index=True)
        hist["podium"] = hist["classified"] & (hist["position"] <= 3)
        freq = hist[hist["grid"] > 0].groupby("grid")["podium"].mean()
        y = res.set_index("driver").reindex(inp.drivers)
        actual = (y["classified"] & (y["position"] <= 3)).astype(float).to_numpy()
        p_grid = np.array([freq.get(g, 0.0) if g > 0 else 0.0 for g in y["grid"]])
        brier_sim = float(np.mean((p_podium.to_numpy() - actual) ** 2))
        brier_grid = float(np.mean((p_grid - actual) ** 2))
        probs.extend(p_podium.tolist())
        outcomes.extend(actual.tolist())
        per_race.append(
            {
                "round": k,
                "name": race.name,
                "spearman_sim": float(rho_sim),
                "spearman_grid": float(rho_grid),
                "brier_sim": brier_sim,
                "brier_grid": brier_grid,
                "inputs": {
                    "pit_loss_s": inp.pit_loss_s,
                    "wear_s_per_lap": inp.wear_s_per_lap,
                    "sc_rate": inp.sc_rate,
                    "dnf_hazard": inp.dnf_hazard,
                    "laps": inp.laps,
                },
            }
        )
        print(json.dumps({k2: v for k2, v in per_race[-1].items() if k2 != "inputs"}), flush=True)

    probs, outcomes = np.array(probs), np.array(outcomes)
    bins = np.clip((probs * 5).astype(int), 0, 4)
    reliability = [
        {
            "bin": f"{b / 5:.1f}-{(b + 1) / 5:.1f}",
            "n": int((bins == b).sum()),
            "mean_p": float(probs[bins == b].mean()) if (bins == b).any() else None,
            "freq": float(outcomes[bins == b].mean()) if (bins == b).any() else None,
        }
        for b in range(5)
    ]
    df = pd.DataFrame(per_race)
    rules = {
        "S1_spearman_sim": float(df["spearman_sim"].mean()),
        "S1_spearman_grid": float(df["spearman_grid"].mean()),
        "S1_pass": bool(df["spearman_sim"].mean() > df["spearman_grid"].mean()),
        "S2_brier_sim": float(df["brier_sim"].mean()),
        "S2_brier_grid": float(df["brier_grid"].mean()),
        "S2_pass": bool(df["brier_sim"].mean() < df["brier_grid"].mean()),
        "S3_reliability": reliability,
    }
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True)
    out = {"spec": "05-race-simulator", "commit": sha.stdout.strip(), "rules": rules, "races": per_race}
    (ROOT / "results" / "05-race-simulator.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(rules, indent=2))


if __name__ == "__main__":
    main()
