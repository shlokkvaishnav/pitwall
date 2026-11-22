"""Spec 17: causal transformer (`seq`) against `gbm_pretrain`, walk-forward over 2026 rounds 4 to 12 (development).

Usage: PYTHONPATH=src .venv/bin/python scripts/deep_lap_model.py   (needs the `deep` extra: torch)
Writes results/17-deep-lap-dev.json. The test on rounds 19 to 23 is added with spec 13 in December.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import numpy as np
import pandas as pd

from pitwall.dump import Dump
from pitwall.lapmodel import development_rounds, fit_predict, pretrain_features, race_features

ROOT = Path(__file__).resolve().parents[1]
TEST_ROUNDS = list(range(4, 13))


def main() -> None:
    dump = Dump(ROOT / "data" / "raw" / "jolpica-dump" / "csv")
    pre = pretrain_features(dump)
    dev = {r: race_features(dump, 2026, r) for r in development_rounds(dump)}
    splits = {}
    for k in TEST_ROUNDS:  # all LightGBM fits first: LightGBM and torch must not run in the same phase on macOS
        train = pd.concat([pre, *[dev[r] for r in dev if r < k]], ignore_index=True)
        test = dev[k].reset_index(drop=True)
        gbm, _ = fit_predict(train, test)
        splits[k] = (train, test, gbm)
    import torch

    from pitwall.seqmodel import fit_predict_seq

    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    rows = []
    for k, (train, test, gbm) in splits.items():
        t0 = time.time()
        seq = fit_predict_seq(train, test, device)
        y = test["time_s"].to_numpy()
        rows.append(pd.DataFrame({"round": k, "err_gbm": np.abs(y - gbm), "err_seq": np.abs(y - seq)}))
        print(
            k,
            f"gbm {np.abs(y - gbm).mean():.3f} seq {np.abs(y - seq).mean():.3f}",
            f"{time.time() - t0:.0f} s",
            flush=True,
        )
    e = pd.concat(rows, ignore_index=True)
    rounds = np.array(TEST_ROUNDS)
    s = e.groupby("round")[["err_gbm", "err_seq"]].agg(["sum", "count"])
    rng = np.random.default_rng(0)
    diffs = []
    for _ in range(10_000):
        pick = rng.choice(rounds, len(rounds))
        g = s.loc[pick]
        n = g[("err_gbm", "count")].sum()
        diffs.append((g[("err_seq", "sum")].sum() - g[("err_gbm", "sum")].sum()) / n)
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    out = {
        "spec": "17-deep-lap-model",
        "section": "3 development comparison",
        "commit": sha,
        "laps": len(e),
        "mae_gbm_s": float(e["err_gbm"].mean()),
        "mae_seq_s": float(e["err_seq"].mean()),
        "diff_seq_minus_gbm_s": float(e["err_seq"].mean() - e["err_gbm"].mean()),
        "diff_95ci": [float(np.quantile(diffs, 0.025)), float(np.quantile(diffs, 0.975))],
        "races": e.groupby("round")[["err_gbm", "err_seq"]].mean().round(4).reset_index().to_dict("records"),
    }
    (ROOT / "results" / "17-deep-lap-dev.json").write_text(json.dumps(out, indent=2))
    print(json.dumps({k: v for k, v in out.items() if k != "races"}, indent=2))


if __name__ == "__main__":
    main()
