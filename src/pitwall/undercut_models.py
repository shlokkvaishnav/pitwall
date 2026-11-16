"""Undercut models of spec 08, also used by spec 09."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .dump import Dump
from .lapmodel import PRETRAIN_SEASONS, development_rounds
from .tyres import join, parse
from .undercut import duels

FULL07 = ["gap_s", "wait_laps", "age_diff", "race_lap_frac"]
FULL_C = [*FULL07, "compound_step", "fresh_a"]
DIRECT = ["gap_s", "age_diff", "race_lap_frac", "compound_step", "fresh_a"]
MODELS = ("base_rate", "full07", "full_c", "direct", "two_stage")
EPS = 1e-6


def logloss(p, y):
    p = np.clip(p, EPS, 1 - EPS)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def logistic():
    return make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=1000))


def load(root: Path, seasons=(*PRETRAIN_SEASONS, 2026)) -> pd.DataFrame:
    """Duels of spec 07 with the compound inputs of spec 08."""
    dump = Dump(root / "data" / "raw" / "jolpica-dump" / "csv")
    parts = []
    for s in seasons:
        rounds = development_rounds(dump) if s == 2026 else [int(r) for r in dump.schedule(s)["round"]]
        for r in rounds:
            race = dump.race(s, r)
            d = duels(race)
            if d.empty:
                continue
            codes = {dump.driver_codes[x]: x for x in race.results["driver"]}
            j = join(race, parse(root / "data" / "raw" / "tracinginsights" / str(s) / f"{r:02d}.json"), codes)
            j = j.set_index(["driver", "lap"])
            d["hard_a_new"] = [j["hardness"].get((a, la + 1), np.nan) for a, la in zip(d["a"], d["lap_a"])]
            d["hard_b"] = [j["hardness"].get((b, la), np.nan) for b, la in zip(d["b"], d["lap_a"])]
            d["life_a_new"] = [j["life"].get((a, la + 1), np.nan) for a, la in zip(d["a"], d["lap_a"])]
            parts.append(d)
    d = pd.concat(parts, ignore_index=True)
    d["age_diff"] = d["age_b"] - d["age_a"]
    d["race"] = d["season"].astype(str) + "-" + d["round"].astype(str)
    d["compound_step"] = d["hard_b"] - d["hard_a_new"]
    d["fresh_a"] = (d["life_a_new"] == 1).astype(float)
    return d


def predict(train: pd.DataFrame, test: pd.DataFrame) -> dict[str, np.ndarray]:
    y = train["a_ahead"].astype(int)
    out = {"base_rate": np.full(len(test), y.mean())}
    fitted = {}
    for name, cols in (("full07", FULL07), ("full_c", FULL_C), ("direct", DIRECT)):
        fitted[name] = logistic().fit(train[cols], y)
        out[name] = fitted[name].predict_proba(test[cols])[:, 1]
    resp = logistic().fit(train[DIRECT], train["wait_laps"])
    pw = resp.predict_proba(test[DIRECT])
    two = np.zeros(len(test))
    for k, w in enumerate(resp.classes_):
        x = test[FULL_C].copy()
        x["wait_laps"] = w
        two += pw[:, k] * fitted["full_c"].predict_proba(x)[:, 1]
    out["two_stage"] = two
    out["_response_acc"] = (resp.classes_[pw.argmax(1)] == test["wait_laps"].to_numpy()).astype(float)
    return out
