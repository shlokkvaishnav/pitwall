"""Live replay: feed a past race to the engine one lap at a time, as if live, and time each update.

Usage: PYTHONPATH=src:scripts .venv/bin/python scripts/replay.py
Race: the 2026 Dutch Grand Prix (round 12, development), the car that started 5th (as the site's strategy section).
After each lap L the engine sees only laps 1 to L and updates:
- the finishing-order forecast (mean position and podium chance of every car, 500 runs from the real state);
- the pit window of the car for its next stop (candidates L + 1 to L + 30, 20 runs each, as spec 22);
- the undercut probability against the car directly ahead, if it is within 3 s (the site's model).
Pre-race inputs: simulator D (spec 21, chosen setting), tyre wear net of fuel (spec 22), pace updated with the laps
run so far (`engine.live_pace`). Display and timing only, not a result.
Writes results/replay.json (latency) and site/data/live-replay.json (the page data).
"""

from __future__ import annotations

import json
import platform
import subprocess
import time
from dataclasses import replace
from pathlib import Path

import numpy as np
from race_sim_d import Data

from pitwall.engine import live_pace, pit_window, state_at, tyre_deg, undercut_probability
from pitwall.fastsim import simulate
from pitwall.laps import lap_table
from pitwall.strategy_env import World

ROOT = Path(__file__).resolve().parents[1]
ROUND, START_SLOT = 12, 5
FORECAST_RUNS, WINDOW_RUNS, HORIZON = 500, 20, 30


def main() -> None:
    chosen = json.loads((ROOT / "results" / "21-simulator-d-dev.json").read_text())["chosen"]
    data = Data([ROUND])
    ri = data.round_inputs(ROUND)
    pre = ri.world(chosen["w"], chosen["c"])
    race = data.races[(2026, ROUND)]
    cid = ri.circuit_id
    hist = [k for k in data.stats if k[0] < 2026 or k[1] < ROUND]
    same = [k for k in hist if data.stats[k].circuit_id == cid] or hist
    degs = [d for d in (tyre_deg(data.races[k]) for k in same) if np.isfinite(d)]
    inp0 = replace(pre.inp, wear_s_per_lap=max(float(np.median(degs)), 0.0))
    stops_mode = int(np.bincount(np.asarray(inp0.stop_counts, int)).argmax())
    model = json.loads((ROOT / "site" / "data" / "undercut-model.json").read_text())
    drivers, n = inp0.drivers, inp0.laps
    car = START_SLOT - 1
    table = lap_table(race)
    real_stops = sorted(int(x) for x in race.pitstops.loc[race.pitstops["driver"] == drivers[car], "lap"].dropna())

    frames, lat = [], []
    for lap in range(1, n):
        t0 = time.perf_counter()
        state = state_at(race, drivers, lap, table)
        pace, wgt = live_pace(table, drivers, lap, inp0.pace)
        world = World(replace(inp0, pace=pace, pace_shock_s=inp0.pace_shock_s * float(np.median(wgt))), pre.hazard,
                      pre.overtake, cid)  # fmt: skip
        fc = simulate(world, FORECAST_RUNS, seed=lap, state=state).positions
        frame: dict = {"lap": lap}
        if state.alive[car]:
            extra = max(stops_mode - int(state.stops[car]) - 1, 0)
            cand = range(lap + 1, min(lap + HORIZON, n - 1) + 1)
            if len(cand) >= 3 and (state.stops[car] < stops_mode or state.age[car] > 25):
                win = pit_window(world, state, car, cand, extra, runs=WINDOW_RUNS, seed=lap)
                frame["window"] = [max(win.lo, cand[0]), min(win.hi, cand[-1])]
            order = np.argsort(np.where(state.alive, state.cum, np.inf))
            p = int(np.flatnonzero(order == car)[0])
            if p > 0:
                ahead = order[p - 1]
                gap = float(state.cum[car] - state.cum[ahead])
                if gap <= 3.0:
                    frame["undercut"] = round(
                        undercut_probability(model, gap, float(state.age[ahead] - state.age[car]), n - lap), 3
                    )
                frame["ahead"] = drivers[ahead]
            frame["position"] = p + 1
        lat.append(1000 * (time.perf_counter() - t0))
        mean_pos = fc.mean(0)
        top = np.argsort(mean_pos)[:5]
        frame["forecast"] = [
            {
                "driver": drivers[i],
                "mean": round(float(mean_pos[i]), 2),
                "podium": round(float((fc[:, i] <= 3).mean()), 3),
            }
            for i in top
        ]
        frame["car_mean"] = round(float(mean_pos[car]), 2)
        frame["ms"] = round(lat[-1], 1)
        frames.append(frame)
        print(lap, {k: v for k, v in frame.items() if k != "forecast"}, flush=True)

    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True)
    res = race.results.set_index("driver")
    summary = {
        "race": f"2026 {race.name}",
        "car": drivers[car],
        "laps": n,
        "real_stops": real_stops,
        "finish": int(res.loc[drivers[car], "position"]),
        "latency_ms": {
            "median": float(np.median(lat)),
            "p95": float(np.quantile(lat, 0.95)),
            "max": float(np.max(lat)),
        },
        "runs_per_lap": {"forecast": FORECAST_RUNS, "window": f"{WINDOW_RUNS} x up to {HORIZON} candidate laps"},
        "machine": {"platform": platform.platform(), "numpy": np.__version__},
        "commit": sha.stdout.strip(),
    }
    (ROOT / "results" / "replay.json").write_text(
        json.dumps({**summary, "lap_ms": [round(x, 1) for x in lat]}, indent=2)
    )
    page = {**summary, "frames": frames}
    page.pop("machine")
    (ROOT / "site" / "data" / "live-replay.json").write_text(json.dumps(page, separators=(",", ":")))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
