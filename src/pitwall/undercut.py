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


def open_duels(race) -> pd.DataFrame:
    """Spec 10: undercut events without the response condition. `a` pits at the end of lap `lap_a` while `b` is
    directly ahead (at most MAX_GAP_S) and `b` does not pit on lap_a - 1 or lap_a. `lap_b` is the next stop of `b`
    after lap_a (any wait). If `b` does not stop again, the outcome lap is the last lap that both completed.
    Outcome `a_ahead`: `a` is ahead after the outcome lap. No neutralised lap from lap_a - 1 to the outcome lap.
    """
    t = lap_table(race)
    cum = cumulative_times(t)
    neutral = t.groupby("lap")["neutral"].any()
    pits = race.pitstops.dropna(subset=["lap"])
    pit_laps = {d: set(g["lap"].astype(int)) for d, g in pits.groupby("driver")}
    age = t.set_index(["driver", "lap"])["tyre_age"]
    total = int(t["lap"].max())
    rows = []
    for a, lap_a in zip(pits["driver"], pits["lap"].astype(int)):
        before = lap_a - 1
        if before < 2 or before not in cum.index or a not in cum.columns or np.isnan(cum.at[before, a]):
            continue
        ahead = cum.loc[before].dropna()
        ahead = ahead[ahead < cum.at[before, a]]
        if ahead.empty:
            continue
        b = ahead.idxmax()
        gap = float(cum.at[before, a] - ahead[b])
        if gap > MAX_GAP_S or {before, lap_a} & pit_laps.get(b, set()):
            continue
        later = sorted(x for x in pit_laps.get(b, set()) if x > lap_a)
        both = cum[[a, b]].dropna()
        if both.empty:
            continue
        last_both = int(both.index.max())
        if later:
            lap_b, end = later[0], later[0] + 1
        else:
            lap_b, end = None, last_both
        if end > last_both or end <= lap_a:
            continue
        if neutral.reindex(range(before, end + 1)).fillna(True).any():
            continue
        rows.append(
            {
                "season": race.season,
                "round": race.round,
                "a": a,
                "b": b,
                "lap_a": lap_a,
                "lap_b": lap_b,
                "b_responds": lap_b is not None,
                "gap_s": gap,
                "age_a": int(age.get((a, lap_a), 0)),
                "age_b": int(age.get((b, lap_a), 0)),
                "race_lap_frac": lap_a / total,
                "remaining_laps": total - lap_a,
                "a_ahead": bool(cum.at[end, a] < cum.at[end, b]),
            }
        )
    return pd.DataFrame(rows)
