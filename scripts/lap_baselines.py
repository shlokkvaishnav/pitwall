"""Spec 02: next-lap-time baselines on the 2026 development races.

Usage: PYTHONPATH=src .venv/bin/python scripts/lap_baselines.py
Needs results/01-data-check.json. Writes results/02-lap-baselines.json.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pandas as pd

from pitwall import baselines as bl
from pitwall.data import Jolpica, load_race
from pitwall.laps import clean_mask, lap_table

ROOT = Path(__file__).resolve().parents[1]
NAMES = ("previous_lap", "linear_stint", "local_trend")


def main() -> None:
    check = json.loads((ROOT / "results" / "01-data-check.json").read_text())
    bad = set(check["rules"]["D1_failed_rounds"])
    bad |= {r["round"] for r in check["races"] if r["pitstop_on_known_lap"] < 0.99}
    rounds = [r["round"] for r in check["races"] if r["round"] not in bad]

    client = Jolpica(ROOT / "data" / "jolpica-cache")
    per_race, frames, neutral = [], [], []
    for rnd in rounds:
        laps = lap_table(load_race(client, 2026, rnd))
        preds = {n: getattr(bl, n)(laps) for n in NAMES}
        keep = clean_mask(laps) & pd.concat(preds, axis=1).notna().all(axis=1)
        err = {n: (preds[n][keep] - laps.loc[keep, "time_s"]).abs() for n in NAMES}
        per_race.append({"round": rnd, "n_laps": int(keep.sum()), **{n: float(e.mean()) for n, e in err.items()}})
        frames.append(pd.DataFrame(err))
        neutral.append(laps["neutral"].mean())
        print(json.dumps(per_race[-1]), flush=True)

    pooled = pd.concat(frames).mean().to_dict()
    bar = min(pooled, key=pooled.get)
    neutral_frac = float(sum(neutral) / len(neutral))
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True)
    out = {
        "spec": "02-lap-baselines",
        "commit": sha.stdout.strip(),
        "rounds": rounds,
        "excluded_rounds": sorted(bad),
        "pooled_mae_s": pooled,
        "L1_bar_for_R1": bar,
        "neutral_fraction": neutral_frac,
        "L2_pass": pooled["previous_lap"] < 2.0 and 0.02 <= neutral_frac <= 0.30,
        "races": per_race,
    }
    (ROOT / "results" / "02-lap-baselines.json").write_text(json.dumps(out, indent=2))
    print(json.dumps({k: v for k, v in out.items() if k != "races"}, indent=2))


if __name__ == "__main__":
    main()
