"""Split conformal prediction intervals on forecast residuals (docs/specs/12-lap-intervals.md, section 2)."""

from __future__ import annotations

import math

import numpy as np


def _upper_order_stat(values: np.ndarray, level: float) -> float:
    """The ceil((n + 1) * level)-th smallest value, or +inf if that rank is above n."""
    n = values.size
    rank = math.ceil((n + 1) * level - 1e-12)
    if rank > n:
        return math.inf
    return float(np.partition(values, rank - 1)[rank - 1])


def conformal_offsets(resid, alpha: float) -> tuple[float, float]:
    """Equal-tailed split conformal offsets (lo, hi) for residuals resid = actual - forecast.

    The interval for a new forecast y_hat is [y_hat + lo, y_hat + hi]. Each tail has miscoverage alpha / 2,
    so if the residuals are exchangeable with the new one, the coverage is at least 1 - alpha.
    """
    if not 0 < alpha < 1:
        raise ValueError(f"alpha must be in (0, 1): {alpha}")
    r = np.asarray(resid, float)
    r = r[~np.isnan(r)]
    if r.size == 0:
        raise ValueError("no residuals to calibrate on")
    level = 1 - alpha / 2
    return -_upper_order_stat(-r, level), _upper_order_stat(r, level)


def coverage(actual, lower, upper) -> float:
    """Fraction of actual values inside [lower, upper]."""
    y = np.asarray(actual, float)
    return float(((y >= np.asarray(lower, float)) & (y <= np.asarray(upper, float))).mean())
