"""Spec 11: the final test on the locked 2026 races (rounds 13 to 18 of the pinned dump).

Usage:
  PYTHONPATH=src .venv/bin/python scripts/holdout.py --dry-run   # development rounds 7 to 12, checks the code, does not count
  PYTHONPATH=src .venv/bin/python scripts/holdout.py             # the one holdout run
Needs the tyre files of the test rounds (fetch_tyres.py --holdout 13 14 15 16 17 18 for the real run).
Writes results/11-holdout.json (or results/11-dry-run.json).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import export_undercut_model as eu
import race_sim_b as rsb
import undercut_open as uo

from pitwall import baselines as bl
from pitwall.dump import Dump
from pitwall.evaluate import dm_block_bootstrap
from pitwall.features import build
from pitwall.lapmodel import fit_predict, pretrain_features
from pitwall.laps import lap_table
from pitwall.undercut_models import logloss

ROOT = Path(__file__).resolve().parents[1]
HOLDOUT_ROUNDS = [13, 14, 15, 16, 17, 18]  # the holdout races in the pinned dump (spec 11)
DRY_RUN_ROUNDS = [7, 8, 9, 10, 11, 12]
DEV_ROUNDS = list(range(1, 13))
BASELINES = ("previous_lap", "linear_stint", "local_trend")


def undercut(test_rounds: list[int], allow: bool) -> dict:
    first = min(test_rounds)
    train = uo.load(range(2018, 2027), rounds_2026=[r for r in DEV_ROUNDS if r < first])
    test = uo.load([2026], rounds_2026=test_rounds, allow_holdout=allow)
    train = train.dropna(subset=["life_a_new"]).reset_index(drop=True)  # as the deployed model (export script)
    test = test.dropna(subset=["life_a_new"]).reset_index(drop=True)
    model = uo.logistic().fit(train[uo.PITWALL], train["a_ahead"].astype(int))
    y = test["a_ahead"].astype(int).to_numpy()
    p = model.predict_proba(test[uo.PITWALL])[:, 1]
    base = float(train["a_ahead"].mean())
    brier, brier_base = float(((p - y) ** 2).mean()), float(((base - y) ** 2).mean())
    dm = dm_block_bootstrap(logloss(p, y), logloss(np.full(len(y), base), y), test["race"])
    edges = np.linspace(0, 1, 6)
    bins = np.clip(np.digitize(p, edges[1:-1]), 0, 4)
    calib = [
        {"lo": float(edges[b]), "hi": float(edges[b + 1]), "n": int((bins == b).sum()),
         "mean_p": float(p[bins == b].mean()) if (bins == b).any() else None,
         "freq": float(y[bins == b].mean()) if (bins == b).any() else None}
        for b in range(5)
    ]  # fmt: skip
    out = {
        "train_events": len(train),
        "test_events": len(test),
        "test_base_rate": float(y.mean()),
        "train_base_rate": base,
        "brier": brier,
        "brier_base_rate": brier_base,
        "bss": 1 - brier / brier_base,
        "logloss": float(logloss(p, y).mean()),
        "logloss_base_rate": float(logloss(np.full(len(y), base), y).mean()),
        "dm": dm,
        "calibration": calib,
        "per_race": test.assign(p=p)
        .groupby("race")
        .apply(
            lambda g: {"events": len(g), "freq": float(g["a_ahead"].mean()), "mean_p": float(g["p"].mean())},
            include_groups=False,
        )
        .to_dict(),
    }
    if allow:  # the model must be the one on the site
        site = json.loads((ROOT / "site" / "data" / "undercut-model.json").read_text())["params"]
        mine = eu.params(model)
        out["same_as_site"] = bool(
            all(np.allclose(mine[k], site[k], atol=2e-6) for k in ("mean", "scale", "coef", "intercept"))
        )
    return out


def lap_rows(dump: Dump, rnd: int, allow: bool) -> pd.DataFrame:
    """The spec 03 rows of one 2026 race (as lapmodel.race_features), with the spec 02 baselines on the same rows."""
    laps = lap_table(dump.race(2026, rnd, allow_holdout=allow))
    f = build(laps)
    f["season"], f["round"] = 2026, rnd
    for name in BASELINES:
        f[name] = getattr(bl, name)(laps)
    return f[f["use"]]


def lap_time(dump: Dump, test_rounds: list[int], allow: bool) -> dict:
    pre = pretrain_features(dump)
    rows26 = {r: lap_rows(dump, r, allow and r in HOLDOUT_ROUNDS) for r in sorted({*DEV_ROUNDS, *test_rounds})}
    parts = []
    for k in test_rounds:
        earlier = pd.concat([rows26[r] for r in rows26 if r < k], ignore_index=True)
        test = rows26[k]
        pred_pre, _ = fit_predict(pd.concat([pre, earlier], ignore_index=True), test)
        pred_26, _ = fit_predict(earlier, test)
        y = test["time_s"].to_numpy()
        part = pd.DataFrame({"round": k, "gbm_pretrain": pred_pre - y, "gbm_2026": pred_26 - y})
        for name in BASELINES:
            part[name] = test[name].to_numpy() - y
        parts.append(part)
    allr = pd.concat(parts, ignore_index=True).dropna()
    mae = {c: float(allr[c].abs().mean()) for c in allr.columns if c != "round"}
    best = min(BASELINES, key=mae.get)
    dm = dm_block_bootstrap(allr["gbm_pretrain"], allr[best], allr["round"])
    per_race = allr.groupby("round").agg(lambda s: float(s.abs().mean())).reset_index().to_dict("records")
    return {"laps": len(allr), "pooled_mae_s": mae, "best_baseline": best, "dm_vs_best": dm, "races": per_race}


def simulator(dump: Dump, test_rounds: list[int], allow: bool) -> dict:
    rounds_2026 = sorted({*DEV_ROUNDS, *test_rounds})
    races, stats, rows = rsb.history(dump, rounds_2026, allow_holdout=allow)
    recs = [rsb.evaluate(dump, races, stats, rows, k, allow_holdout=allow)[0] for k in test_rounds]
    df = pd.DataFrame(recs)
    return {
        "spearman_B": float(df["spearman_B"].mean()),
        "spearman_grid": float(df["spearman_grid"].mean()),
        "brier_B": float(df["brier_B"].mean()),
        "brier_grid": float(df["brier_grid"].mean()),
        "races": recs,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--dry-run", action="store_true", help="development rounds 7 to 12; checks the code, does not count"
    )
    args = ap.parse_args()
    rounds, allow = (DRY_RUN_ROUNDS, False) if args.dry_run else (HOLDOUT_ROUNDS, True)
    dump = Dump(ROOT / "data" / "raw" / "jolpica-dump" / "csv")

    u = undercut(rounds, allow)
    print("undercut", json.dumps({k: u[k] for k in ("test_events", "bss", "dm")}), flush=True)
    lt = lap_time(dump, rounds, allow)
    print("lap time", json.dumps(lt["pooled_mae_s"]), flush=True)
    sim = simulator(dump, rounds, allow)
    print("simulator", json.dumps({k: v for k, v in sim.items() if k != "races"}), flush=True)

    mae = lt["pooled_mae_s"]
    rules = {
        "U1_bss": u["bss"],
        "U1_pass": bool(u["bss"] > 0),
        "U2_p": u["dm"]["p_value"],
        "U2_pass": bool(u["dm"]["p_value"] < 0.05),
        "R1_ratio": mae["gbm_pretrain"] / mae[lt["best_baseline"]],
        "R1_pass": bool(mae["gbm_pretrain"] <= 0.95 * mae[lt["best_baseline"]] and lt["dm_vs_best"]["p_value"] < 0.05),
        "R2": "not tested (charter amendment A1)",
        "R3_pass": bool(mae["gbm_pretrain"] < mae["gbm_2026"]),
        "R4_pass": bool(sim["spearman_B"] > sim["spearman_grid"] and sim["brier_B"] < sim["brier_grid"]),
        "R5": "not tested (charter amendment A3)",
    }
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True)
    out = {
        "spec": "11-holdout" + (" (dry run, development rounds, does not count)" if args.dry_run else ""),
        "commit": sha.stdout.strip(),
        "rounds": rounds,
        "rules": rules,
        "undercut": u,
        "lap_time": lt,
        "simulator": sim,
    }
    name = "11-dry-run.json" if args.dry_run else "11-holdout.json"
    (ROOT / "results" / name).write_text(json.dumps(out, indent=2, default=str))
    print(json.dumps(rules, indent=2))


if __name__ == "__main__":
    main()
