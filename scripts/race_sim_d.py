"""Spec 21: simulator D (grid prior, lap noise from past races) against the grid and simulator C.

Usage: PYTHONPATH=src:scripts .venv/bin/python scripts/race_sim_d.py          (development: 2026 rounds 4 to 12)
       PYTHONPATH=src:scripts .venv/bin/python scripts/race_sim_d.py --test   (once, rounds 19 to 23; spec 21 s. 5)
Writes results/21-simulator-d-dev.json or results/21-simulator-d-test.json.
"""

from __future__ import annotations

import itertools
import json
import subprocess
import sys
import time
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from race_sim_b import history, score
from race_sim_c import simulate_c
from sc_hazard import dev_rows

from pitwall.dump import Dump
from pitwall.fastsim import simulate
from pitwall.hazard import Models as HazardModels
from pitwall.hazard import race_rows
from pitwall.laps import clean_mask, lap_table
from pitwall.overtake import Models as OvertakeModels
from pitwall.pace import MIN_CLEAN_LAPS, fit, qualifying_gap
from pitwall.sim import SimInputs, inputs_from_history
from pitwall.strategy_env import World

ROOT = Path(__file__).resolve().parents[1]
DEV_ROUNDS = list(range(4, 13))
TEST_ROUNDS = list(range(19, 24))
W_GRID = (0.0, 0.25, 0.5, 0.75, 1.0)
C_SHOCK = (0.5, 0.75, 1.0, 1.5, 2.0)
TUNE_RUNS, FINAL_RUNS = 1000, 2000
MIN_STINT_LAPS = 6


def lap_noise(race) -> float:
    """Robust SD of clean-lap residuals around a straight line per driver stint (spec 21, section 2)."""
    t = lap_table(race)
    t = t[clean_mask(t)]
    res = []
    for _, g in t.groupby(["driver", "stint"]):
        if len(g) >= MIN_STINT_LAPS:
            x, y = g["lap"].to_numpy(float), g["time_s"].to_numpy(float)
            res.append(y - np.polyval(np.polyfit(x, y, 1), x))
    r = np.concatenate(res) if res else np.zeros(1)
    return float(1.4826 * np.median(np.abs(r - np.median(r))))


def grid_slots(results: pd.DataFrame) -> pd.Series:
    """Driver -> slot 1..D in the order `inputs_from_history` uses (pit lane and unknown last)."""
    order = np.where(results["grid"] > 0, results["grid"], 100 + np.arange(len(results)))
    ranked = results.assign(order=order).sort_values("order")["driver"].tolist()
    return pd.Series(np.arange(1, len(ranked) + 1), index=ranked)


@dataclass
class RoundInputs:
    base: SimInputs  # simulator B inputs (spec 06): pace_B and sigma_r
    sigma_r: float
    grid_pace: np.ndarray  # g(s) for the cars in grid order
    noise_s: float
    hazard: np.ndarray
    overtake: OvertakeModels
    circuit_id: int
    p_grid: np.ndarray
    results: pd.DataFrame

    def world(self, w: float, c: float) -> World:
        inp = replace(
            self.base,
            pace=(1 - w) * self.base.pace + w * self.grid_pace,
            pace_shock_s=c * self.sigma_r,
            noise_s=self.noise_s,
        )
        return World(inp, self.hazard, self.overtake, self.circuit_id)

    def world_c(self) -> World:
        return World(self.base, self.hazard, self.overtake, self.circuit_id)


