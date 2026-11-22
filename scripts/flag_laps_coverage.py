"""Spec 14, section 4 (exploratory): spec 12 `rolling` coverage when officially neutral laps are also removed.

Usage: PYTHONPATH=src .venv/bin/python scripts/flag_laps_coverage.py   (after scripts/flag_laps.py)
Same 2026 development rounds, model and method as scripts/lap_intervals.py. Adds `coverage` to results/flag_laps.json.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from lap_intervals import ALPHAS, TEST_ROUNDS, interval_table, summary

from pitwall.dump import Dump
from pitwall.flags import neutral_laps
from pitwall.lapmodel import development_rounds, pretrain_features, race_features, walk_forward_residuals

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "openf1"


def main() -> None:
    res_path = ROOT / "results" / "flag_laps.json"
    res = json.loads(res_path.read_text())
    official: dict[int, set[int]] = {}
    for r in res["races"]:
        if r["season"] == 2026:
            msgs = json.loads((RAW / f"race_control_{r['session_key']}.json").read_text())
            official[r["round"]] = set(neutral_laps(msgs, r["laps"]))

    dump = Dump(ROOT / "data" / "raw" / "jolpica-dump" / "csv")
    dev_rounds = development_rounds(dump)
    pre = pretrain_features(dump)
    dev = {r: race_features(dump, 2026, r) for r in dev_rounds}
    wf = walk_forward_residuals(pre, dev)
    assert "lap" in wf.columns
    flagged = np.array([lap in official.get(int(k), set()) for k, lap in zip(wf["round"], wf["lap"])])

    out = {}
    for name, keep in (("detector_only", np.ones(len(wf), bool)), ("official_removed", ~flagged)):
        w = wf[keep]
        test = w[w["round"].isin(TEST_ROUNDS)]
        cal = {k: w.loc[w["round"] < k, "resid"].to_numpy() for k in TEST_ROUNDS}
        t = interval_table(test, cal)
        out[name] = {**summary(t), "mae_s": float(test["resid"].abs().mean())}
    out["test_laps_removed"] = int((flagged & wf["round"].isin(TEST_ROUNDS).to_numpy()).sum())
    out["levels"] = list(ALPHAS)
    out["note"] = "exploratory: these 2026 races were used to develop spec 12"
    res["coverage"] = out
    res_path.write_text(json.dumps(res, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
