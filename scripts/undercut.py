"""Spec 07: when does an undercut work?

Usage: PYTHONPATH=src .venv/bin/python scripts/undercut.py
Writes results/07-undercut.json.
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
from pitwall.undercut import duels

ROOT = Path(__file__).resolve().parents[1]
FULL = ["gap_s", "wait_laps", "age_diff", "race_lap_frac"]
EPS = 1e-6


def logloss(p, y):
    p = np.clip(p, EPS, 1 - EPS)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def predict(train: pd.DataFrame, test: pd.DataFrame) -> dict[str, np.ndarray]:
    y = train["a_ahead"].astype(int)
    out = {"base_rate": np.full(len(test), y.mean())}
    for name, cols in (("gap_only", ["gap_s"]), ("full", FULL)):
        m = make_pipeline(StandardScaler(), LogisticRegression(C=1.0))
        m.fit(train[cols], y)
        out[name] = m.predict_proba(test[cols])[:, 1]
    return out


def summary(preds, test):
    y = test["a_ahead"].astype(int).to_numpy()
    return {
        k: {"log_loss": float(logloss(p, y).mean()), "brier": float(((p - y) ** 2).mean())} for k, p in preds.items()
    }


def main() -> None:
    dump = Dump(ROOT / "data" / "raw" / "jolpica-dump" / "csv")
    parts = []
    for s in (*PRETRAIN_SEASONS, 2026):
        rounds = development_rounds(dump) if s == 2026 else [int(r) for r in dump.schedule(s)["round"]]
        parts += [duels(dump.race(s, r)) for r in rounds]
    d = pd.concat(parts, ignore_index=True)
    d["age_diff"] = d["age_b"] - d["age_a"]
    d["race"] = d["season"].astype(str) + "-" + d["round"].astype(str)
    pre, dev = d[d["season"] < 2026], d[d["season"] == 2026]
    counts = d.groupby("season").size().to_dict()

    # U1: leave-one-season-out on 2022-2025
    loso = []
    for s in PRETRAIN_SEASONS:
        test = pre[pre["season"] == s]
        p = predict(pre[pre["season"] != s], test)
        loso.append(test.assign(**{f"p_{k}": v for k, v in p.items()}))
    loso = pd.concat(loso)
    y = loso["a_ahead"].astype(int).to_numpy()
    u1 = dm_block_bootstrap(logloss(loso["p_full"], y), logloss(loso["p_base_rate"], y), loso["race"].to_numpy())

    # U2: walk-forward on 2026 rounds 4-12
    wf = []
    for k in sorted(dev.loc[dev["round"] >= 4, "round"].unique()):
        train = pd.concat([pre, dev[dev["round"] < k]])
        test = dev[dev["round"] == k]
        p = predict(train, test)
        wf.append(test.assign(**{f"p_{m}": v for m, v in p.items()}))
    wf = pd.concat(wf)
    y2 = wf["a_ahead"].astype(int).to_numpy()
    u2 = dm_block_bootstrap(logloss(wf["p_full"], y2), logloss(wf["p_base_rate"], y2), wf["race"].to_numpy())

    # U3: success rate 2026 minus 2022-2025, bootstrap by race
    rng = np.random.default_rng(0)
    rate = lambda x: x["a_ahead"].mean()
    diff = rate(dev) - rate(pre)
    races_pre = [g for _, g in pre.groupby("race")]
    races_dev = [g for _, g in dev.groupby("race")]
    boot = []
    for _ in range(2000):
        bp = pd.concat([races_pre[i] for i in rng.integers(0, len(races_pre), len(races_pre))])
        bd = pd.concat([races_dev[i] for i in rng.integers(0, len(races_dev), len(races_dev))])
        boot.append(rate(bd) - rate(bp))
    lo, hi = np.quantile(boot, [0.025, 0.975])

    final = make_pipeline(StandardScaler(), LogisticRegression(C=1.0)).fit(pre[FULL], pre["a_ahead"].astype(int))
    coef = dict(zip(FULL, final[-1].coef_[0].round(4).tolist()))

    s1 = summary({k: loso[f"p_{k}"].to_numpy() for k in ("base_rate", "gap_only", "full")}, loso)
    s2 = summary({k: wf[f"p_{k}"].to_numpy() for k in ("base_rate", "gap_only", "full")}, wf)
    rules = {
        "U1_scores": s1,
        "U1_dm": u1,
        "U1_pass": bool(s1["full"]["log_loss"] < s1["base_rate"]["log_loss"] and u1["p_value"] < 0.05),
        "U2_scores": s2,
        "U2_dm": u2,
        "U2_pass": bool(s2["full"]["log_loss"] < s2["base_rate"]["log_loss"]),
        "U3_rate_2026": float(rate(dev)),
        "U3_rate_2022_2025": float(rate(pre)),
        "U3_diff": float(diff),
        "U3_ci95": [float(lo), float(hi)],
    }
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True)
    out = {
        "spec": "07-undercut",
        "commit": sha.stdout.strip(),
        "counts": {str(k): int(v) for k, v in counts.items()},
        "n_u2": len(wf),
        "rules": rules,
        "coefficients_full_2022_2025_standardised": coef,
    }
    (ROOT / "results" / "07-undercut.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
