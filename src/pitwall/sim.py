"""Lap-by-lap Monte Carlo race simulator, version A (spec 05) with the pace shock of version B (spec 06)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .data import Race
from .laps import clean_mask, lap_table

PASS_MARGIN_S = 0.4
STUCK_GAP_S = 0.2
SC_LAPS = 4
SC_GAP_S = 0.3
START_GAP_S = 0.25


@dataclass
class RaceStats:
    """Statistics of one past race, used as history for later races."""

    season: int
    round: int
    circuit_id: int
    pit_losses: list[float]
    wear_slope: float
    stops: list[int]
    neutral_periods: int
    pace: dict[str, float]  # driver -> median clean lap minus field median clean lap
    starters: int
    classified: int
    laps: int
    clean_laps: dict[str, int] | None = None  # driver -> number of clean laps


def race_stats(race: Race, circuit_id: int) -> RaceStats:
    t = lap_table(race)
    clean = clean_mask(t)
    field = float(t.loc[clean, "time_s"].median())
    med = t[clean].groupby("driver")["time_s"].median()
    pace = (med - field).to_dict()

    losses = []
    for d, lap in zip(race.pitstops["driver"], race.pitstops["lap"]):
        if pd.isna(lap) or d not in med.index:
            continue
        rows = t[(t["driver"] == d) & t["lap"].isin([int(lap), int(lap) + 1])]
        if len(rows) == 2 and rows["time_s"].notna().all() and not rows["neutral"].any():
            losses.append(float(rows["time_s"].sum() - 2 * med[d]))

    slopes = []
    for _, g in t[clean].groupby(["driver", "stint"]):
        if len(g) >= 6:
            slopes.append(float(np.polyfit(g["tyre_age"], g["time_s"], 1)[0]))

    res = race.results
    cls = res[res["classified"]]
    stops = race.pitstops.groupby("driver")["stop"].max()
    neutral = t.groupby("lap")["neutral"].first().sort_index()
    neutral = neutral[neutral.index > 1].astype(int).to_numpy()
    periods = int(((neutral[1:] == 1) & (neutral[:-1] == 0)).sum() + (neutral[:1] == 1).sum()) if len(neutral) else 0
    return RaceStats(
        season=race.season,
        round=race.round,
        circuit_id=int(circuit_id),
        pit_losses=losses,
        wear_slope=float(np.median(slopes)) if slopes else float("nan"),
        stops=[int(stops.get(d, 0)) for d in cls["driver"]],
        neutral_periods=periods,
        pace=pace,
        starters=int((res["laps"] > 0).sum()),
        classified=len(cls),
        laps=int(res["laps"].max()),
        clean_laps=t[clean].groupby("driver").size().astype(int).to_dict(),
    )


@dataclass
class SimInputs:
    drivers: list[str]  # in grid order
    pace: np.ndarray  # (D,) s per lap, lower is faster
    noise_s: float
    pit_loss_s: float
    wear_s_per_lap: float
    stop_counts: np.ndarray  # empirical distribution of the number of stops
    sc_rate: float  # mean neutralised periods per race
    dnf_hazard: float  # per car per lap
    laps: int
    pace_shock_s: float = 0.0  # SD of one pace offset per driver per run (spec 06)


def inputs_from_history(
    history: list[RaceStats], circuit_id: int, grid: pd.DataFrame, laps: int, noise_s: float = 1.0
) -> SimInputs:
    """Build the inputs of spec 05, section 2. `history` must contain only races before the test race."""
    same = [h for h in history if h.circuit_id == circuit_id]

    def pick(values_same, values_all, fn):
        v = [x for x in values_same if np.isfinite(x)]
        return fn(v) if v else fn([x for x in values_all if np.isfinite(x)])

    pit = pick([x for h in same for x in h.pit_losses], [x for h in history for x in h.pit_losses], np.median)
    wear = pick([h.wear_slope for h in same], [h.wear_slope for h in history], np.median)
    stops = [s for h in same for s in h.stops] or [s for h in history for s in h.stops]
    sc = (
        float(np.mean([h.neutral_periods for h in same]))
        if same
        else float(np.mean([h.neutral_periods for h in history]))
    )
    this_season = [h for h in history if h.season == 2026]
    if this_season:
        dnf = 1 - sum(h.classified for h in this_season) / max(sum(h.starters for h in this_season), 1)
        dnf_h = dnf / np.mean([h.laps for h in this_season])
    else:
        dnf_h = 0.0

    g = grid.copy()
    g["order"] = np.where(g["grid"] > 0, g["grid"], 100 + g.index.to_numpy())
    g = g.sort_values("order")
    drivers = g["driver"].tolist()
    pace = np.array([np.mean([h.pace[d] for h in this_season if d in h.pace] or [0.0]) for d in drivers])
    return SimInputs(drivers, pace, noise_s, float(pit), float(wear), np.asarray(stops), sc, float(dnf_h), int(laps))


def simulate(inp: SimInputs, runs: int = 2000, seed: int = 0) -> np.ndarray:
    """Return finishing positions (runs, D), 1 = winner, in the order of inp.drivers."""
    rng = np.random.default_rng(seed)
    d, n = len(inp.drivers), inp.laps
    cum = np.broadcast_to(np.arange(d) * START_GAP_S, (runs, d)).copy()
    cum += rng.normal(0, 2 * inp.noise_s, (runs, d))
    alive = np.ones((runs, d), dtype=bool)
    laps_done = np.ones((runs, d), dtype=int)
    age = np.ones((runs, d))

    # pit plan: number of stops from history, laps spread evenly with noise
    n_stops = rng.choice(inp.stop_counts, size=(runs, d)) if len(inp.stop_counts) else np.ones((runs, d), int)
    max_stops = int(n_stops.max()) if n_stops.size else 0
    pit_laps = np.full((runs, d, max(max_stops, 1)), -1)
    for k in range(1, max_stops + 1):
        base = np.round(k * n / (n_stops + 1))
        lap = np.clip(base + rng.integers(-3, 4, (runs, d)), 2, n - 1)
        pit_laps[..., k - 1] = np.where(n_stops >= k, lap, -1)

    # safety-car periods
    sc = np.zeros((runs, n + 1), dtype=bool)
    counts = rng.poisson(inp.sc_rate, runs)
    for r in np.flatnonzero(counts):
        for start in rng.integers(2, max(n - SC_LAPS, 3), counts[r]):
            sc[r, start : start + SC_LAPS] = True

    pace = np.broadcast_to(inp.pace, (runs, d))
    if inp.pace_shock_s > 0:
        pace = pace + rng.normal(0, inp.pace_shock_s, (runs, d))

    rows = np.arange(runs)[:, None]
    for lap in range(2, n + 1):
        order = np.argsort(np.where(alive, cum, np.inf), axis=1)
        t = pace + inp.wear_s_per_lap * age + rng.normal(0, inp.noise_s, (runs, d))
        pitting = (pit_laps == lap).any(-1)
        t = t + np.where(pitting, inp.pit_loss_s, 0.0)
        age = np.where(pitting, 1.0, age + 1.0)
        new = cum + t

        # overtaking in the order of the last lap
        sorted_new = np.take_along_axis(new, order, 1)
        sorted_t = np.take_along_axis(t, order, 1)
        sorted_alive = np.take_along_axis(alive, order, 1)
        for p in range(1, d):
            ahead, me = sorted_new[:, p - 1], sorted_new[:, p]
            faster = (sorted_t[:, p - 1] - sorted_t[:, p]) >= PASS_MARGIN_S
            blocked = sorted_alive[:, p] & sorted_alive[:, p - 1] & (me < ahead) & ~faster
            sorted_new[:, p] = np.where(blocked, ahead + STUCK_GAP_S, me)
        # neutralised lap: no passing, gaps close up at the end of the period
        in_sc = sc[:, lap]
        if in_sc.any():
            prev_sorted = np.take_along_axis(cum, order, 1)
            leader = prev_sorted[:, :1] + np.median(t)
            bunched = leader + np.arange(d)[None] * SC_GAP_S
            sorted_new = np.where(in_sc[:, None] & sorted_alive, bunched, sorted_new)
        new_cum = np.empty_like(cum)
        new_cum[rows, order] = sorted_new

        # retirements
        out = alive & (rng.random((runs, d)) < inp.dnf_hazard)
        alive &= ~out
        cum = np.where(alive, new_cum, cum)
        laps_done = np.where(alive, lap, laps_done)

    key = -laps_done * 1e6 + np.where(alive, cum, cum + 1e5)
    pos = np.empty((runs, d), dtype=int)
    pos[rows, np.argsort(key, axis=1)] = np.arange(1, d + 1)[None]
    return pos
