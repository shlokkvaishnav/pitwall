"""Spec 15: per-lap hazard of a safety car, VSC or red-flag period.

Usage:
  PYTHONPATH=src .venv/bin/python scripts/sc_hazard.py          # section 4, leave-one-season-out on development races
  PYTHONPATH=src .venv/bin/python scripts/sc_hazard.py --test   # section 5, once, after 2026-12-06
Development races are the 80 of results/flag_laps.json (spec 14). Only --test fetches or loads 2026 rounds 13 to 23.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from flag_laps import API, RAW, get

from pitwall.dump import Dump
from pitwall.flags import neutral_laps
from pitwall.hazard import Models, any_event_prob, log_loss, race_rows
from pitwall.laps import lap_table

ROOT = Path(__file__).resolve().parents[1]
TEST_ROUNDS = list(range(13, 24))
TEST_AFTER = date(2026, 12, 6)


def commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


def dev_rows(dump: Dump) -> pd.DataFrame:
    res = json.loads((ROOT / "results" / "flag_laps.json").read_text())
    rows = []
    for r in res["races"]:
        msgs = json.loads((RAW / f"race_control_{r['session_key']}.json").read_text())
        circuit = int(dump.schedule(r["season"]).set_index("round").loc[r["round"], "circuit_id"])
        rows.append(
            race_rows(
                neutral_laps(msgs, r["laps"]), r["laps"], season=r["season"], round=r["round"], circuit_id=circuit
            )
        )
    return pd.concat(rows, ignore_index=True)


def score(t: pd.DataFrame, preds: dict[str, np.ndarray]) -> dict:
    y = t["event"].to_numpy()
    out = {"at_risk_laps": len(t), "events": int(y.sum()), "races": int(t.groupby(["season", "round"]).ngroups)}
    race_any = t.groupby(["season", "round"])["event"].max()
    for name, p in preds.items():
        brier = float(((any_event_prob(t, p) - race_any) ** 2).mean())
        out[name] = {"log_loss": log_loss(y, p), "race_any_brier": brier}
    return out


def loso(t: pd.DataFrame) -> dict:
    parts, preds = [], {"M0": [], "M1": [], "M2": []}
    for season in sorted(t["season"].unique()):
        tr, te = t[t["season"] != season], t[t["season"] == season]
        p = Models(tr).predict(te)
        parts.append(te)
        for k, acc in preds.items():
            acc.append(p[k])
    allt = pd.concat(parts)
    return score(allt, {k: np.concatenate(v) for k, v in preds.items()})


def kinds(t: pd.DataFrame) -> dict:
    ev = t[t["event"] == 1]
    return {
        "by_kind": ev["kind"].value_counts().to_dict(),
        "lap1_events": int((ev["lap"] == 1).sum()),
        "lap2_3_events": int(ev["lap"].isin([2, 3]).sum()),
    }


def test_rows(dump: Dump) -> pd.DataFrame:
    sessions = get(f"{API}/sessions?year=2026&session_name=Race", RAW / "sessions_2026_test.json")
    by_day = {date.fromisoformat(s["date_start"][:10]): s for s in sessions if s.get("session_type") == "Race"}
    sched = dump.schedule(2026).set_index("round")
    rows = []
    for rnd in TEST_ROUNDS:
        day = sched.loc[rnd, "date"]
        s = by_day.get(day)
        if s is None:
            print("no OpenF1 race for round", rnd, day)
            continue
        msgs = get(f"{API}/race_control?session_key={s['session_key']}", RAW / f"race_control_{s['session_key']}.json")
        last = int(lap_table(dump.race(2026, rnd, allow_holdout=True))["lap"].max())
        circuit = int(sched.loc[rnd, "circuit_id"])
        rows.append(race_rows(neutral_laps(msgs, last), last, season=2026, round=rnd, circuit_id=circuit))
    return pd.concat(rows, ignore_index=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true")
    args = ap.parse_args()
    dump = Dump(ROOT / "data" / "raw" / "jolpica-dump" / "csv")
    dev = dev_rows(dump)
    if not args.test:
        m = Models(dev)
        out = {
            "spec": "15-sc-hazard",
            "section": "4 development, leave-one-season-out",
            "commit": commit(),
            "loso": loso(dev),
            "events": kinds(dev),
            "full_fit": {
                "w_intercept_lap1_lap2_3": m.w.tolist(),
                "prior_strength": m.prior_strength,
                "global_rate": m.global_rate,
            },
        }
        (ROOT / "results" / "15-sc-hazard-dev.json").write_text(json.dumps(out, indent=2))
        print(json.dumps(out, indent=2))
        return

    if date.today() <= TEST_AFTER:
        raise SystemExit(f"spec 15 test runs after {TEST_AFTER} (last 2026 race)")
    out_path = ROOT / "results" / "15-sc-hazard-test.json"
    if out_path.exists():
        raise SystemExit("spec 15 test already ran; it runs once")
    test = test_rows(dump)
    preds = Models(dev).predict(test)
    res = score(test, preds)
    y = test["event"].to_numpy()
    keys = list(zip(test["season"], test["round"]))
    races = sorted(set(keys))
    rng = np.random.default_rng(0)
    idx_by_race = {r: np.flatnonzero([k == r for k in keys]) for r in races}
    diffs = []
    for _ in range(10_000):
        pick = np.concatenate([idx_by_race[races[i]] for i in rng.integers(0, len(races), len(races))])
        diffs.append(log_loss(y[pick], preds["M1"][pick]) - log_loss(y[pick], preds["M2"][pick]))
    ci = [float(np.quantile(diffs, 0.025)), float(np.quantile(diffs, 0.975))]
    rules = {
        "H1_pass": res["M2"]["log_loss"] < res["M1"]["log_loss"],
        "H2_pass": res["M2"]["log_loss"] < res["M0"]["log_loss"],
        "H3_ci_M1_minus_M2": ci,
        "H3_pass": ci[0] > 0,
    }
    rules["pass"] = bool(rules["H1_pass"] and rules["H2_pass"])
    out = {
        "spec": "15-sc-hazard",
        "section": "5 test",
        "commit": commit(),
        "test": res,
        "events": kinds(test),
        "rules": rules,
    }
    out_path.write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
