"""Next-lap-time baselines for rule R1 (spec 00).

Each function returns a one-step-ahead prediction for each row of a lap table.
The prediction for lap n uses only clean laps of the same driver before lap n (causal).
NaN means no prediction (for example, the first clean lap of a stint).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .laps import clean_mask


def previous_lap(laps: pd.DataFrame) -> pd.Series:
    """The last clean lap time of the same driver in the same stint."""
    clean = clean_mask(laps)
    t = laps["time_s"].where(clean)
    return t.groupby([laps["driver"], laps["stint"]]).transform(lambda s: s.ffill().shift(1))


def linear_stint(laps: pd.DataFrame, min_laps: int = 3) -> pd.Series:
    """Least-squares line of lap time against tyre age, fitted on the earlier clean laps of the stint."""
    clean = clean_mask(laps)
    out = pd.Series(np.nan, index=laps.index)
    for _, g in laps.groupby(["driver", "stint"]):
        xs: list[float] = []
        ys: list[float] = []
        for idx, age, t, ok in zip(g.index, g["tyre_age"], g["time_s"], clean[g.index]):
            if len(xs) >= min_laps:
                slope, icpt = np.polyfit(xs, ys, 1)
                out[idx] = icpt + slope * age
            elif xs:
                out[idx] = ys[-1]
            if ok:
                xs.append(age)
                ys.append(t)
    return out


def local_trend(laps: pd.DataFrame, level_std: float = 0.15, slope_std: float = 0.01, obs_std: float = 0.6):
    """Kalman filter with a local linear trend per stint (a state-space tyre model without energy).

    State: [pace, wear rate]. The pace moves by the wear rate each lap. Non-clean laps are not observed.
    """
    clean = clean_mask(laps)
    f = np.array([[1.0, 1.0], [0.0, 1.0]])
    q = np.diag([level_std**2, slope_std**2])
    r = obs_std**2
    out = pd.Series(np.nan, index=laps.index)
    for _, g in laps.groupby(["driver", "stint"]):
        x, p, started = np.zeros(2), np.eye(2), False
        for idx, t, ok in zip(g.index, g["time_s"], clean[g.index]):
            if started:
                x = f @ x
                p = f @ p @ f.T + q
                out[idx] = x[0]
            if not ok:
                continue
            if not started:
                x, p, started = np.array([t, 0.05]), np.diag([1.0, 0.05**2]), True
                continue
            s = p[0, 0] + r
            k = p[:, 0] / s
            x = x + k * (t - x[0])
            p = p - np.outer(k, p[0, :])
    return out


def mae(pred: pd.Series, laps: pd.DataFrame) -> float:
    """Mean absolute error on clean laps that have a prediction."""
    keep = clean_mask(laps) & pred.notna()
    return float((pred[keep] - laps.loc[keep, "time_s"]).abs().mean())