class Data:
    def __init__(self, rounds: list[int], allow_holdout: bool = False):
        self.allow = allow_holdout
        self.dump = Dump(ROOT / "data" / "raw" / "jolpica-dump" / "csv")
        self.races, self.stats, rows = history(self.dump, list(range(1, max(rounds) + 1)), allow_holdout)
        slots = pd.concat(
            [
                grid_slots(r.results).rename("slot").to_frame().assign(season=s, round=k)
                for (s, k), r in self.races.items()
            ]
        )
        self.rows = rows.merge(slots.rename_axis("driver").reset_index(), on=["season", "round", "driver"], how="left")
        self.noise = {key: lap_noise(r) for key, r in self.races.items()}
        self.hz = dev_rows(self.dump)
        self.pairs = pd.read_csv(ROOT / "data" / "derived" / "pair_laps.csv.gz")

    def round_inputs(self, k: int) -> RoundInputs:
        before = (self.rows["season"] < 2026) | (self.rows["round"] < k)
        hist_keys = [key for key in self.stats if key[0] < 2026 or key[1] < k]
        pf = fit(self.rows[before])
        res = self.races[(2026, k)].results
        laps, cid = int(res["laps"].max()), self.stats[(2026, k)].circuit_id
        base = inputs_from_history([self.stats[x] for x in hist_keys], cid, res[["driver", "grid"]], laps)
        q = qualifying_gap(self.dump.qualifying(2026, k, allow_holdout=self.allow), base.drivers)
        base = replace(base, pace=pf.predict(q, base.pace), pace_shock_s=pf.sigma_r)

        r = self.rows[before & (self.rows["clean_laps"] >= MIN_CLEAN_LAPS) & self.rows["pace"].notna()]
        r = r[r["slot"].notna()]
        x = np.column_stack([np.ones(len(r)), np.log(r["slot"].to_numpy(float))])
        (a, b), *_ = np.linalg.lstsq(x, r["pace"].to_numpy(float), rcond=None)
        grid_pace = a + b * np.log(np.arange(1, len(base.drivers) + 1))

        hz_before = (self.hz["season"] < 2026) | (self.hz["round"] < k)
        p_before = (self.pairs["season"] < 2026) | (self.pairs["round"] < k)
        hazard_m, overtake = HazardModels(self.hz[hz_before]), OvertakeModels(self.pairs[p_before])
        h = np.concatenate([[0.0], hazard_m.predict(race_rows({}, laps, season=2026, round=k, circuit_id=cid))["M2"]])

        hist = pd.concat([self.races[key].results for key in hist_keys], ignore_index=True)
        hist["podium"] = hist["classified"] & (hist["position"] <= 3)
        freq = hist[hist["grid"] > 0].groupby("grid")["podium"].mean()
        y = res.set_index("driver").reindex(base.drivers)
        p_grid = np.array([freq.get(g, 0.0) if g > 0 else 0.0 for g in y["grid"]])
        noise = float(np.median([self.noise[key] for key in hist_keys]))
        return RoundInputs(base, pf.sigma_r, grid_pace, noise, h, overtake, cid, p_grid, res)


def grid_score(ri: RoundInputs) -> dict:
    from scipy.stats import spearmanr

    res = ri.results
    y = res.set_index("driver").reindex(ri.base.drivers)
    actual = (y["classified"] & (y["position"] <= 3)).astype(float).to_numpy()
    cls = res[res["classified"]].set_index("driver")
    rank = pd.Series(np.arange(1, len(ri.base.drivers) + 1), index=ri.base.drivers)
    return {
        "spearman": float(spearmanr(rank[cls.index], cls["position"]).statistic),
        "brier": float(np.mean((ri.p_grid - actual) ** 2)),
    }


def sha() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


