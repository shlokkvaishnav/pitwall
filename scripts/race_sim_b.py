"""Spec 06: test race simulator version B before each race, on 2026 development rounds 4 to 12.

Usage: PYTHONPATH=src .venv/bin/python scripts/race_sim_b.py
Writes results/06-race-simulator-b.json.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from pitwall.dump import Dump
from pitwall.lapmodel import PRETRAIN_SEASONS, development_rounds
from pitwall.pace import fit, form, qualifying_gap
from pitwall.sim import inputs_from_history, race_stats, simulate

ROOT = Path(__file__).resolve().parents[1]
VARIANTS = ("B", "ablation_a_no_shock", "ablation_b_form_with_shock")


def score(pos, drivers, res, p_grid):
    mean_pos = pd.Series(pos.mean(0), index=drivers)
    p_podium = pd.Series((pos <= 3).mean(0), index=drivers)
    cls = res[res["classified"]].set_index("driver")
    y = res.set_index("driver").reindex(drivers)
    actual = (y["classified"] & (y["position"] <= 3)).astype(float).to_numpy()
    return {
        "spearman": float(spearmanr(mean_pos[cls.index], cls["position"]).statistic),
        "brier": float(np.mean((p_podium.to_numpy() - actual) ** 2)),
        "p": p_podium.to_numpy(),
        "y": actual,
    }


def main() -> None:
    dump = Dump(ROOT / "data" / "raw" / "jolpica-dump" / "csv")
    races, stats, rows = {}, {}, []
    for season in (*PRETRAIN_SEASONS, 2026):
        sched = dump.schedule(season)
        rounds = development_rounds(dump) if season == 2026 else [int(r) for r in sched["round"]]
        earlier = []
        for rnd in rounds:
            cid = int(sched.loc[sched["round"] == rnd, "circuit_id"].iloc[0])
            race = dump.race(season, rnd)
            st = race_stats(race, cid)
            races[(season, rnd)], stats[(season, rnd)] = race, st
            drivers = list(st.pace)
            q = qualifying_gap(dump.qualifying(season, rnd), drivers)
            f = form(earlier, drivers)
            for d, qi, fi in zip(drivers, q, f):
                rows.append(
                    {
                        "season": season,
                        "round": rnd,
                        "driver": d,
                        "q": qi,
                        "f": fi,
                        "pace": st.pace[d],
                        "clean_laps": st.clean_laps.get(d, 0),
                    }
                )
            earlier.append(st.pace)
    rows = pd.DataFrame(rows)
    print("history ready:", len(stats), "races,", len(rows), "driver rows", flush=True)

    per_race, pooled = [], {v: ([], []) for v in VARIANTS}
    for k in [r for r in development_rounds(dump) if r >= 4]:
        hist_keys = [key for key in stats if key[0] < 2026 or key[1] < k]
        history = [stats[key] for key in hist_keys]
        in_hist = rows["season"].lt(2026) | rows["round"].lt(k)
        pf = fit(rows[in_hist])

        race = races[(2026, k)]
        res = race.results.copy()
        base = inputs_from_history(
            history, stats[(2026, k)].circuit_id, res[["driver", "grid"]], int(res["laps"].max())
        )
        q = qualifying_gap(dump.qualifying(2026, k), base.drivers)
        f = base.pace  # the version A pace is the season form
        inputs = {
            "B": replace(base, pace=pf.predict(q, f), pace_shock_s=pf.sigma_r),
            "ablation_a_no_shock": replace(base, pace=pf.predict(q, f)),
            "ablation_b_form_with_shock": replace(base, pace_shock_s=pf.sigma_r),
        }

        hist = pd.concat([races[key].results for key in hist_keys], ignore_index=True)
        hist["podium"] = hist["classified"] & (hist["position"] <= 3)
        freq = hist[hist["grid"] > 0].groupby("grid")["podium"].mean()
        y = res.set_index("driver").reindex(base.drivers)
        p_grid = np.array([freq.get(g, 0.0) if g > 0 else 0.0 for g in y["grid"]])
        actual = (y["classified"] & (y["position"] <= 3)).astype(float).to_numpy()
        cls = res[res["classified"]].set_index("driver")
        grid_rank = pd.Series(np.arange(1, len(base.drivers) + 1), index=base.drivers)

        rec = {
            "round": k,
            "name": race.name,
            "beta_q": pf.beta_q,
            "beta_f": pf.beta_f,
            "sigma_r": pf.sigma_r,
            "fit_rows": pf.n,
            "spearman_grid": float(spearmanr(grid_rank[cls.index], cls["position"]).statistic),
            "brier_grid": float(np.mean((p_grid - actual) ** 2)),
        }
        for v, inp in inputs.items():
            s = score(simulate(inp, runs=2000, seed=0), inp.drivers, res, p_grid)
            rec[f"spearman_{v}"], rec[f"brier_{v}"] = s["spearman"], s["brier"]
            pooled[v][0].extend(s["p"].tolist())
            pooled[v][1].extend(s["y"].tolist())
        per_race.append(rec)
        print(json.dumps(rec), flush=True)

    df = pd.DataFrame(per_race)

    def reliability(v):
        p, o = np.array(pooled[v][0]), np.array(pooled[v][1])
        bins = np.clip((p * 5).astype(int), 0, 4)
        return [
            {
                "bin": f"{b / 5:.1f}-{(b + 1) / 5:.1f}",
                "n": int((bins == b).sum()),
                "mean_p": float(p[bins == b].mean()) if (bins == b).any() else None,
                "freq": float(o[bins == b].mean()) if (bins == b).any() else None,
            }
            for b in range(5)
        ]

    rules = {
        "S1_spearman_B": float(df["spearman_B"].mean()),
        "S1_spearman_grid": float(df["spearman_grid"].mean()),
        "S1_pass": bool(df["spearman_B"].mean() > df["spearman_grid"].mean()),
        "S2_brier_B": float(df["brier_B"].mean()),
        "S2_brier_grid": float(df["brier_grid"].mean()),
        "S2_pass": bool(df["brier_B"].mean() < df["brier_grid"].mean()),
        "S3_reliability_B": reliability("B"),
    }
    ablations = {
        v: {"spearman": float(df[f"spearman_{v}"].mean()), "brier": float(df[f"brier_{v}"].mean())}
        for v in VARIANTS[1:]
    }
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True)
    out = {
        "spec": "06-race-simulator-b",
        "commit": sha.stdout.strip(),
        "rules": rules,
        "ablations": ablations,
        "races": per_race,
    }
    (ROOT / "results" / "06-race-simulator-b.json").write_text(json.dumps(out, indent=2))
    print(json.dumps({"rules": rules, "ablations": ablations}, indent=2))


if __name__ == "__main__":
    main()
