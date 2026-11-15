"""Spec 04: is there a hidden energy regime in 2026 lap-time residuals?

Usage: PYTHONPATH=src .venv/bin/python scripts/energy_regime.py
Writes results/04-energy-regime.json.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from pitwall.dump import Dump
from pitwall.evaluate import dm_block_bootstrap
from pitwall.hmm import fit, fit_ar1, predict_next
from pitwall.lapmodel import (
    development_rounds,
    loso_residuals,
    pretrain_features,
    race_features,
    stint_sequences,
    walk_forward_residuals,
)

ROOT = Path(__file__).resolve().parents[1]
KEYS = ["season", "round", "driver", "stint"]


def corrections(test: pd.DataFrame, hmm, phi: float) -> pd.DataFrame:
    test = test.sort_values([*KEYS, "lap"]).copy()
    test["corr_hmm2"] = np.nan
    test["corr_ar1"] = np.nan
    for _, g in test.groupby(KEYS, sort=False):
        r = g["resid"].to_numpy()
        test.loc[g.index, "corr_hmm2"] = predict_next(r, hmm)
        test.loc[g.index, "corr_ar1"] = phi * np.concatenate([[0.0], r[:-1]])
    return test


def bootstrap_separation(df: pd.DataFrame, base, n: int, rng) -> np.ndarray:
    races = df[["season", "round"]].drop_duplicates().to_numpy()
    groups = {tuple(k): g for k, g in df.groupby(["season", "round"])}
    out = np.empty(n)
    for i in range(n):
        pick = races[rng.integers(0, len(races), len(races))]
        seqs = [s for k in pick for s in stint_sequences(groups[tuple(k)])]
        out[i] = fit(seqs, init=base)[0].separation()
    return out


def main() -> None:
    dump = Dump(ROOT / "data" / "raw" / "jolpica-dump" / "csv")
    pre = pretrain_features(dump)
    dev = {r: race_features(dump, 2026, r) for r in development_rounds(dump)}
    wf = walk_forward_residuals(pre, dev)
    loso = loso_residuals(pre)
    print("residuals ready", len(wf), len(loso), flush=True)

    scored = []
    for k in [r for r in sorted(dev) if r >= 4]:
        train = wf[wf["round"] < k]
        hmm, _ = fit(stint_sequences(train), seed=0)
        phi = fit_ar1(stint_sequences(train))
        scored.append(corrections(wf[wf["round"] == k], hmm, phi))
    s = pd.concat(scored, ignore_index=True)
    err = {
        "none": s["resid"].to_numpy(),
        "ar1": (s["resid"] - s["corr_ar1"]).to_numpy(),
        "hmm2": (s["resid"] - s["corr_hmm2"]).to_numpy(),
    }
    mae = {k: float(np.abs(v).mean()) for k, v in err.items()}
    dm_none = dm_block_bootstrap(err["hmm2"], err["none"], s["round"])
    dm_ar1 = dm_block_bootstrap(err["hmm2"], err["ar1"], s["round"])

    hmm26, _ = fit(stint_sequences(wf), seed=0)
    hmm_pre, _ = fit(stint_sequences(loso), seed=0)
    rng = np.random.default_rng(0)
    b26 = bootstrap_separation(wf, hmm26, 2000, rng)
    bpre = bootstrap_separation(loso, hmm_pre, 2000, rng)
    diff = b26 - bpre
    ci = np.quantile(diff, [0.025, 0.975]).tolist()
    rules = {
        "E1_pass": bool(mae["hmm2"] < mae["none"] and dm_none["p_value"] < 0.05),
        "E1_dm": dm_none,
        "E2_pass": bool(mae["hmm2"] < mae["ar1"] and dm_ar1["p_value"] < 0.05),
        "E2_dm": dm_ar1,
        "E3_separation_2026": hmm26.separation(),
        "E3_separation_2022_2025": hmm_pre.separation(),
        "E3_diff_ci95": ci,
        "E3_pass": bool(hmm26.separation() > hmm_pre.separation() and ci[0] > 0),
    }
    rules["energy_regime_claim"] = bool(rules["E1_pass"] and rules["E2_pass"] and rules["E3_pass"])
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True)
    out = {
        "spec": "04-energy-regime",
        "commit": sha.stdout.strip(),
        "n_test_laps": len(s),
        "pooled_mae_s": mae,
        "rules": rules,
        "hmm_2026": hmm26.as_dict(),
        "hmm_2022_2025": hmm_pre.as_dict(),
        "residual_sd_s": {"2026": float(wf["resid"].std()), "2022_2025": float(loso["resid"].std())},
    }
    (ROOT / "results" / "04-energy-regime.json").write_text(json.dumps(out, indent=2))
    print(json.dumps({k: out[k] for k in ("pooled_mae_s", "rules", "hmm_2026", "hmm_2022_2025")}, indent=2))


if __name__ == "__main__":
    main()