def dev() -> None:
    data = Data(DEV_ROUNDS)
    settings = list(itertools.product(W_GRID, C_SHOCK))
    table, per_round = [], []
    for k in DEV_ROUNDS:
        t0 = time.time()
        ri = data.round_inputs(k)
        for w, c in settings:
            s = score(simulate(ri.world(w, c), TUNE_RUNS, seed=0).positions, ri.base.drivers, ri.results, ri.p_grid)
            table.append({"round": k, "w": w, "c": c, "brier": s["brier"], "spearman": s["spearman"]})
        g = grid_score(ri)
        per_round.append({"round": k, "name": data.races[(2026, k)].name, "noise_s": ri.noise_s,
                          "sigma_r": ri.sigma_r, "brier_grid": g["brier"], "spearman_grid": g["spearman"]})  # fmt: skip
        print(k, f"{time.time() - t0:.0f} s", per_round[-1], flush=True)
    tab = pd.DataFrame(table)
    mean = tab.groupby(["w", "c"])[["brier", "spearman"]].mean().reset_index()
    best = mean.loc[mean["brier"].idxmin()]
    w_best, c_best = float(best["w"]), float(best["c"])

    loro = []
    for k in DEV_ROUNDS:
        m = tab[tab["round"] != k].groupby(["w", "c"])["brier"].mean()
        w, c = m.idxmin()
        row = tab[(tab["round"] == k) & (tab["w"] == w) & (tab["c"] == c)].iloc[0]
        loro.append({"round": k, "w": float(w), "c": float(c), "brier": float(row["brier"])})

    for rec in per_round:
        ri = data.round_inputs(rec["round"])
        s = score(simulate(ri.world(w_best, c_best), FINAL_RUNS, seed=0).positions, ri.base.drivers, ri.results,
                  ri.p_grid)  # fmt: skip
        rec["brier_D"], rec["spearman_D"] = s["brier"], s["spearman"]
    c_file = json.loads((ROOT / "results" / "20-simulator-c-dev.json").read_text())
    df = pd.DataFrame(per_round)
    out = {
        "spec": "21-simulator-d",
        "section": "3 development",
        "commit": sha(),
        "chosen": {"w": w_best, "c": c_best},
        "means": {
            "brier_D_tuned": float(df["brier_D"].mean()),
            "spearman_D_tuned": float(df["spearman_D"].mean()),
            "brier_D_leave_one_round_out": float(np.mean([r["brier"] for r in loro])),
            "brier_grid": float(df["brier_grid"].mean()),
            "spearman_grid": float(df["spearman_grid"].mean()),
            "brier_C": c_file["means"]["brier_C"],
            "spearman_C": c_file["means"]["spearman_C"],
        },
        "leave_one_round_out": loro,
        "settings": mean.to_dict(orient="records"),
        "races": per_round,
        "runs": {"tuning": TUNE_RUNS, "final": FINAL_RUNS, "seed": 0},
    }
    (ROOT / "results" / "21-simulator-d-dev.json").write_text(json.dumps(out, indent=2))
    print(json.dumps({"chosen": out["chosen"], "means": out["means"]}, indent=2))


def test() -> None:
    """Spec 21, section 5: once, on rounds 19 to 23, with the setting recorded by the development run."""
    out_path = ROOT / "results" / "21-simulator-d-test.json"
    if out_path.exists():
        raise SystemExit("the test has been run; spec 21 allows one run")
    if date.today() <= date(2026, 12, 6):
        raise SystemExit("rounds 19 to 23 are not all run yet (last race 6 December 2026)")
    chosen = json.loads((ROOT / "results" / "21-simulator-d-dev.json").read_text())["chosen"]
    data = Data(TEST_ROUNDS, allow_holdout=True)
    recs = []
    for k in TEST_ROUNDS:
        ri = data.round_inputs(k)
        d = score(simulate(ri.world(chosen["w"], chosen["c"]), FINAL_RUNS, seed=0).positions, ri.base.drivers,
                  ri.results, ri.p_grid)  # fmt: skip
        c = score(simulate_c(ri.world_c(), FINAL_RUNS, seed=0), ri.base.drivers, ri.results, ri.p_grid)
        g = grid_score(ri)
        recs.append({"round": k, "name": data.races[(2026, k)].name, "brier_D": d["brier"], "spearman_D": d["spearman"],
                     "brier_C": c["brier"], "spearman_C": c["spearman"], "brier_grid": g["brier"],
                     "spearman_grid": g["spearman"]})  # fmt: skip
        print(recs[-1], flush=True)
    df = pd.DataFrame(recs)
    m = {col: float(df[col].mean()) for col in df.columns if col.startswith(("brier", "spearman"))}
    rules = {
        "D1_pass": bool(m["brier_D"] < m["brier_grid"]),
        "D2_pass": bool(m["brier_D"] < m["brier_C"]),
        "D3_pass": bool(m["spearman_D"] >= m["spearman_grid"]),
        "brier_gain_vs_grid": 1 - m["brier_D"] / m["brier_grid"],
    }
    out = {"spec": "21-simulator-d", "section": "5 test", "commit": sha(), "chosen": chosen, "means": m,
           "rules": rules, "races": recs}  # fmt: skip
    out_path.write_text(json.dumps(out, indent=2))
    print(json.dumps({"means": m, "rules": rules}, indent=2))


if __name__ == "__main__":
    test() if "--test" in sys.argv else dev()
