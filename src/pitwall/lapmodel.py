"""The gbm_pretrain next-lap-time model of spec 03, shared by later specs."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .dump import Dump
from .features import FEATURES, build
from .laps import lap_table
from .splits import split_of

PARAMS = {
    "objective": "l1",
    "n_estimators": 400,
    "learning_rate": 0.03,
    "num_leaves": 31,
    "min_child_samples": 50,
    "colsample_bytree": 0.8,
    "random_state": 0,
    "verbose": -1,
}
PRETRAIN_SEASONS = (2022, 2023, 2024, 2025)


def race_features(dump: Dump, season: int, rnd: int) -> pd.DataFrame:
    f = build(lap_table(dump.race(season, rnd)))
    f["season"], f["round"] = season, rnd
    return f[f["use"]]


def fit_predict(train: pd.DataFrame, test: pd.DataFrame):
    import lightgbm as lgb

    model = lgb.LGBMRegressor(**PARAMS).fit(train[FEATURES], train["delta"])
    return test["last1"].to_numpy() + model.predict(test[FEATURES]), model


def pretrain_features(dump: Dump) -> pd.DataFrame:
    rows = [race_features(dump, s, int(r)) for s in PRETRAIN_SEASONS for r in dump.schedule(s)["round"]]
    return pd.concat(rows, ignore_index=True)


def development_rounds(dump: Dump) -> list[int]:
    sched = dump.schedule(2026)
    return [int(r) for r, d in zip(sched["round"], sched["date"]) if split_of(d) == "development"]


def walk_forward_residuals(pre: pd.DataFrame, dev: dict[int, pd.DataFrame]) -> pd.DataFrame:
    """For each development round k, train on pre-training + rounds < k, and predict round k."""
    out = []
    for k in sorted(dev):
        train = pd.concat([pre, *[dev[r] for r in dev if r < k]], ignore_index=True)
        pred, _ = fit_predict(train, dev[k])
        test = dev[k].copy()
        test["pred"] = pred
        test["resid"] = test["time_s"] - pred
        out.append(test)
    return pd.concat(out, ignore_index=True)


def loso_residuals(pre: pd.DataFrame) -> pd.DataFrame:
    """Leave-one-season-out residuals for the pre-training seasons."""
    out = []
    for s in PRETRAIN_SEASONS:
        pred, _ = fit_predict(pre[pre["season"] != s], pre[pre["season"] == s])
        test = pre[pre["season"] == s].copy()
        test["pred"] = pred
        test["resid"] = test["time_s"] - pred
        out.append(test)
    return pd.concat(out, ignore_index=True)


def stint_sequences(df: pd.DataFrame, value: str = "resid") -> list[np.ndarray]:
    """One array per (season, round, driver, stint), in lap order."""
    df = df.sort_values(["season", "round", "driver", "stint", "lap"])
    return [g[value].to_numpy() for _, g in df.groupby(["season", "round", "driver", "stint"], sort=False)]
