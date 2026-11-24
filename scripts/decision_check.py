"""Spec 22: does the engine's pit window contain the real stops of the top 5 finishers? 2023 to 2025 races.

Usage: PYTHONPATH=src:scripts .venv/bin/python scripts/decision_check.py [--tyres]
Writes results/22-decision-check.json; with --tyres (spec 23: wear per compound) results/23-decision-check-tyres.json.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from collections import Counter
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
from race_sim_b import history
from sc_hazard import dev_rows

from pitwall.dump import Dump
from pitwall.engine import pit_window, pit_window_tyres, state_at, tyre_deg
from pitwall.hazard import Models as HazardModels
from pitwall.hazard import race_rows
from pitwall.laps import lap_table
from pitwall.overtake import Models as OvertakeModels
from pitwall.pace import fit, qualifying_gap
from pitwall.sim import inputs_from_history
from pitwall.strategy_env import World
from pitwall.tyres import join, parse
from pitwall.tyrewear import COMPOUNDS, IDX, TyreRates

ROOT = Path(__file__).resolve().parents[1]
SEASONS = (2023, 2024, 2025)
TOP_N, HORIZON, HALF, RUNS = 5, 45, 3, 40
RUNS_TYRES = 20  # per (lap, compound) pair, spec 23
MIN_HAZARD_RACES = 5
BOOT = 10_000


def stint_lengths(race) -> dict[int, list[int]]:
    """Stint number (0 = first) -> lengths of the stints that ended in a stop, for classified cars."""
    out: dict[int, list[int]] = {}
    cls = set(race.results.loc[race.results["classified"], "driver"])
    for d, g in race.pitstops.dropna(subset=["lap"]).groupby("driver"):
        if d not in cls:
            continue
        prev = 0
        for j, lap in enumerate(sorted(int(x) for x in g["lap"])):
            out.setdefault(j, []).append(lap - prev)
            prev = lap
    return out


def mode(values: list[int]) -> int:
    return Counter(values).most_common(1)[0][0] if values else 1


def boot_ci(df: pd.DataFrame, col: str, rng: np.random.Generator) -> list[float]:
    """95% race-block bootstrap interval of the mean of `col` over decisions."""
    g = df.groupby("race")[col].agg(["sum", "count"])
    s, c = g["sum"].to_numpy(float), g["count"].to_numpy(float)
    idx = rng.integers(0, len(g), (BOOT, len(g)))
    stats = s[idx].sum(1) / c[idx].sum(1)
    return [float(np.quantile(stats, 0.025)), float(np.quantile(stats, 0.975))]


def tyre_rates(cid: int) -> TyreRates:
    """Spec 23, section 2: the circuit's rates if it had at least 2 fitted races in 2019 to 2022, else all races."""
    m = json.loads((ROOT / "results" / "23-tyre-model.json").read_text())
    r = m["circuits"].get(str(cid), m["global"])
    return TyreRates(np.array(r["deg"], float), np.array(r["offset"], float))


def tyre_laps(dump: Dump, race, s: int, k: int) -> pd.DataFrame:
    """Compound and tyre life per driver and lap (TracingInsights), or an empty frame."""
    path = ROOT / "data" / "raw" / "tracinginsights" / str(s) / f"{k:02d}.json"
    if not path.exists():
        return pd.DataFrame(columns=["driver", "lap", "compound", "life"])
    codes = {dump.driver_codes[x]: x for x in race.results["driver"] if x in dump.driver_codes.index}
    return join(race, parse(path), codes)[["driver", "lap", "compound", "life"]]


