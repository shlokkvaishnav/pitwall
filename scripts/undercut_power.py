"""Spec 13 power analysis: how many undercut events the U1 + U2 test of spec 11 needs.

We resample whole development races (with their real outcomes and out-of-sample model probabilities) until we
have n events, and apply the spec 11 rules: U1 Brier skill > 0 against the training base rate, and U2 one-sided
block-bootstrap test by race on log loss, p < 0.05. Power = fraction of simulations where both pass.

Scenarios (development data only, no holdout race is loaded):
  bss_2024_25  model trained on 2018 to 2023, events of 2024 and 2025 (spec 10, O1: BSS 0.22)
  bss_2026_dev model trained on 2018 to 2025, events of 2026 rounds 4 to 12 (spec 10, O3: BSS 0.11)
  no_skill     the 2024 to 2025 events with the outcomes shuffled (false-positive check; should be about 5% or less)

Usage: PYTHONPATH=src .venv/bin/python scripts/undercut_power.py
Writes results/13-undercut-power.json.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import undercut_open as uo

from pitwall.evaluate import dm_block_bootstrap
from pitwall.undercut_models import logloss

ROOT = Path(__file__).resolve().parents[1]
SIZES = [20, 40, 60, 80, 100, 120, 150, 200, 250]
N_SIM = 2000
N_BOOT = 2000  # inside each simulation; spec 11 uses 10,000 for the real test
SEED = 0


def scenario(train: pd.DataFrame, test: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    model = uo.logistic().fit(train[uo.PITWALL], train["a_ahead"].astype(int))
    out = test[["race", "a_ahead"]].copy()
    out["y"] = out["a_ahead"].astype(int)
    out["p"] = model.predict_proba(test[uo.PITWALL])[:, 1]
    return out[["race", "y", "p"]].reset_index(drop=True), float(train["a_ahead"].mean())


def one_test(y: np.ndarray, p: np.ndarray, races: np.ndarray, base: float, seed: int) -> tuple[bool, float]:
    bss = 1 - ((p - y) ** 2).mean() / ((base - y) ** 2).mean()
    dm = dm_block_bootstrap(logloss(p, y), logloss(np.full(len(y), base), y), races, n_boot=N_BOOT, seed=seed)
    return bool(bss > 0 and dm["p_value"] < 0.05), float(bss)


def power(ev: pd.DataFrame, base: float, n: int, rng: np.random.Generator, shuffle: bool = False) -> dict:
    blocks = [g for _, g in ev.groupby("race")]
    passes, bsss = 0, []
    for i in range(N_SIM):
        parts, count, k = [], 0, 0
        while count < n:  # whole races, drawn with replacement, until n events
            g = blocks[rng.integers(len(blocks))]
            parts.append(g.assign(block=k))
            count += len(g)
            k += 1
        s = pd.concat(parts, ignore_index=True).iloc[:n]
        y = s["y"].to_numpy()
        if shuffle:
            y = rng.permutation(y)
        ok, bss = one_test(y, s["p"].to_numpy(), s["block"].to_numpy(), base, seed=i)
        passes += ok
        bsss.append(bss)
    b = np.array(bsss)
    return {
        "n_events": n,
        "power": passes / N_SIM,
        "bss_median": float(np.median(b)),
        "bss_p05": float(np.quantile(b, 0.05)),
        "bss_p95": float(np.quantile(b, 0.95)),
        "share_bss_le_0": float((b <= 0).mean()),
    }


def main() -> None:
    d = uo.load(range(2018, 2027)).dropna(subset=["life_a_new"]).reset_index(drop=True)  # 2026: development only
    assert set(d.loc[d["season"] == 2026, "round"]) <= set(range(1, 13))
    a, base_a = scenario(d[d["season"] <= 2023], d[d["season"].isin([2024, 2025])])
    b, base_b = scenario(d[d["season"] <= 2025], d[(d["season"] == 2026) & (d["round"] >= 4)])
    rng = np.random.default_rng(SEED)
    scen = {
        "bss_2024_25": (a, base_a, False),
        "bss_2026_dev": (b, base_b, False),
        "no_skill": (a, base_a, True),
    }
    out_s = {}
    for name, (ev, base, shuffle) in scen.items():
        full_bss = 1 - ((ev["p"] - ev["y"]) ** 2).mean() / ((base - ev["y"]) ** 2).mean()
        rows = [power(ev, base, n, rng, shuffle) for n in SIZES]
        print(name, [(r["n_events"], r["power"]) for r in rows], flush=True)
        out_s[name] = {
            "events": len(ev),
            "races": int(ev["race"].nunique()),
            "events_per_race": len(ev) / ev["race"].nunique(),
            "train_base_rate": base,
            "bss_all_events": float(full_bss) if not shuffle else None,
            "power_by_n": rows,
        }
    dev26 = d[d["season"] == 2026]
    need = next((r["n_events"] for r in out_s["bss_2024_25"]["power_by_n"] if r["power"] >= 0.8), None)
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True)
    out = {
        "spec": "13-out-of-sample-rounds (power analysis)",
        "commit": sha.stdout.strip(),
        "n_sim": N_SIM,
        "n_boot": N_BOOT,
        "seed": SEED,
        "test": "U1 BSS > 0 and U2 block-bootstrap p < 0.05 (spec 11)",
        "scenarios": out_s,
        "n_for_80_power_bss_2024_25": need,
        "events_2026_development_rounds_1_12": len(dev26),
        "events_per_race_2026_development": len(dev26) / 12,
        "events_per_race_2026_holdout_spec11": 20 / 6,  # results/11-holdout.json: 20 events in the 6 locked races
    }
    (ROOT / "results" / "13-undercut-power.json").write_text(json.dumps(out, indent=2))
    print(json.dumps({k: v for k, v in out.items() if k != "scenarios"}, indent=2))


if __name__ == "__main__":
    main()
