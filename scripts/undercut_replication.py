"""Spec 09: replicate the decision-time undercut model on 2018 to 2021.

Usage: PYTHONPATH=src .venv/bin/python scripts/undercut_replication.py
Writes results/09-undercut-replication.json.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np

from pitwall.evaluate import dm_block_bootstrap
from pitwall.lapmodel import PRETRAIN_SEASONS
from pitwall.undercut_models import MODELS, load, logloss, predict

ROOT = Path(__file__).resolve().parents[1]
EARLY = (2018, 2019, 2020, 2021)


def main() -> None:
    train = load(ROOT, PRETRAIN_SEASONS).dropna(subset=["compound_step"])
    test_all = load(ROOT, EARLY)
    test = test_all.dropna(subset=["compound_step"]).reset_index(drop=True)
    p = predict(train, test)
    y = test["a_ahead"].astype(int).to_numpy()
    base_brier = float(((p["base_rate"] - y) ** 2).mean())
    scores = {}
    for m in MODELS:
        brier = float(((p[m] - y) ** 2).mean())
        scores[m] = {"log_loss": float(logloss(p[m], y).mean()), "brier": brier, "bss": 1 - brier / base_brier}
    groups = test["race"].to_numpy()
    w1 = dm_block_bootstrap(logloss(p["two_stage"], y), logloss(p["base_rate"], y), groups)
    f = dm_block_bootstrap(logloss(p["full_c"], y), logloss(p["base_rate"], y), groups)
    rules = {
        "scores": scores,
        "R9_W1_dm": w1,
        "R9_W1_pass": bool(scores["two_stage"]["log_loss"] < scores["base_rate"]["log_loss"] and w1["p_value"] < 0.05),
        "R9_F_full_c_dm": f,
        "response_accuracy": float(np.mean(p["_response_acc"])),
        "success_rate_test": float(y.mean()),
        "success_rate_train": float(train["a_ahead"].mean()),
    }
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True)
    out = {
        "spec": "09-undercut-replication",
        "commit": sha.stdout.strip(),
        "counts": {
            "train": len(train),
            "test_all": len(test_all),
            "test_with_compounds": len(test),
            "test_by_season": test.groupby("season").size().to_dict(),
        },
        "rules": rules,
    }
    (ROOT / "results" / "09-undercut-replication.json").write_text(json.dumps(out, indent=2, default=float))
    print(json.dumps(out, indent=2, default=float))


if __name__ == "__main__":
    main()