def main() -> None:
    use_tyres = "--tyres" in sys.argv
    dump = Dump(ROOT / "data" / "raw" / "jolpica-dump" / "csv")
    races, stats, rows = history(dump, [])  # 2022 to 2025
    hz = dev_rows(dump)
    pairs = pd.read_csv(ROOT / "data" / "derived" / "pair_laps.csv.gz")
    keys = sorted(stats)
    deg = {key: tyre_deg(r) for key, r in races.items()}
    recs = []
    for season in SEASONS:
        overtake = OvertakeModels(pairs[pairs["season"] < season])
        for ri, key in enumerate(k for k in keys if k[0] == season):
            t0_clock = time.time()
            s, k = key
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
            ti = tyre_laps(dump, race, s, k) if use_tyres else None
            rates = tyre_rates(cid) if use_tyres else None
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
                    state = state_at(race, inp.drivers, t0, table)
                    extra = max(n_stops - int(state.stops[car]) - 1, 0)
                    choice = None
                    if use_tyres:
                        assert ti is not None and rates is not None
                        now = ti[ti["lap"] == t0].set_index("driver").reindex(inp.drivers)
                        state.compound = now["compound"].map(IDX).fillna(1).astype(int).to_numpy()
                        state.age = np.where(now["life"].notna(), now["life"], state.age).astype(float)
                        run_ = ti[(ti["driver"] == d) & (ti["lap"] <= t0) & ti["compound"].isin(COMPOUNDS)]
                        allowed = [0, 1, 2]
                        if run_["compound"].nunique() <= 1 and extra == 0:
                            allowed.remove(int(state.compound[car]))
                        win, choice = pit_window_tyres(world, state, car, cand, rates, allowed, extra, runs=RUNS_TYRES,
                                                       seed=ri, half_width=HALF)  # fmt: skip
                    else:
                        win = pit_window(world, state, car, cand, extra, runs=RUNS, seed=ri, half_width=HALF)
                    lo, hi = cand[0], cand[-1]
                    med = lengths.get(j) or all_lengths.get(j) or [laps // (n_stops + 1)]
                    b1 = int(np.clip(t0 - 1 + np.median(med), lo, hi))
                    if j + 1 <= n_stops:
                        b2 = round((j + 1) * laps / (n_stops + 1))
                    else:
                        b2 = round(prev_stop + (laps - prev_stop) / 2)
                    b2 = int(np.clip(b2, lo, hi))
                    best = int(np.clip(win.best, lo, hi))
                    recs.append(
                        {
                            "race": f"{s}-{k:02d}",
                            "driver": d,
                            "stop": j + 1,
                            "t0": t0,
                            "real": stop,
                            "neutral_lap": bool(neutral.get(stop, False)),
                            "engine": best,
                            "b1": b1,
                            "b2": b2,
                            "in_engine": int(abs(stop - best) <= HALF),
                            "in_b1": int(abs(stop - b1) <= HALF),
                            "in_b2": int(abs(stop - b2) <= HALF),
                            **({"compound": COMPOUNDS[choice]} if choice is not None else {}),
                        }
                    )
            print(key, race.name, f"{time.time() - t0_clock:.0f} s", len(recs), flush=True)

    df = pd.DataFrame(recs)
    rng = np.random.default_rng(0)
    df["d_b1"] = df["in_engine"] - df["in_b1"]
    df["d_b2"] = df["in_engine"] - df["in_b2"]
    cols = ["in_engine", "in_b1", "in_b2", "d_b1", "d_b2"]
    if use_tyres:  # paired against the spec 22 engine on the same decisions
        old = pd.DataFrame(json.loads((ROOT / "results" / "22-decision-check.json").read_text())["decisions"])
        old = old[["race", "driver", "stop", "in_engine"]].rename(columns={"in_engine": "in_spec22"})
        df = df.merge(old, on=["race", "driver", "stop"], how="left")
        df["d_spec22"] = df["in_engine"] - df["in_spec22"]
        cols += ["in_spec22", "d_spec22"]

    def summary(part: pd.DataFrame) -> dict:
        return {
            "decisions": len(part),
            "races": int(part["race"].nunique()),
            **{c: {"rate": float(part[c].mean()), "ci95": boot_ci(part, c, rng)} for c in cols},
            "median_abs_error": {m: float((part[m] - part["real"]).abs().median()) for m in ("engine", "b1", "b2")},
        }

    allv, green = summary(df), summary(df[~df["neutral_lap"]])
    best_b = "d_b1" if allv["in_b1"]["rate"] >= allv["in_b2"]["rate"] else "d_b2"
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True)
    out = {
        "spec": "23-compound-wear" if use_tyres else "22-decision-check",
        "commit": sha.stdout.strip(),
        "settings": {
            "top_n": TOP_N,
            "horizon": HORIZON,
            "half_width": HALF,
            "runs_per_candidate": RUNS_TYRES if use_tyres else RUNS,
        },
        "all_stops": allv,
        "green_stops": green,
        ("E2" if use_tyres else "E1") + "_engine_above_best_baseline": bool(allv[best_b]["ci95"][0] > 0),
        "decisions": recs,
    }
    name = "23-decision-check-tyres.json" if use_tyres else "22-decision-check.json"
    (ROOT / "results" / name).write_text(json.dumps(out, indent=2))
    print(json.dumps({k: v for k, v in out.items() if k != "decisions"}, indent=2))


if __name__ == "__main__":
    main()
