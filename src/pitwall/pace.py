"""Pre-race pace model of spec 06: qualifying gap and season form."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

Q_CLIP_S = 5.0
MIN_CLEAN_LAPS = 10


def qualifying_gap(best: pd.Series, drivers: list[str]) -> np.ndarray:
    """Best qualifying lap minus the field median, clipped (spec 06, section 2). No time -> slowest in the field."""
    b = best.reindex(drivers).astype(float)
    if b.notna().any():
        b = b.fillna(b.max())
        gap = b - b.median()
    else:
        gap = b.fillna(0.0)
    return np.clip(gap.to_numpy(), -Q_CLIP_S, Q_CLIP_S)


def form(previous_paces: list[dict[str, float]], drivers: list[str]) -> np.ndarray:
    """Mean race pace of each driver over earlier races of the same season, 0 if none."""
    return np.array([np.mean([p[d] for p in previous_paces if d in p] or [0.0]) for d in drivers])


@dataclass
class PaceFit:
    beta_q: float
    beta_f: float
    sigma_r: float
    n: int

    def predict(self, q: np.ndarray, f: np.ndarray) -> np.ndarray:
        return self.beta_q * q + self.beta_f * f


def fit(rows: pd.DataFrame) -> PaceFit:
    """Least squares without intercept. `rows` has the columns q, f, pace, clean_laps."""
    r = rows[(rows["clean_laps"] >= MIN_CLEAN_LAPS) & rows["pace"].notna()]
    x = r[["q", "f"]].to_numpy(float)
    y = r["pace"].to_numpy(float)
    beta, *_ = np.linalg.lstsq(x, y, rcond=None)
    resid = y - x @ beta
    return PaceFit(float(beta[0]), float(beta[1]), float(resid.std(ddof=2)), len(r))
