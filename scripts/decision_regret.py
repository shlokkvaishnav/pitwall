"""Spec 24 (SIMULATED): race-time regret of the engine's pit lap, the real stop and two rules. 2023 to 2025 races.

Usage: PYTHONPATH=src:scripts .venv/bin/python scripts/decision_regret.py [--only 2024-05]
Writes results/24-decision-regret.json (`--only` writes nothing). Uses the engine's own simulator, so the numbers
say how the options compare inside the model, not in the real world.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
from decision_check import BOOT, HALF, HORIZON, MIN_HAZARD_RACES, RUNS, SEASONS, TOP_N, mode, stint_lengths
from race_sim_b import history
from sc_hazard import dev_rows

from pitwall.dump import Dump
from pitwall.engine import pit_window, plan_from, state_at, tyre_deg
from pitwall.fastsim import simulate
from pitwall.hazard import Models as HazardModels
from pitwall.hazard import race_rows
from pitwall.laps import lap_table
from pitwall.overtake import Models as OvertakeModels
from pitwall.pace import fit, qualifying_gap
from pitwall.sim import inputs_from_history
from pitwall.strategy_env import World

ROOT = Path(__file__).resolve().parents[1]
EVAL_RUNS, SMOOTH, SEED_OFFSET = 100, 5, 1000
OPTIONS = ("engine", "actual", "b2", "b1")


def smooth(raw: np.ndarray, k: int = SMOOTH) -> np.ndarray:
    k = min(k, len(raw))
    pad = np.pad(raw, (k // 2, k - 1 - k // 2), mode="edge")
    return np.convolve(pad, np.ones(k) / k, mode="valid")


def boot(df: pd.DataFrame, col: str, rng: np.random.Generator) -> list[float]:
    """95% race-block bootstrap interval of the mean of `col` over decisions."""
    g = df.groupby("race")[col].agg(["sum", "count"])
    s, c = g["sum"].to_numpy(float), g["count"].to_numpy(float)
    idx = rng.integers(0, len(g), (BOOT, len(g)))
    st = s[idx].sum(1) / c[idx].sum(1)
    return [float(np.quantile(st, 0.025)), float(np.quantile(st, 0.975))]


def main() -> None:
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    dump = Dump(ROOT / "data" / "raw" / "jolpica-dump" / "csv")
    races, stats, rows = history(dump, [])
    hz = dev_rows(dump)
    pairs = pd.read_csv(ROOT / "data" / "derived" / "pair_laps.csv.gz")
    keys = sorted(stats)
    deg = {key: tyre_deg(r) for key, r in races.items()}
    recs: list[dict] = []
    dropped = 0
    for season in SEASONS:
        overtake = OvertakeModels(pairs[pairs["season"] < season])
        for ri, key in enumerate(k for k in keys if k[0] == season):
            s, k = key
            if only and only != f"{s}-{k:02d}":
                continue
            t_start = time.time()
            before = [x for x in keys if x < key]
            hist = [stats[x] for x in before]
            race = races[key]
            res = race.results
            laps, cid = int(res["laps"].max()), stats[key].circuit_id
            base = inputs_from_history(hist, cid, res[["driver", "grid"]], laps, season=s)
            in_hist = rows["season"].lt(s) | (rows["season"].eq(s) & rows["round"].lt(k))
            pf = fit(rows[in_hist])
            q = qualifying_gap(dump.qualifying(s, k), base.drivers)
            inp = replace(base, pace=pf.predict(q, base.pace), pace_shock_s=pf.sigma_r)
            hz_b = hz[(hz["season"] < s) | ((hz["season"] == s) & (hz["round"] < k))]
            if hz_b.groupby(["season", "round"]).ngroups >= MIN_HAZARD_RACES:
                rr = race_rows({}, laps, season=s, round=k, circuit_id=cid)
                h = np.concatenate([[0.0], HazardModels(hz_b).predict(rr)["M2"]])
            else:
                h = np.full(laps + 1, inp.sc_rate / laps)
            same = [x for x in before if stats[x].circuit_id == cid] or before
            wear = [deg[x] for x in same if np.isfinite(deg[x])] or [deg[x] for x in before if np.isfinite(deg[x])]
            inp = replace(inp, wear_s_per_lap=max(float(np.median(wear)), 0.0))
            world = World(inp, h, overtake, cid)

            n_stops = mode([c for x in same for c in stats[x].stops])
            lengths: dict[int, list[int]] = {}
            for x in same:
                for j, v in stint_lengths(races[x]).items():
                    lengths.setdefault(j, []).extend(v)
            all_lengths: dict[int, list[int]] = {}
            for x in before:
                for j, v in stint_lengths(races[x]).items():
                    all_lengths.setdefault(j, []).extend(v)

            table = lap_table(race)
            neutral = table.groupby("lap")["neutral"].any().to_dict()
            top = res[res["classified"]].sort_values("position").head(TOP_N)
            pits = race.pitstops.dropna(subset=["lap"])
            for d in top["driver"]:
                car = inp.drivers.index(d)
                real = sorted(int(x) for x in pits.loc[pits["driver"] == d, "lap"])
                prev = 0
                for j, stop in enumerate(real):
                    t0 = max(prev + 1, 1)
                    prev_stop, prev = prev, stop
                    if stop <= t0:
                        continue
                    cand = range(t0 + 1, min(t0 + HORIZON, laps - 1) + 1)
                    if len(cand) == 0:
                        continue
                    if stop > cand[-1]:
                        dropped += 1
                        continue
                    state = state_at(race, inp.drivers, t0, table)
                    extra = max(n_stops - int(state.stops[car]) - 1, 0)
                    win = pit_window(world, state, car, cand, extra, runs=RUNS, seed=ri, half_width=HALF)
                    lo, hi = cand[0], cand[-1]
                    med = lengths.get(j) or all_lengths.get(j) or [laps // (n_stops + 1)]
                    b1 = int(np.clip(t0 - 1 + np.median(med), lo, hi))
                    if j + 1 <= n_stops:
                        b2 = round((j + 1) * laps / (n_stops + 1))
                    else:
                        b2 = round(prev_stop + (laps - prev_stop) / 2)
                    lap_of = {
                        "engine": int(np.clip(win.best, lo, hi)),
                        "actual": stop,
                        "b2": int(np.clip(b2, lo, hi)),
                        "b1": b1,
                    }
                    # scoring batch: another seed, no retirements, metric = the car's simulated race time
                    grid = np.array(list(cand))
                    plans = np.array([plan_from(int(p), extra, laps) for p in grid])
                    b = simulate(world, EVAL_RUNS * len(grid), ri + SEED_OFFSET, state=state, ego=car,
                                 ego_plan=np.repeat(plans, EVAL_RUNS, axis=0), retirements=False)  # fmt: skip
                    assert b.time is not None
                    t = smooth(b.time[:, car].reshape(len(grid), EVAL_RUNS).mean(1))
                    rec: dict = {
                        "race": f"{s}-{k:02d}", "driver": d, "stop": j + 1, "t0": t0,
                        "neutral_lap": bool(neutral.get(stop, False)),
                        "grid_best_lap": int(grid[int(np.argmin(t))]),
                        "actual_rank": int((t < t[stop - lo]).sum()) + 1, "grid_size": len(grid),
                    }  # fmt: skip
                    for o in OPTIONS:
                        rec[f"{o}_lap"] = lap_of[o]
                        rec[f"{o}_time"] = float(t[lap_of[o] - lo])
                        rec[f"{o}_regret"] = float(t[lap_of[o] - lo] - t.min())
                    for o in OPTIONS[1:]:
                        rec[f"d_{o}"] = rec[f"{o}_time"] - rec["engine_time"]
                    recs.append(rec)
            print(key, race.name, f"{time.time() - t_start:.0f} s", len(recs), flush=True)

    df = pd.DataFrame(recs)
    rng = np.random.default_rng(0)
    cols = [f"{o}_regret" for o in OPTIONS] + [f"d_{o}" for o in OPTIONS[1:]]

    def summary(part: pd.DataFrame) -> dict:
        out = {"decisions": len(part), "races": int(part["race"].nunique())}
        out.update({c: {"mean": float(part[c].mean()), "ci95": boot(part, c, rng)} for c in cols})
        for o in OPTIONS[1:]:
            out[f"engine_regret_below_{o}"] = float((part["engine_regret"] < part[f"{o}_regret"]).mean())
        out["median_regret"] = {o: float(part[f"{o}_regret"].median()) for o in OPTIONS}
        return out

    if only:
        print(json.dumps(summary(df), indent=2))
        return
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True)
    out = {
        "spec": "24-simulated-regret",
        "label": "SIMULATED: scored with the engine's own model; not independent evidence of real-world gains",
        "commit": sha.stdout.strip(),
        "settings": {"top_n": TOP_N, "horizon": HORIZON, "engine_runs": RUNS, "eval_runs_per_lap": EVAL_RUNS,
                     "smooth": SMOOTH, "eval_seed_offset": SEED_OFFSET, "bootstrap": BOOT},  # fmt: skip
        "dropped_real_stop_outside_grid": dropped,
        "all_stops": summary(df),
        "green_stops": summary(df[~df["neutral_lap"]]),
        "neutral_stops": summary(df[df["neutral_lap"]]),
        "decisions": recs,
    }
    (ROOT / "results" / "24-decision-regret.json").write_text(json.dumps(out, indent=2))
    print(json.dumps({k: v for k, v in out.items() if k != "decisions"}, indent=2))


if __name__ == "__main__":
    main()
