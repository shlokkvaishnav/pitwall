"""Simulator C with every run of a batch in one set of numpy arrays (the same race model as `strategy_env.Race`).

`strategy_env.Race` plays one race at a time in Python. Here the runs are the first axis of every array, so one lap
of 2,000 races is a few numpy calls. The random numbers are drawn in a different order, so a seed gives a different
race than in `Race`, but the same distribution (tests/test_fastsim.py).

Two additions for the strategy engine:
- `State`: start from a race in progress (the real race up to some lap) instead of the grid;
- `ego_plan`: the pit laps of one car, fixed by the caller (all other cars follow their plans).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .sim import SC_GAP_S, START_GAP_S, STUCK_GAP_S
from .strategy_env import MAX_GAP_S, REACT_LAPS, SC_PACE, SC_PIT_FACTOR, World

BASE_S = 90.0
NO_LAP = 10_000  # a plan slot with no stop


@dataclass
class State:
    """A race at the end of lap `lap`. Arrays are per car, in the order of `World.inp.drivers`."""

    lap: int
    cum: np.ndarray  # race time so far, s
    age: np.ndarray  # laps on the current tyres
    stops: np.ndarray  # stops made
    alive: np.ndarray  # still running
    sc_left: int = 0  # laps left in a neutral period
    laps_done: np.ndarray | None = None  # laps completed (for cars out of the race); `lap` for all if None


def start_state(world: World, rng: np.random.Generator, runs: int) -> tuple[np.ndarray, ...]:
    """The state after lap 1, as in `Race.__init__`: (cum, age, stops, alive) with shape (runs, D)."""
    d, noise = len(world.inp.drivers), world.inp.noise_s
    cum = np.arange(d) * START_GAP_S + rng.normal(0, 2 * noise, (runs, d))
    return cum, np.ones((runs, d)), np.zeros((runs, d), int), np.ones((runs, d), bool)


def sample_plans(world: World, rng: np.random.Generator, runs: int, state: State | None = None) -> np.ndarray:
    """Planned pit laps (runs, D, S), sorted, NO_LAP where there is no stop.

    From the grid this is the rule of `Race.__init__`: a number of stops from history, spread evenly over the race,
    each moved by -3 to +3 laps. From a race in progress, the stops still to make are spread evenly from the car's
    last stop to the end (at least one stop if the car has not stopped yet).
    """
    inp, n, d = world.inp, world.inp.laps, len(world.inp.drivers)
    counts = inp.stop_counts if len(inp.stop_counts) else np.array([1])
    total = rng.choice(counts, (runs, d))
    if state is None:
        first, left, lo = np.ones((runs, d)), total, 2
    else:
        first = np.broadcast_to(state.lap - state.age + 1.0, (runs, d))  # first lap of the current stint
        left = np.maximum(total - state.stops, (state.stops == 0).astype(int))
        lo = state.lap + 1
    s = max(int(left.max()), 1)
    k = np.arange(1, s + 1)[None, None, :]
    if state is None:
        base = np.round(k * n / (left[..., None] + 1))
    else:
        base = first[..., None] + np.round(k * (n - first[..., None]) / (left[..., None] + 1))
    laps = np.clip(base + rng.integers(-3, 4, (runs, d, s)), lo, n - 1)
    laps = np.where(k <= left[..., None], laps, NO_LAP)
    laps = np.sort(laps, axis=-1)
    dup = np.zeros_like(laps, bool)
    dup[..., 1:] = laps[..., 1:] == laps[..., :-1]  # the same lap twice is one stop (a set in `Race`)
    return np.sort(np.where(dup, NO_LAP, laps), axis=-1).astype(int)


@dataclass
class Batch:
    """Result of `simulate`: finishing positions (runs, D), 1 = winner, and the number of stops of each car."""

    positions: np.ndarray
    stops: np.ndarray  # (runs, D) number of stops made


def simulate(
    world: World,
    runs: int,
    seed: int = 0,
    *,
    state: State | None = None,
    ego: int | None = None,
    ego_plan: np.ndarray | None = None,
    retirements: bool = True,
) -> Batch:
    """Simulate `runs` races to the flag. `ego_plan` (runs, S) or (S,): pit laps of car `ego`, NO_LAP to pad."""
    inp, w = world.inp, world
    rng = np.random.default_rng(seed)
    n, d = inp.laps, len(inp.drivers)
    if state is None:
        cum, age, stops, alive = start_state(world, rng, runs)
        lap, sc_left = 1, np.zeros(runs, int)
    else:
        cum = np.tile(np.asarray(state.cum, float), (runs, 1))
        age = np.tile(np.asarray(state.age, float), (runs, 1))
        stops = np.tile(np.asarray(state.stops, int), (runs, 1))
        alive = np.tile(np.asarray(state.alive, bool), (runs, 1))
        lap, sc_left = state.lap, np.full(runs, int(state.sc_left))
    plans = sample_plans(world, rng, runs, state)
    pace = inp.pace + (rng.normal(0, inp.pace_shock_s, (runs, d)) if inp.pace_shock_s > 0 else 0.0)
    laps_done = np.full((runs, d), lap)
    if state is not None and state.laps_done is not None:
        laps_done = np.tile(np.asarray(state.laps_done, int), (runs, 1))
    fixed = None
    if ego is not None and ego_plan is not None:
        fixed = np.broadcast_to(np.atleast_2d(np.asarray(ego_plan, int)), (runs, np.shape(ego_plan)[-1]))
    rows = np.arange(runs)
    rank = np.arange(d)[None, :]
    hazard = w.hazard

    while lap < n:
        lap += 1
        start = (sc_left == 0) & (rng.random(runs) < hazard[min(lap, len(hazard) - 1)])
        sc_left = np.where(start, rng.integers(3, 6, runs), sc_left)
        sc = sc_left > 0

        # pit decisions: the next planned lap, or early under a fresh neutral period
        live = plans >= lap
        slot = np.argmax(live, axis=-1)  # first plan slot not yet passed (plans are sorted)
        nxt = np.where(live.any(-1), np.take_along_axis(plans, slot[..., None], -1)[..., 0], NO_LAP)
        react = (sc & (sc_left >= 3))[:, None] & (nxt - lap <= REACT_LAPS)
        pit = (nxt < NO_LAP) & ((nxt == lap) | react)
        used = pit[..., None] & (np.arange(plans.shape[-1])[None, None, :] == slot[..., None])
        plans = np.sort(np.where(used, NO_LAP, plans), axis=-1)  # a stop made leaves the plan
        if fixed is not None:
            pit[:, ego] = (fixed == lap).any(-1)

        t = BASE_S + pace + inp.wear_s_per_lap * age + rng.normal(0, inp.noise_s, (runs, d))
        loss = inp.pit_loss_s * np.where(sc, SC_PIT_FACTOR, 1.0)[:, None]
        t = t + np.where(pit, loss, 0.0)
        order = np.argsort(np.where(alive, cum, np.inf), axis=1)
        n_alive = alive.sum(1)
        running = rank < n_alive[:, None]  # slot i of `order` is a running car
        new = cum + t

        o_cum = np.take_along_axis(cum, order, 1)
        o_new = np.take_along_axis(new, order, 1)
        o_t = np.take_along_axis(t, order, 1)
        o_age = np.take_along_axis(age, order, 1)
        o_pit = np.take_along_axis(pit, order, 1)

        # neutral lap: the field closes up behind the leader in the last lap's order, plus any pit loss
        bunched = o_cum[:, :1] + BASE_S * SC_PACE + rank * SC_GAP_S + np.where(o_pit, loss, 0.0)
        o_new = np.where(sc[:, None] & running, bunched, o_new)

        # green lap: a pass chance for each running car within 3 s of the car ahead that is not clear of it
        green = ~sc
        both = running[:, 1:] & green[:, None]
        gap = o_cum[:, 1:] - o_cum[:, :-1]
        close = both & (gap <= MAX_GAP_S) & (o_new[:, 1:] < o_new[:, :-1] + STUCK_GAP_S)
        passed = np.zeros_like(close)
        if close.any():
            r_i, k_i = np.nonzero(close)
            p = w.overtake.gbm_fast(  # type: ignore[attr-defined]
                w.circuit_id,
                gap[r_i, k_i],
                o_t[r_i, k_i] - o_t[r_i, k_i + 1],
                o_age[r_i, k_i] - o_age[r_i, k_i + 1],
                lap / n,
                memo=True,
            )
            passed[r_i, k_i] = rng.random(len(p)) < p
        for k in range(1, d):
            c, ok = close[:, k - 1], passed[:, k - 1]
            ahead = o_new[:, k - 1]
            o_new[:, k] = np.where(
                c, np.where(ok, np.minimum(o_new[:, k], ahead - STUCK_GAP_S), np.maximum(o_new[:, k], ahead + STUCK_GAP_S)),
                o_new[:, k],
            )  # fmt: skip
        new = np.empty_like(new)
        new[rows[:, None], order] = o_new

        if retirements:
            out = alive & (rng.random((runs, d)) < inp.dnf_hazard)
            alive = alive & ~out
            laps_done = np.where(alive, lap, laps_done)
        cum = np.where(alive, new, cum)
        age = np.where(pit, 1.0, age + 1.0)
        stops = stops + pit
        sc_left = np.maximum(0, sc_left - 1)

    key = -laps_done * 1e6 + cum
    pos = np.empty((runs, d), int)
    pos[rows[:, None], np.argsort(key, axis=1)] = rank + 1
    return Batch(pos, stops)
