"""Pair-laps and overtaking models (spec 16)."""

from __future__ import annotations

import itertools

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from .data import Race
from .laps import clean_mask, lap_table

MAX_GAP_S = 3.0
DRS_GAP_S = 1.0
SIM_MARGIN_S = 0.4
SHRINK = 200.0
FEATURES = ["gap", "drs", "pace_delta", "tyre_age_diff", "circuit_rate", "race_frac"]


def pair_laps(race: Race, circuit_id: int) -> pd.DataFrame:
    """One row per (lap L, car A ahead, car B behind) as in spec 16, section 2, with features of section 3
    except circuit_rate (added by `add_circuit_rate`)."""
    t = lap_table(race)
    t["clean"] = clean_mask(t)
    t["cum"] = t.groupby("driver")["time_s"].cumsum()
    # pace: mean of the last 3 clean laps up to and including this lap
    clean_time = t["time_s"].where(t["clean"])
    t["pace3"] = clean_time.groupby(t["driver"]).transform(lambda s: s.rolling(3, min_periods=1).mean().ffill())
    total = int(t["lap"].max())
    by = t.set_index(["driver", "lap"])
    neutral = t.groupby("lap")["neutral"].any()
    rows = []
    for lap in range(3, total + 1):
        if neutral.get(lap, True):
            continue
        prev = t[(t["lap"] == lap - 1) & t["cum"].notna()].sort_values("position")
        drivers = prev["driver"].tolist()
        for a, b in itertools.pairwise(drivers):
            if (a, lap) not in by.index or (b, lap) not in by.index:
                continue
            pa, pb, ca, cb = by.loc[(a, lap - 1)], by.loc[(b, lap - 1)], by.loc[(a, lap)], by.loc[(b, lap)]
            if any(r["in_lap"] or r["out_lap"] for r in (pa, pb, ca, cb)):
                continue
            if np.isnan(ca["time_s"]) or np.isnan(cb["time_s"]):
                continue
            gap = float(pb["cum"] - pa["cum"])
            if not (0 <= gap <= MAX_GAP_S):
                continue
            rows.append(
                {
                    "season": race.season,
                    "round": race.round,
                    "circuit_id": circuit_id,
                    "lap": lap,
                    "a": a,
                    "b": b,
                    "gap": gap,
                    "drs": float(gap <= DRS_GAP_S),
                    "pace_delta": float(pa["pace3"] - pb["pace3"]),
                    "tyre_age_diff": float(pa["tyre_age"] - pb["tyre_age"]),
                    "race_frac": lap / total,
                    "passed": int(cb["position"] < ca["position"]),
                }
            )
    out = pd.DataFrame(rows)
    return out.dropna(subset=["pace_delta"]) if len(out) else out


def circuit_rates(train: pd.DataFrame) -> tuple[dict[int, float], float]:
    base = float(train["passed"].mean())
    g = train.groupby("circuit_id")["passed"].agg(["sum", "count"])
    return {int(c): float((s + SHRINK * base) / (n + SHRINK)) for c, s, n in zip(g.index, g["sum"], g["count"])}, base


def add_circuit_rate(df: pd.DataFrame, rates: dict[int, float], base: float) -> pd.DataFrame:
    df = df.copy()
    df["circuit_rate"] = df["circuit_id"].map(rates).fillna(base)
    return df


class Models:
    """Fit base, sim_rule, logit and gbm on training pair-laps (spec 16, section 4)."""

    def __init__(self, train: pd.DataFrame):
        import lightgbm as lgb

        self.rates, self.base = circuit_rates(train)
        tr = add_circuit_rate(train, self.rates, self.base)
        y = tr["passed"].to_numpy()
        self.sim = LogisticRegression(C=1e6).fit((tr[["pace_delta"]] - SIM_MARGIN_S).to_numpy(), y)
        self.logit = LogisticRegression(C=1e6, max_iter=1000).fit(tr[FEATURES].to_numpy(), y)
        self.gbm = lgb.LGBMClassifier(
            n_estimators=100, max_depth=4, learning_rate=0.05, min_child_samples=50, random_state=0, verbose=-1
        ).fit(tr[FEATURES], y)

    def predict(self, df: pd.DataFrame) -> dict[str, np.ndarray]:
        d = add_circuit_rate(df, self.rates, self.base)
        return {
            "base": np.full(len(d), self.base),
            "sim_rule": self.sim.predict_proba((d[["pace_delta"]] - SIM_MARGIN_S).to_numpy())[:, 1],
            "logit": self.logit.predict_proba(d[FEATURES].to_numpy())[:, 1],
            "gbm": self.gbm.predict_proba(d[FEATURES])[:, 1],
        }


def log_loss(y: np.ndarray, p: np.ndarray) -> float:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))
