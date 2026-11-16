"""Undercut duels (specs/07-undercut.md): a driver pits first to pass the car directly ahead."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .laps import lap_table

MAX_GAP_S = 3.0
MAX_RESPONSE_LAPS = 5


def cumulative_times(t: pd.DataFrame) -> pd.DataFrame:
    """(lap x driver) cumulative race time. NaN after a missing lap time."""
    wide = t.pivot(index="lap", columns="driver", values="time_s").sort_index()
    return wide.cumsum(skipna=False)


def duels(race) -> pd.DataFrame:
    """One row per undercut duel. `a` pits at the end of lap `lap_a`; `b` was directly ahead of `a` at the end
    of lap `lap_a` - 1, at most MAX_GAP_S ahead, and pits at the end of lap `lap_b` (lap_a < lap_b <= lap_a + 5).
    There is no neutralised lap from lap_a - 1 to lap_b + 1. Outcome `a_ahead`: `a` is ahead after lap_b + 1.
    """
    t = lap_table(race)
    cum = cumulative_times(t)
    neutral = t.groupby("lap")["neutral"].any()
    pits = race.pitstops.dropna(subset=["lap"])
    pit_laps = {d: set(g["lap"].astype(int)) for d, g in pits.groupby("driver")}
    age = t.set_index(["driver", "lap"])["tyre_age"]
    rows = []
    for a, lap_a in zip(pits["driver"], pits["lap"].astype(int)):
        before = lap_a - 1
        if before < 2 or before not in cum.index or a not in cum.columns or np.isnan(cum.at[before, a]):
            continue
        ahead = cum.loc[before].dropna()
        ahead = ahead[ahead < cum.at[before, a]]
        if ahead.empty:
            continue
        b = ahead.idxmax()  # the car directly ahead
        gap = float(cum.at[before, a] - ahead[b])
        if gap > MAX_GAP_S or {before, lap_a} & pit_laps.get(b, set()):
            continue
        later = sorted(x for x in pit_laps.get(b, set()) if lap_a < x <= lap_a + MAX_RESPONSE_LAPS)
        if not later:
            continue
        lap_b = later[0]
        end = lap_b + 1
        if end not in cum.index or neutral.reindex(range(before, end + 1)).fillna(True).any():
            continue
        ca, cb = cum.at[end, a], cum.at[end, b]
        if np.isnan(ca) or np.isnan(cb):
            continue
        rows.append(
            {
                "season": race.season,
                "round": race.round,
                "a": a,
                "b": b,
                "lap_a": lap_a,
                "lap_b": lap_b,
                "gap_s": gap,
                "wait_laps": lap_b - lap_a,
                "age_a": int(age.get((a, lap_a), 0)),
                "age_b": int(age.get((b, lap_a), 0)),
                "race_lap_frac": lap_a / int(t["lap"].max()),
                "a_ahead": bool(ca < cb),
            }
        )
    return pd.DataFrame(rows)
