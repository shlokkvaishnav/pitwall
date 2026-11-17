"""Causal features for the next-lap-time model (docs/specs/03-lap-model.md, section 2)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .laps import clean_mask

FEATURES = [
    "last1",
    "last2",
    "last3",
    "last_mean",
    "tyre_age",
    "stint",
    "race_lap_frac",
    "gap_ahead",
    "gap_behind",
    "ahead_lt_1s",
    "ahead_lt_2s",
    "laps_since_neutral",
    "field_prev",
]


def _gaps(laps: pd.DataFrame) -> pd.DataFrame:
    """Gap to the car ahead and behind at the end of each lap, from cumulative race times."""
    lt = laps["time_s"].fillna(laps.groupby("lap")["time_s"].transform("median"))
    cum = lt.groupby(laps["driver"]).cumsum()
    frame = pd.DataFrame({"lap": laps["lap"], "position": laps["position"], "cum": cum}, index=laps.index)
    frame = frame.sort_values(["lap", "position"])
    frame["gap_ahead"] = frame.groupby("lap")["cum"].diff()
    frame["gap_behind"] = -frame.groupby("lap")["cum"].diff(-1)
    return frame[["gap_ahead", "gap_behind"]].reindex(laps.index)


def build(laps: pd.DataFrame) -> pd.DataFrame:
    """One row per lap with FEATURES, the target `delta` (time - last1), and `use` (row can be scored).

    `laps` is a lap table from pitwall.laps.lap_table. Each feature for lap n uses only laps before n.
    """
    df = laps.sort_values(["driver", "lap"]).copy()
    clean = clean_mask(df)
    t_clean = df["time_s"].where(clean)
    g = t_clean.groupby([df["driver"], df["stint"]])
    for k in (1, 2, 3):
        # k-th last clean lap before this lap, in the same stint
        df[f"last{k}"] = g.transform(lambda s, k=k: s.shift(1).ffill() if k == 1 else _kth_last(s, k))
    df["last_mean"] = df[["last1", "last2", "last3"]].mean(axis=1)

    gaps = _gaps(df)
    by_driver = df.groupby("driver")
    df["gap_ahead"] = gaps["gap_ahead"].groupby(df["driver"]).shift(1)
    df["gap_behind"] = gaps["gap_behind"].groupby(df["driver"]).shift(1)
    df["ahead_lt_1s"] = (df["gap_ahead"] < 1.0).astype(float)
    df["ahead_lt_2s"] = (df["gap_ahead"] < 2.0).astype(float)

    neutral_seen = df["neutral"].astype(int).groupby(df["driver"]).cumsum().groupby(df["driver"]).shift(1).fillna(0)
    run = df.groupby([df["driver"], neutral_seen]).cumcount()
    df["laps_since_neutral"] = run.astype(float)

    field = t_clean.groupby(df["lap"]).median()
    df["field_prev"] = df["lap"].map(field.shift(1))

    df["delta"] = df["time_s"] - df["last1"]
    df["use"] = clean & df["last1"].notna()
    del by_driver
    return df


def _kth_last(s: pd.Series, k: int) -> pd.Series:
    """For each row, the k-th most recent non-NaN value strictly before it."""
    vals = s.to_numpy()
    out = np.full(len(vals), np.nan)
    seen: list[float] = []
    for i, v in enumerate(vals):
        if len(seen) >= k:
            out[i] = seen[-k]
        if not np.isnan(v):
            seen.append(v)
    return pd.Series(out, index=s.index)
