"""Per-lap hazard of a safety car, VSC or red-flag period starting (spec 15)."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar
from scipy.special import betaln, expit, logit

NEUTRAL_KINDS = ("sc", "vsc", "red")
EPS = 1e-6


def event_laps(official: Mapping[int, set[str]], last_lap: int) -> pd.DataFrame:
    """One row per lap 1..last_lap: in_period, at_risk, event, kind (spec 15, section 2)."""
    marked = {lap: {k for k in kinds if k in NEUTRAL_KINDS} for lap, kinds in official.items()}
    rows, prev = [], False
    for lap in range(1, last_lap + 1):
        kinds = marked.get(lap, set())
        now = bool(kinds)
        at_risk = lap == 1 or not prev
        event = at_risk and now
        kind = next((k for k in NEUTRAL_KINDS if k in kinds), None) if event else None
        rows.append({"lap": lap, "in_period": now, "at_risk": at_risk, "event": event, "kind": kind})
        prev = now
    return pd.DataFrame(rows)


def race_rows(official: Mapping[int, set[str]], last_lap: int, **info) -> pd.DataFrame:
    """At-risk laps of one race with race info (season, round, circuit_id, laps) and the lap features of M2."""
    t = event_laps(official, last_lap)
    t = t[t["at_risk"]].copy()
    for k, v in info.items():
        t[k] = v
    t["laps"] = last_lap
    t["lap1"] = (t["lap"] == 1).astype(float)
    t["lap2_3"] = t["lap"].isin([2, 3]).astype(float)
    t["event"] = t["event"].astype(float)
    return t


def _shrunk_rates(train: pd.DataFrame) -> tuple[dict, float]:
    """Empirical-Bayes circuit event rates (beta-binomial, prior strength by maximum marginal likelihood)."""
    g = train.groupby("circuit_id")["event"].agg(["sum", "count"])
    k, n = g["sum"].to_numpy(), g["count"].to_numpy()
    m = float(k.sum() / n.sum())

    def nll(log_s: float) -> float:
        s = np.exp(log_s)
        a, b = m * s, (1 - m) * s
        return -float(np.sum(betaln(k + a, n - k + b) - betaln(a, b)))

    s = float(np.exp(minimize_scalar(nll, bounds=(np.log(1.0), np.log(1e6)), method="bounded").x))
    rates = {c: float((kc + s * m) / (nc + s)) for c, kc, nc in zip(g.index, k, n)}
    return rates, s


def _fit_logistic(x: np.ndarray, y: np.ndarray, offset: np.ndarray, iters: int = 50) -> np.ndarray:
    """Logistic regression with an offset, by Newton steps (small ridge for stability)."""
    w = np.zeros(x.shape[1])
    for _ in range(iters):
        p = expit(x @ w + offset)
        grad = x.T @ (y - p) - 1e-6 * w
        h = (x * (p * (1 - p))[:, None]).T @ x + 1e-6 * np.eye(x.shape[1])
        step = np.linalg.solve(h, grad)
        w += step
        if np.abs(step).max() < 1e-10:
            break
    return w


class Models:
    """Fit M0, M1 and M2 on training rows (from `race_rows`), then predict per-lap hazards."""

    def __init__(self, train: pd.DataFrame):
        self.global_rate = float(train["event"].mean())
        per_race = train.groupby(["season", "round", "circuit_id"])["event"].sum().reset_index()
        self.global_periods = float(per_race["event"].mean())
        self.circuit_periods = per_race.groupby("circuit_id")["event"].mean().to_dict()
        self.rates, self.prior_strength = _shrunk_rates(train)
        x = self._x(train)
        self.w = _fit_logistic(x, train["event"].to_numpy(), self._offset(train))

    @staticmethod
    def _x(t: pd.DataFrame) -> np.ndarray:
        return np.column_stack([np.ones(len(t)), t["lap1"], t["lap2_3"]])

    def _offset(self, t: pd.DataFrame) -> np.ndarray:
        r = t["circuit_id"].map(self.rates).fillna(self.global_rate).to_numpy(float)
        return logit(np.clip(r, EPS, 1 - EPS)) - logit(self.global_rate)

    def predict(self, t: pd.DataFrame) -> dict[str, np.ndarray]:
        m0 = np.full(len(t), self.global_rate)
        periods = t["circuit_id"].map(self.circuit_periods).fillna(self.global_periods).to_numpy(float)
        m1 = np.clip(periods / t["laps"].to_numpy(float), EPS, 1 - EPS)
        m2 = expit(self._x(t) @ self.w + self._offset(t))
        return {"M0": m0, "M1": m1, "M2": m2}


def log_loss(y: np.ndarray, p: np.ndarray) -> float:
    p = np.clip(p, EPS, 1 - EPS)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def any_event_prob(t: pd.DataFrame, p: np.ndarray) -> pd.Series:
    """Chance of at least one period in each race, from per-lap hazards (at-risk laps treated as independent)."""
    q = pd.Series(np.log1p(-np.clip(p, EPS, 1 - EPS)), index=t.index)
    s = q.groupby([t["season"], t["round"]]).sum()
    return pd.Series(1 - np.exp(s.to_numpy()), index=s.index)
