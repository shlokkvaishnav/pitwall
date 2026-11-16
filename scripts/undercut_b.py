"""Spec 08: undercut with tyre compounds and a decision-time model.

Usage: PYTHONPATH=src .venv/bin/python scripts/undercut_b.py
Writes results/08-undercut-b.json.
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
from pitwall.lapmodel import PRETRAIN_SEASONS, development_rounds
from pitwall.tyres import join, parse
from pitwall.undercut import duels

ROOT = Path(__file__).resolve().parents[1]
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


def load() -> pd.DataFrame:
    dump = Dump(ROOT / "data" / "raw" / "jolpica-dump" / "csv")
    parts = []
    for s in (*PRETRAIN_SEASONS, 2026):
        rounds = development_rounds(dump) if s == 2026 else [int(r) for r in dump.schedule(s)["round"]]
        for r in rounds:
            race = dump.race(s, r)
            d = duels(race)
            if d.empty:
                continue
            codes = {dump.driver_codes[x]: x for x in race.results["driver"]}
            j = join(race, parse(ROOT / "data" / "raw" / "tracinginsights" / str(s) / f"{r:02d}.json"), codes)
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


def scores(df):
    y = df["a_ahead"].astype(int).to_numpy()
    base_brier = float(((df["p_base_rate"] - y) ** 2).mean())
    out = {}
    for m in MODELS:
        p = df[f"p_{m}"].to_numpy()
        brier = float(((p - y) ** 2).mean())
        out[m] = {"log_loss": float(logloss(p, y).mean()), "brier": brier, "bss": 1 - brier / base_brier}
    out["response_accuracy"] = float(df["p__response_acc"].mean())
    return out


def dm(df, a, b):
    y = df["a_ahead"].astype(int).to_numpy()
    return dm_block_bootstrap(logloss(df[f"p_{a}"], y), logloss(df[f"p_{b}"], y), df["race"].to_numpy())


def main() -> None:
    d = load()
    n_all = len(d)
    d = d.dropna(subset=["compound_step"]).reset_index(drop=True)
    pre, dev = d[d["season"] < 2026], d[d["season"] == 2026]

    loso = []
    for s in PRETRAIN_SEASONS:
        test = pre[pre["season"] == s]
        p = predict(pre[pre["season"] != s], test)
        loso.append(test.assign(**{f"p_{k}": v for k, v in p.items()}))
    loso = pd.concat(loso)

    wf = []
    for k in sorted(dev.loc[dev["round"] >= 4, "round"].unique()):
        test = dev[dev["round"] == k]
        p = predict(pd.concat([pre, dev[dev["round"] < k]]), test)
        wf.append(test.assign(**{f"p_{m}": v for m, v in p.items()}))
    wf = pd.concat(wf)

    s1, s2 = scores(loso), scores(wf)
    c1, w1 = dm(loso, "full_c", "full07"), dm(loso, "two_stage", "base_rate")
    t1 = dm(wf, "two_stage", "base_rate")
    rules = {
        "LOSO_scores": s1,
        "C1_dm": c1,
        "C1_pass": bool(s1["full_c"]["log_loss"] < s1["full07"]["log_loss"] and c1["p_value"] < 0.05),
        "W1_dm": w1,
        "W1_pass": bool(s1["two_stage"]["log_loss"] < s1["base_rate"]["log_loss"] and w1["p_value"] < 0.05),
        "W2_two_stage_vs_direct": dm(loso, "two_stage", "direct"),
        "W2_two_stage_vs_full_c": dm(loso, "two_stage", "full_c"),
        "T1_scores": s2,
        "T1_dm": t1,
        "T1_pass": bool(s2["two_stage"]["log_loss"] < s2["base_rate"]["log_loss"]),
    }
    coef = {}
    for name, cols in (("full_c", FULL_C), ("direct", DIRECT)):
        m = logistic().fit(pre[cols], pre["a_ahead"].astype(int))
        coef[name] = dict(zip(cols, m[-1].coef_[0].round(4).tolist()))
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True)
    out = {
        "spec": "08-undercut-b",
        "commit": sha.stdout.strip(),
        "counts": {"all_duels": n_all, "with_compounds": len(d), "loso": len(loso), "t1": len(wf)},
        "compound_step_counts": d["compound_step"].value_counts().sort_index().to_dict(),
        "rules": rules,
        "coefficients_2022_2025_standardised": coef,
    }
    (ROOT / "results" / "08-undercut-b.json").write_text(json.dumps(out, indent=2, default=float))
    print(json.dumps(out, indent=2, default=float))


if __name__ == "__main__":
    main()
