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
from .tyrewear import NEXT, TyreRates


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


def tyre_deg(race: Race, table: pd.DataFrame | None = None) -> float:
    """Tyre wear in s per lap of tyre age, net of fuel burn: clean laps, time = driver + deg × age + fuel × lap.

    Within one stint age and lap move together; the stops reset age, which separates the two slopes. (The wear
    input of simulators A to C is the slope within stints, which includes fuel burn and is often negative.)
    """
    t = lap_table(race) if table is None else table
    from .laps import clean_mask

    c = t[clean_mask(t)]
    if c["stint"].nunique() < 2 or len(c) < 50:
        return float("nan")
    x = c[["tyre_age", "lap"]].astype(float)
    y = c["time_s"].astype(float)
    xd = (x - x.groupby(c["driver"]).transform("mean")).to_numpy()
    yd = (y - y.groupby(c["driver"]).transform("mean")).to_numpy()
    (deg, _fuel), *_ = np.linalg.lstsq(xd, yd, rcond=None)
    return float(deg)


def live_pace(
    table: pd.DataFrame, drivers: list[str], lap: int, prior: np.ndarray, prior_laps: float = 10.0
) -> tuple[np.ndarray, np.ndarray]:
    """Pre-race pace updated with the clean laps run so far (up to `lap`): a weighted mean, the prior counting as
    `prior_laps` laps. Returns the pace and the weight left on the prior (to shrink the pace shock with)."""
    from .laps import clean_mask

    t = table[(table["lap"] <= lap)]
    c = t[clean_mask(t)]
    if c.empty:
        return prior.copy(), np.ones(len(drivers))
    rel = c["time_s"] - c.groupby("lap")["time_s"].transform("median")
    g = rel.groupby(c["driver"]).agg(["sum", "count"]).reindex(drivers).fillna(0.0)
    n = g["count"].to_numpy(float)
    pace = (prior_laps * prior + g["sum"].to_numpy(float)) / (prior_laps + n)
    return pace, prior_laps / (prior_laps + n)


def undercut_probability(model: dict, gap_s: float, age_diff: float, remaining_laps: int) -> float:
    """The site's undercut model (spec 10, `site/data/undercut-model.json`): chance that a car pitting now, `gap_s`
    behind the car ahead, is ahead after both stop. `age_diff` = tyre age of the car ahead minus the car's own."""
    p = model["params"]
    x = np.array([gap_s, age_diff, np.log(max(remaining_laps, 1))])
    z = p["intercept"] + float(np.dot(p["coef"], (x - np.array(p["mean"])) / np.array(p["scale"])))
    return float(1 / (1 + np.exp(-z)))


def pit_window_tyres(
    world: World,
    state: State,
    car: int,
    candidates: range,
    tyres: TyreRates,
    compounds: list[int],
    extra_stops: int = 0,
    runs: int = 20,
    seed: int = 0,
    half_width: int = 3,
    smooth: int = 5,
) -> tuple[Window, int]:
    """Spec 23: the next stop is a pair (lap, compound). Returns the window around the best pair's lap and its
    compound. Means are smoothed over laps for each compound; extra stops fit `tyrewear.NEXT` in turn."""
    laps = np.array(list(candidates))
    width = extra_stops + 1
    plan, comp = [], []
    for c in compounds:
        chain = [c]
        for _ in range(extra_stops):
            chain.append(int(NEXT[chain[-1]]))
        for p in laps:
            plan.append(plan_from(int(p), extra_stops, world.inp.laps))
            comp.append(chain)
    plan_a = np.repeat(np.array(plan, int).reshape(-1, width), runs, axis=0)
    comp_a = np.repeat(np.array(comp, int).reshape(-1, width), runs, axis=0)
    b = simulate(world, len(plan_a), seed, state=state, ego=car, ego_plan=plan_a, tyres=tyres, ego_compounds=comp_a)
    raw = b.positions[:, car].reshape(len(compounds), len(laps), runs).mean(2)
    k = min(smooth, len(laps))
    means = np.empty_like(raw)
    for i in range(len(compounds)):
        pad = np.pad(raw[i], (k // 2, k - 1 - k // 2), mode="edge")
        means[i] = np.convolve(pad, np.ones(k) / k, mode="valid")
    ci, li = np.unravel_index(int(np.argmin(means)), means.shape)
    return Window(laps, means[ci], int(laps[li]), half_width), int(compounds[ci])
