"""Spec 23, section 2: tyre wear and pace offset per compound, fitted on 2019 to 2022 races only.

Usage: PYTHONPATH=src .venv/bin/python scripts/tyre_model.py
Writes results/23-tyre-model.json.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np

from pitwall.dump import Dump
from pitwall.tyres import join, parse
from pitwall.tyrewear import COMPOUNDS, pool, race_fit

ROOT = Path(__file__).resolve().parents[1]
SEASONS = (2019, 2020, 2021, 2022)
MIN_CIRCUIT_RACES = 2


def fit_all(dump: Dump) -> list[dict]:
    fits = []
    for s in SEASONS:
        sched = dump.schedule(s)
        for rnd, cid in zip(sched["round"].astype(int), sched["circuit_id"].astype(int)):
            path = ROOT / "data" / "raw" / "tracinginsights" / str(s) / f"{rnd:02d}.json"
            if not path.exists():
                continue
            race = dump.race(s, rnd)
            codes = {dump.driver_codes[x]: x for x in race.results["driver"] if x in dump.driver_codes.index}
            f = race_fit(race, join(race, parse(path), codes))
            if f is not None:
                fits.append({"season": s, "round": rnd, "circuit_id": cid, "name": race.name, "fit": f})
    return fits


def main() -> None:
    fits = fit_all(Dump(ROOT / "data" / "raw" / "jolpica-dump" / "csv"))
    glob = pool([f["fit"] for f in fits])
    circuits = {}
    for cid in sorted({f["circuit_id"] for f in fits}):
        mine = [f["fit"] for f in fits if f["circuit_id"] == cid]
        if len(mine) >= MIN_CIRCUIT_RACES:
            r = pool(mine)
            circuits[str(cid)] = {"deg": r.deg.tolist(), "offset": r.offset.tolist(), "races": len(mine)}
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True)
    out = {
        "spec": "23-compound-wear",
        "commit": sha.stdout.strip(),
        "seasons": list(SEASONS),
        "compounds": list(COMPOUNDS),
        "races_fitted": len(fits),
        "global": {"deg": glob.deg.tolist(), "offset": glob.offset.tolist()},
        "circuits": circuits,
        "races": fits,
    }
    (ROOT / "results" / "23-tyre-model.json").write_text(json.dumps(out, indent=2))
    print(
        len(fits), "races;", {k: np.round(v, 3).tolist() for k, v in out["global"].items()}, len(circuits), "circuits"
    )


if __name__ == "__main__":
    main()
