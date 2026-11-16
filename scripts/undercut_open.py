"""Spec 10: undercut on open events, compared with the model of arXiv 2607.06495.

Usage: PYTHONPATH=src .venv/bin/python scripts/undercut_open.py
Writes results/10-undercut-open-events.json.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from pitwall.dump import Dump
from pitwall.evaluate import dm_block_bootstrap
from pitwall.lapmodel import development_rounds
from pitwall.tyres import join, parse
from pitwall.undercut import open_duels
from pitwall.undercut_models import logloss

ROOT = Path(__file__).resolve().parents[1]
PITWALL = ["gap_s", "age_diff", "log_remaining"]
DECISION = [*PITWALL, "race_lap_frac", "fresh_a"]
CLASSES = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 8, 7: 11, 8: 11}  # class -> wait used by the success model
MODELS = ("base_rate", "pitwall_style", "decision", "two_stage")


def wait_class(w):
    if pd.isna(w):
        return 8  # no stop
    w = int(w)
    return w if w <= 5 else (6 if w <= 10 else 7)


def logistic(**kw):
    return make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=2000, **kw))


def load(seasons) -> pd.DataFrame:
    dump = Dump(ROOT / "data" / "raw" / "jolpica-dump" / "csv")
    parts = []
    for s in seasons:
        rounds = development_rounds(dump) if s == 2026 else [int(r) for r in dump.schedule(s)["round"]]
        for r in rounds:
            race = dump.race(s, r)
            d = open_duels(race)
            if d.empty:
                continue
            codes = {dump.driver_codes[x]: x for x in race.results["driver"]}
            life = join(race, parse(ROOT / "data" / "raw" / "tracinginsights" / str(s) / f"{r:02d}.json"), codes)
            life = life.set_index(["driver", "lap"])["life"]
            d["life_a_new"] = [life.get((a, la + 1), np.nan) for a, la in zip(d["a"], d["lap_a"])]
            parts.append(d)
    d = pd.concat(parts, ignore_index=True)
    d["age_diff"] = d["age_b"] - d["age_a"]
    d["log_remaining"] = np.log(d["remaining_laps"].clip(lower=1))
    d["fresh_a"] = (d["life_a_new"] == 1).astype(float)
    d["wait"] = d["lap_b"] - d["lap_a"]
    d["cls"] = d["wait"].map(wait_class)
    d["wait_capped"] = d["cls"].map(CLASSES).where(d["cls"] < 8, 11)
    d["no_stop"] = (d["cls"] == 8).astype(float)
    d["race"] = d["season"].astype(str) + "-" + d["round"].astype(str)
    return d


def predict(train, test):
    y = train["a_ahead"].astype(int)
    out = {"base_rate": np.full(len(test), y.mean())}
    for name, cols in (("pitwall_style", PITWALL), ("decision", DECISION)):
        out[name] = logistic().fit(train[cols], y).predict_proba(test[cols])[:, 1]
    succ_cols = [*DECISION, "wait_capped", "no_stop"]
    succ = logistic().fit(train[succ_cols], y)
    resp = logistic().fit(train[DECISION], train["cls"])
    pc = resp.predict_proba(test[DECISION])
    two = np.zeros(len(test))
    for k, c in enumerate(resp.classes_):
        x = test[succ_cols].copy()
        x["wait_capped"] = CLASSES[int(c)]
        x["no_stop"] = float(c == 8)
        two += pc[:, k] * succ.predict_proba(x)[:, 1]
    out["two_stage"] = two
    return out, succ, resp


def scores(p, y):
    base = float(((p["base_rate"] - y) ** 2).mean())
    return {
        m: {
            "log_loss": float(logloss(p[m], y).mean()),
            "brier": float(((p[m] - y) ** 2).mean()),
            "bss": 1 - float(((p[m] - y) ** 2).mean()) / base,
        }
        for m in MODELS
    }


def main() -> None:
    d_all = load(range(2018, 2027))
    d = d_all.dropna(subset=["life_a_new"]).reset_index(drop=True)
    train, test = d[d["season"] <= 2023], d[d["season"].isin([2024, 2025])]
    p, succ, _ = predict(train, test)
    y = test["a_ahead"].astype(int).to_numpy()
    s_test = scores(p, y)
    o2 = dm_block_bootstrap(logloss(p["two_stage"], y), logloss(p["pitwall_style"], y), test["race"].to_numpy())

    dev = d[(d["season"] == 2026) & (d["round"] >= 4)]
    p26, _, _ = predict(d[d["season"] <= 2025], dev)
    y26 = dev["a_ahead"].astype(int).to_numpy()

    pw = logistic().fit(train[PITWALL], train["a_ahead"].astype(int))
    rules = {
        "O1_test_scores": s_test,
        "O1_base_rate_test": float(y.mean()),
        "O2_dm_two_stage_vs_pitwall_style": o2,
        "O2_pass": bool(s_test["two_stage"]["log_loss"] < s_test["pitwall_style"]["log_loss"] and o2["p_value"] < 0.05),
        "O3_2026_scores": scores(p26, y26),
        "O3_n": len(dev),
    }
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True)
    out = {
        "spec": "10-undercut-open-events",
        "commit": sha.stdout.strip(),
        "counts": {
            "all": len(d_all),
            "with_tyre_life": len(d),
            "train": len(train),
            "test": len(test),
            "by_season": d.groupby("season").size().to_dict(),
        },
        "rules": rules,
        "coefficients_standardised": {
            "pitwall_style": dict(zip(PITWALL, pw[-1].coef_[0].round(4).tolist())),
            "two_stage_success": dict(zip([*DECISION, "wait_capped", "no_stop"], succ[-1].coef_[0].round(4).tolist())),
        },
    }
    (ROOT / "results" / "10-undercut-open-events.json").write_text(json.dumps(out, indent=2, default=float))
    print(json.dumps(out, indent=2, default=float))


if __name__ == "__main__":
    main()
