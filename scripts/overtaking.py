"""Spec 16: learned overtaking model.

Usage:
  PYTHONPATH=src .venv/bin/python scripts/overtaking.py          # development check: train 2018-2025, score 2026 r1-12
  PYTHONPATH=src .venv/bin/python scripts/overtaking.py --test   # once, after 2026-12-06: train 2018-2026 r12, score r19-23
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from pitwall.dump import Dump
from pitwall.overtake import Models, log_loss, pair_laps

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "derived" / "pair_laps.csv.gz"
TEST_ROUNDS = [19, 20, 21, 22, 23]
TEST_AFTER = date(2026, 12, 6)


def build(dump: Dump, races: list[tuple[int, int]], allow_holdout: bool = False) -> pd.DataFrame:
    parts = []
    for season, rnd in races:
        circuit = int(dump.schedule(season).set_index("round").loc[rnd, "circuit_id"])
        parts.append(pair_laps(dump.race(season, rnd, allow_holdout=allow_holdout), circuit))
    return pd.concat([p for p in parts if len(p)], ignore_index=True)


def dev_races(dump: Dump) -> list[tuple[int, int]]:
    out = [(s, int(r)) for s in range(2018, 2026) for r in dump.schedule(s)["round"]]
    return out + [(2026, r) for r in range(1, 13)]


def score(df: pd.DataFrame, preds: dict[str, np.ndarray]) -> dict:
    y = df["passed"].to_numpy()
    return {"pair_laps": len(df), "passes": int(y.sum()), **{k: {"log_loss": log_loss(y, p)} for k, p in preds.items()}}


def commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true")
    args = ap.parse_args()
    dump = Dump(ROOT / "data" / "raw" / "jolpica-dump" / "csv")
    if CACHE.exists():
        dev = pd.read_csv(CACHE)
    else:
        dev = build(dump, dev_races(dump))
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        dev.to_csv(CACHE, index=False)
    print("pair-laps", len(dev), "passes", int(dev["passed"].sum()), flush=True)

    if not args.test:
        train, test = dev[dev["season"] < 2026], dev[dev["season"] == 2026]
        m = Models(train)
        res = score(test, m.predict(test))
        imp = dict(zip(m.gbm.feature_name_, m.gbm.booster_.feature_importance("gain").round(1).tolist()))
        out = {
            "spec": "16-overtaking",
            "section": "5 development check: train 2018-2025, score 2026 rounds 1-12",
            "commit": commit(),
            "train": {"pair_laps": len(train), "pass_rate": float(train["passed"].mean())},
            "dev": res,
            "logit_coef": dict(
                zip(
                    ["gap", "drs", "pace_delta", "tyre_age_diff", "circuit_rate", "race_frac"],
                    m.logit.coef_[0].round(4).tolist(),
                )
            ),
            "gbm_gain": imp,
        }
        (ROOT / "results" / "16-overtaking-dev.json").write_text(json.dumps(out, indent=2))
        print(json.dumps(out, indent=2))
        return

    if date.today() <= TEST_AFTER:
        raise SystemExit(f"spec 16 test runs after {TEST_AFTER}")
    path = ROOT / "results" / "16-overtaking-test.json"
    if path.exists():
        raise SystemExit("spec 16 test already ran; it runs once")
    test = build(dump, [(2026, r) for r in TEST_ROUNDS], allow_holdout=True)
    m = Models(dev)
    preds = m.predict(test)
    res = score(test, preds)
    y, keys = test["passed"].to_numpy(), test["round"].to_numpy()
    races = np.unique(keys)
    rng = np.random.default_rng(0)
    diffs = []
    for _ in range(10_000):
        idx = np.concatenate([np.flatnonzero(keys == r) for r in rng.choice(races, len(races))])
        diffs.append(log_loss(y[idx], preds["sim_rule"][idx]) - log_loss(y[idx], preds["gbm"][idx]))
    ci = [float(np.quantile(diffs, 0.025)), float(np.quantile(diffs, 0.975))]
    rules = {
        "O1_pass": res["gbm"]["log_loss"] < res["sim_rule"]["log_loss"],
        "O2_pass": res["gbm"]["log_loss"] < res["base"]["log_loss"],
        "O3_ci": ci,
        "O3_pass": ci[0] > 0,
    }
    out = {"spec": "16-overtaking", "section": "5 test", "commit": commit(), "test": res, "rules": rules}
    path.write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
