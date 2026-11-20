"""Spec 12: split conformal intervals for the lap-time model, on the 2026 development races only.

Usage: PYTHONPATH=src .venv/bin/python scripts/lap_intervals.py
Writes results/12-lap-intervals.json and site/data/lap-replay.json. No holdout race is loaded.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from pitwall.dump import Dump
from pitwall.intervals import conformal_offsets, coverage
from pitwall.lapmodel import development_rounds, fit_predict, pretrain_features, race_features, walk_forward_residuals
from pitwall.splits import assert_not_holdout

ROOT = Path(__file__).resolve().parents[1]
TEST_ROUNDS = list(range(4, 13))
ALPHAS = {"80": 0.20, "95": 0.05}
REPLAY_ROUND = 12  # spec 12, section 5: the last development race, chosen before the run


def interval_table(test: pd.DataFrame, cal: dict[int, np.ndarray]) -> pd.DataFrame:
    """Add lo/hi columns for each level, with the calibration residuals cal[round]."""
    out = []
    for k, g in test.groupby("round"):
        g = g.copy()
        for name, a in ALPHAS.items():
            lo, hi = conformal_offsets(cal[int(k)], a)
            g[f"lo{name}"], g[f"hi{name}"] = g["pred"] + lo, g["pred"] + hi
            g[f"off{name}"] = [(lo, hi)] * len(g)
        out.append(g)
    return pd.concat(out, ignore_index=True)


def summary(t: pd.DataFrame) -> dict:
    res: dict = {"laps": len(t)}
    for name in ALPHAS:
        res[f"coverage_{name}"] = coverage(t["time_s"], t[f"lo{name}"], t[f"hi{name}"])
        res[f"mean_width_{name}_s"] = float((t[f"hi{name}"] - t[f"lo{name}"]).mean())
    return res


def main() -> None:
    dump = Dump(ROOT / "data" / "raw" / "jolpica-dump" / "csv")
    dev_rounds = development_rounds(dump)
    sched = dump.schedule(2026).set_index("round")
    assert_not_holdout([sched.loc[r, "date"] for r in dev_rounds])  # development rounds only (spec 12)
    assert set(TEST_ROUNDS) <= set(dev_rounds)

    pre = pretrain_features(dump)
    dev = {r: race_features(dump, 2026, r) for r in dev_rounds}
    wf = walk_forward_residuals(pre, dev)
    print("walk-forward rows", len(wf), flush=True)

    # static_2025: one model trained on 2022 to 2024, residuals on all 2025 races
    pred25, _ = fit_predict(pre[pre["season"] < 2025], pre[pre["season"] == 2025])
    resid25 = pre.loc[pre["season"] == 2025, "time_s"].to_numpy() - pred25

    test = wf[wf["round"].isin(TEST_ROUNDS)].copy()
    rolling_cal = {k: wf.loc[wf["round"] < k, "resid"].to_numpy() for k in TEST_ROUNDS}
    static_cal = {k: resid25 for k in TEST_ROUNDS}
    roll = interval_table(test, rolling_cal)
    stat = interval_table(test, static_cal)

    per_race = []
    for k in TEST_ROUNDS:
        g = roll[roll["round"] == k]
        rec = {"round": k, "name": sched.loc[k, "name"], "calibration_laps": int(rolling_cal[k].size), **summary(g)}
        for name in ALPHAS:
            rec[f"offsets_{name}_s"] = list(g[f"off{name}"].iloc[0])
        rec["static_2025_coverage_80"] = summary(stat[stat["round"] == k])["coverage_80"]
        per_race.append(rec)

    pooled = summary(roll)
    groups = {
        "ahead_lt_1s": summary(roll[roll["ahead_lt_1s"] == 1.0]),
        "not_ahead_lt_1s": summary(roll[roll["ahead_lt_1s"] != 1.0]),
        "tyre_age_gt_20": summary(roll[roll["tyre_age"] > 20]),
        "tyre_age_le_20": summary(roll[roll["tyre_age"] <= 20]),
    }
    races_ok = sum(r["coverage_80"] >= 0.70 for r in per_race)
    rules = {
        "C1_coverage_80": pooled["coverage_80"],
        "C1_pass": bool(0.77 <= pooled["coverage_80"] <= 0.83),
        "C2_coverage_95": pooled["coverage_95"],
        "C2_pass": bool(0.93 <= pooled["coverage_95"] <= 0.97),
        "C3_races_with_80_coverage_at_least_70": races_ok,
        "C3_pass": bool(races_ok >= 7),
    }
    rules["pass"] = bool(rules["C1_pass"] and rules["C2_pass"] and rules["C3_pass"])

    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True)
    out = {
        "spec": "12-lap-intervals",
        "commit": sha.stdout.strip(),
        "test_rounds": TEST_ROUNDS,
        "point_mae_s": float(test["resid"].abs().mean()),
        "rules": rules,
        "rolling": pooled,
        "static_2025": {
            **summary(stat),
            "calibration_laps": int(resid25.size),
            **{f"offsets_{n}_s": list(conformal_offsets(resid25, a)) for n, a in ALPHAS.items()},
        },
        "groups_rolling": groups,
        "races": per_race,
    }
    (ROOT / "results" / "12-lap-intervals.json").write_text(json.dumps(out, indent=2))
    print(json.dumps({k: out[k] for k in ("point_mae_s", "rules", "rolling")}, indent=2))
    write_replay(dump, roll[roll["round"] == REPLAY_ROUND], sched.loc[REPLAY_ROUND, "name"])


def write_replay(dump: Dump, t: pd.DataFrame, name: str) -> None:
    """site/data/lap-replay.json: the clean laps of the first three classified drivers (spec 12, section 5)."""
    res = dump.race(2026, REPLAY_ROUND).results
    top = res[res["classified"] & res["position"].isin([1, 2, 3])].sort_values("position")
    codes = dump.driver_codes
    drivers = []
    for _, row in top.iterrows():
        g = t[t["driver"] == row["driver"]].sort_values("lap")
        drivers.append(
            {
                "code": str(codes.get(row["driver"], row["driver"])),
                "position": int(row["position"]),
                "laps": [
                    [int(r.lap), round(float(r.time_s), 3), round(float(r.pred), 3), round(float(r.lo80), 3),
                     round(float(r.hi80), 3), int(r.stint)]
                    for r in g.itertuples()
                ],
            }
        )  # fmt: skip
    rec = {
        "race": f"2026 {name}",
        "round": REPLAY_ROUND,
        "level": 0.8,
        "columns": ["lap", "actual_s", "forecast_s", "lo80_s", "hi80_s", "stint"],
        "coverage_80": coverage(t["time_s"], t["lo80"], t["hi80"]),
        "drivers": drivers,
    }
    (ROOT / "site" / "data" / "lap-replay.json").write_text(json.dumps(rec, separators=(",", ":")))


if __name__ == "__main__":
    main()
