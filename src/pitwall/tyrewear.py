"""Tyre wear per compound (spec 23): lap time = driver + compound offset + compound wear x tyre life + fuel x lap."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .laps import clean_mask, lap_table

COMPOUNDS = ("SOFT", "MEDIUM", "HARD")
IDX = {c: i for i, c in enumerate(COMPOUNDS)}
NEXT = np.array([1, 2, 1])  # the compound another car fits at its next stop: S -> M, M -> H, H -> M
MIN_LAPS = 30  # clean laps of a compound in a race to estimate its wear


@dataclass
class TyreRates:
    deg: np.ndarray  # (3,) s per lap of tyre life
    offset: np.ndarray  # (3,) s per lap against MEDIUM on new tyres


def race_fit(race, joined: pd.DataFrame) -> dict | None:
    """One race: least squares on clean dry laps with driver effects. `joined` = `tyres.join(race, ...)`.
    Returns {compound: {"deg", "offset", "laps"}} for the compounds with at least MIN_LAPS laps, or None."""
    t = lap_table(race)
    t = t.merge(joined[["driver", "lap", "compound", "life"]], on=["driver", "lap"], how="left")
    c = t[clean_mask(t) & t["compound"].isin(COMPOUNDS) & t["life"].notna()]
    counts = c["compound"].value_counts()
    used = [k for k in COMPOUNDS if counts.get(k, 0) >= MIN_LAPS]
    if len(used) < 2 or c["driver"].nunique() < 5:
        return None
    c = c[c["compound"].isin(used)]
    cols = {}
    for k in used:
        on = (c["compound"] == k).astype(float)
        cols[f"deg_{k}"] = on * c["life"].astype(float)
        if k != used[0]:
            cols[f"off_{k}"] = on
    cols["fuel"] = c["lap"].astype(float)
    x = pd.DataFrame(cols, index=c.index)
    y = c["time_s"].astype(float)
    xd = (x - x.groupby(c["driver"]).transform("mean")).to_numpy()
    yd = (y - y.groupby(c["driver"]).transform("mean")).to_numpy()
    beta, *_ = np.linalg.lstsq(xd, yd, rcond=None)
    b = dict(zip(x.columns, beta))
    base = {k: b.get(f"off_{k}", 0.0) for k in used}  # relative to used[0]
    ref = base.get("MEDIUM", np.nan)
    out = {}
    for k in used:
        out[k] = {
            "deg": float(b[f"deg_{k}"]),
            "offset": float(base[k] - ref) if np.isfinite(ref) else float("nan"),
            "laps": int(counts[k]),
        }
    return out


def pool(fits: list[dict]) -> TyreRates:
    """Median over races of each compound's wear and offset (offsets only from races that ran MEDIUM)."""
    deg, off = np.zeros(3), np.zeros(3)
    for i, k in enumerate(COMPOUNDS):
        d = [f[k]["deg"] for f in fits if k in f]
        o = [f[k]["offset"] for f in fits if k in f and np.isfinite(f[k]["offset"])]
        deg[i] = float(np.median(d)) if d else np.nan
        off[i] = float(np.median(o)) if o else 0.0
    deg = np.where(np.isfinite(deg), deg, np.nanmedian(deg))
    return TyreRates(np.maximum(deg, 0.0), off)
