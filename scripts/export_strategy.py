"""Export the "race strategy" section of the site for one race: the 2026 Dutch Grand Prix (round 12).

Usage: PYTHONPATH=src:scripts .venv/bin/python scripts/export_strategy.py
Writes site/data/race-strategy.json. Same race as the next-lap forecast on the page (chosen before, not by result) and
one of the three spec 18 development races. Models are the spec 18 world: nothing from 2026 informs the hazard or
the overtaking model; pace inputs use races before round 12. Display only, not a result.

- hazard: chance a safety car or VSC starts on each lap (spec 15 M2), with the laps where one really started;
- overtaking: chance of a pass on one lap at each circuit for the same duel (0.8 s behind, 0.5 s a lap faster);
- pit window: simulator C, the car starting 5th stops once on lap L, every other car on its plan; mean finish.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
from race_sim_b import history
from rl_strategy import build_worlds
from sc_hazard import dev_rows

from pitwall.dump import Dump
from pitwall.strategy_env import fixed_policy, run

ROOT = Path(__file__).resolve().parents[1]
ROUND = 12
RUNS = 200
SEED0 = 50_000  # not used by spec 18 (training 0-9999, evaluation 10000-10999)
DUEL = {"gap": 0.8, "pace_delta": -0.5, "tyre_age_diff": 0.0, "race_frac": 0.5}


def main() -> None:
    dump = Dump(ROOT / "data" / "raw" / "jolpica-dump" / "csv")
    w = build_worlds(dump)[ROUND]
    races, _stats, _rows = history(dump, [ROUND])
    race = races[(2026, ROUND)]
    laps = w.inp.laps
    ego = w.inp.drivers[w.ego]

    hz = dev_rows(dump)
    real = hz[(hz["season"] == 2026) & (hz["round"] == ROUND) & (hz["event"] == 1)]
    h = w.hazard[1:]

    rounds = dump.rounds
    names = rounds[rounds["year"] == 2026].set_index("circuit_id")["name"].str.replace(" Grand Prix", "").to_dict()
    pairs = pd.read_csv(ROOT / "data" / "derived" / "pair_laps.csv.gz", usecols=["season", "circuit_id"])
    seen = set(pairs.loc[pairs["season"] < 2026, "circuit_id"])
    over = []
    for cid, name in sorted(names.items(), key=lambda x: x[1]):
        if cid not in seen:
            continue
        p = w.overtake.gbm_fast(int(cid), np.array([DUEL["gap"]]), np.array([DUEL["pace_delta"]]),
                                np.array([DUEL["tyre_age_diff"]]), DUEL["race_frac"])  # fmt: skip
        over.append({"circuit": name, "p": round(float(p[0]), 4), "this": int(cid) == int(w.circuit_id)})

    window = []
    for lap in range(8, laps - 7):
        res = [run(w, SEED0 + i, fixed_policy([lap]))[0] for i in range(RUNS)]
        window.append(
            {"lap": lap, "mean": round(float(np.mean(res)), 3), "top5": round(float(np.mean(np.array(res) <= 5)), 3)}
        )
        print(lap, window[-1], flush=True)
    stops = race.pitstops
    real_stops = stops.loc[stops["driver"] == ego, "lap"].astype(int).tolist()
    res = race.results.set_index("driver")

    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True)
    out = {
        "race": race.name if str(race.name).startswith("2026") else f"2026 {race.name}",
        "round": ROUND,
        "laps": laps,
        "hazard": np.round(h, 4).tolist(),
        "any_neutral": round(float(1 - np.prod(1 - h)), 3),
        "real_neutral": [{"lap": int(r.lap), "kind": str(r.kind)} for r in real.itertuples()],
        "duel": DUEL,
        "overtaking": over,
        "ego": {
            "driver": ego,
            "grid": int(res.loc[ego, "grid"]),
            "finish": int(res.loc[ego, "position"]),
            "real_stops": real_stops,
        },
        "window": window,
        "runs": RUNS,
        "commit": sha.stdout.strip(),
    }
    (ROOT / "site" / "data" / "race-strategy.json").write_text(json.dumps(out, separators=(",", ":")))
    print({k: v for k, v in out.items() if k not in ("hazard", "window", "overtaking")})


if __name__ == "__main__":
    main()
