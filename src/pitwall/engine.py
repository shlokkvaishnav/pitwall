"""Strategy engine: from a race in progress, simulate the rest of it and pick the pit lap (fast simulator).

Point in time: `state_at` reads only laps up to and including the decision lap.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .data import Race
from .fastsim import NO_LAP, State, simulate
from .laps import lap_table
from .strategy_env import World


def state_at(race: Race, drivers: list[str], lap: int, table: pd.DataFrame | None = None) -> State:
    """The real race at the end of `lap`, for the cars in `drivers` (World order). Uses no later lap."""
    t = lap_table(race) if table is None else table
    t = t[t["lap"] <= lap]
    wide = t.pivot(index="lap", columns="driver", values="time_s").reindex(index=range(1, lap + 1), columns=drivers)
    have = wide.notna().to_numpy()
    done = np.cumprod(have, axis=0).sum(0)  # laps completed in a row from lap 1
    cum_all = np.nancumsum(np.where(have, wide.to_numpy(float), 0.0), axis=0)
    cum = np.array([cum_all[k - 1, i] if k > 0 else 0.0 for i, k in enumerate(done)])
    last = t[t["lap"] == lap].set_index("driver")
    age = last["tyre_age"].reindex(drivers).fillna(1).to_numpy(float)
    pits = race.pitstops.dropna(subset=["lap"])
    stops = np.array([int(((pits["driver"] == d) & (pits["lap"] <= lap)).sum()) for d in drivers])
    return State(lap=lap, cum=cum, age=age, stops=stops, alive=done == lap, laps_done=done.astype(int))


def plan_from(p: int, extra: int, laps: int) -> list[int]:
    """Pit on lap `p`, then `extra` more stops spread evenly over the rest of the race."""
    return [p] + [int(p + round(j * (laps - p) / (extra + 1))) for j in range(1, extra + 1)]


@dataclass
class Window:
    laps: np.ndarray  # candidate laps for the next stop
    mean_pos: np.ndarray  # mean finishing position of the car for each candidate
    best: int
    half_width: int

    @property
    def lo(self) -> int:
        return self.best - self.half_width

    @property
    def hi(self) -> int:
        return self.best + self.half_width

    def contains(self, lap: int) -> bool:
        return self.lo <= lap <= self.hi


def pit_window(
    world: World,
    state: State,
    car: int,
    candidates: range,
    extra_stops: int = 0,
    runs: int = 40,
    seed: int = 0,
    half_width: int = 3,
    smooth: int = 5,
) -> Window:
    """For each candidate lap, the car's mean finishing position if it stops then (and `extra_stops` more later).

    One batch: `runs` races per candidate. The means are smoothed with a centred moving average over `smooth`
    candidate laps; the best lap is the lowest smoothed mean (the earliest on a tie), the window best ± `half_width`.
    """
    laps = np.array(list(candidates))
    plans = [plan_from(int(p), extra_stops, world.inp.laps) for p in laps]
    width = max(len(p) for p in plans)
    plan = np.full((len(laps), width), NO_LAP)
    for i, p in enumerate(plans):
        plan[i, : len(p)] = p
    b = simulate(world, runs * len(laps), seed, state=state, ego=car, ego_plan=np.repeat(plan, runs, axis=0))
    raw = b.positions[:, car].reshape(len(laps), runs).mean(1)
    k = min(smooth, len(laps))
    pad = np.pad(raw, (k // 2, k - 1 - k // 2), mode="edge")
    means = np.convolve(pad, np.ones(k) / k, mode="valid")
    best = int(laps[int(np.argmin(means))])
    return Window(laps, means, best, half_width)
