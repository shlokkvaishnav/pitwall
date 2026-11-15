"""Spec 03: walk-forward test of the next-lap-time model on the 2026 development races.

Usage: PYTHONPATH=src .venv/bin/python scripts/lap_model.py
Writes results/03-lap-model.json.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from pitwall.dump import Dump
from pitwall.evaluate import dm_block_bootstrap
from pitwall.features import FEATURES
from pitwall.lapmodel import PARAMS, development_rounds, fit_predict, pretrain_features, race_features

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    dump = Dump(ROOT / "data" / "raw" / "jolpica-dump" / "csv")
    pre = pretrain_features(dump)
    dev_rounds = development_rounds(dump)
    dev = {r: race_features(dump, 2026, r) for r in dev_rounds}
    print("pretrain rows", len(pre), "dev rows", sum(len(v) for v in dev.values()), flush=True)

    rows, importance = [], None
    for k in [r for r in dev_rounds if r >= 4]:
        earlier = pd.concat([dev[r] for r in dev_rounds if r < k], ignore_index=True)
        test = dev[k]
        pred_pre, model = fit_predict(pd.concat([pre, earlier], ignore_index=True), test)
        pred_26, _ = fit_predict(earlier, test)
        importance = dict(zip(FEATURES, model.booster_.feature_importance("gain").round(1).tolist()))
        y = test["time_s"].to_numpy()
        rows.append(
            pd.DataFrame(
                {
                    "round": k,
                    "err_previous_lap": test["last1"].to_numpy() - y,
                    "err_gbm_pretrain": pred_pre - y,
                    "err_gbm_2026": pred_26 - y,
                }
            )
        )
        print(k, {c: round(float(np.abs(rows[-1][c]).mean()), 3) for c in rows[-1].columns[1:]}, flush=True)

    allr = pd.concat(rows, ignore_index=True).dropna()
    mae = {c[4:]: float(allr[c].abs().mean()) for c in allr.columns if c.startswith("err_")}
    best = min(("gbm_pretrain", "gbm_2026"), key=mae.get)
    dm = dm_block_bootstrap(allr[f"err_{best}"], allr["err_previous_lap"], allr["round"])
    rules = {
        "best_candidate": best,
        "S1_ratio": mae[best] / mae["previous_lap"],
        "S1_pass": bool(mae[best] <= 0.95 * mae["previous_lap"]),
        "S2_dm": dm,
        "S2_pass": bool(dm["p_value"] < 0.05),
        "S3_pass": bool(mae["gbm_pretrain"] < mae["gbm_2026"]),
    }
    per_race = allr.groupby("round").agg(lambda s: float(s.abs().mean())).reset_index().to_dict("records")
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True)
    out = {
        "spec": "03-lap-model",
        "commit": sha.stdout.strip(),
        "params": PARAMS,
        "pooled_mae_s": mae,
        "rules": rules,
        "feature_importance_gain_last_fold": importance,
        "races": per_race,
    }
    (ROOT / "results" / "03-lap-model.json").write_text(json.dumps(out, indent=2))
    print(json.dumps({k: out[k] for k in ("pooled_mae_s", "rules")}, indent=2))


if __name__ == "__main__":
    main()
