"""Tyre compounds per lap from the TracingInsights open data (specs/08-undercut-b.md).

Source: github.com/TracingInsights/<year>, file "<Grand Prix name>/Race/session_laptimes.json"
(MIT for 2022 to 2024, Apache-2.0 for 2025 and 2026). The race lap times in these files come from Ergast/Jolpica.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

import numpy as np
import pandas as pd

RAW_URL = "https://raw.githubusercontent.com/TracingInsights/{year}/main/{gp}/Race/session_laptimes.json"
HARDNESS = {"SOFT": 1, "MEDIUM": 2, "HARD": 3}  # INTERMEDIATE, WET and UNKNOWN are not in the map
COLUMNS = ("drv", "lap", "time", "compound", "life", "stint")


def url(year: int, gp: str) -> str:
    return RAW_URL.format(year=year, gp=quote(gp))


def _none(v):
    return np.nan if v in (None, "None", "") else v


def parse(path: str | Path) -> pd.DataFrame:
    """One row per driver and lap: code, lap, time_s, compound, life, stint, hardness (NaN if not dry)."""
    d = json.loads(Path(path).read_text())
    n = len(d["lap"])
    cols = {c: d.get(c, [None] * n) for c in COLUMNS}
    out = pd.DataFrame(
        {
            "code": cols["drv"],
            "lap": pd.to_numeric(pd.Series(cols["lap"]).map(_none), errors="coerce"),
            "time_s": pd.to_numeric(pd.Series(cols["time"]).map(_none), errors="coerce"),
            "compound": pd.Series(cols["compound"]).map(_none),
            "life": pd.to_numeric(pd.Series(cols["life"]).map(_none), errors="coerce"),
            "stint": pd.to_numeric(pd.Series(cols["stint"]).map(_none), errors="coerce"),
        }
    )
    out = out.dropna(subset=["lap"])
    out["lap"] = out["lap"].astype(int)
    out["hardness"] = out["compound"].map(HARDNESS)
    return out.reset_index(drop=True)


def join(race, tyres: pd.DataFrame, codes: dict[str, str]) -> pd.DataFrame:
    """Add compound, life, stint_ti and hardness to the Jolpica laps of a race. `codes` maps the driver code to the
    Jolpica driver reference. Adds `time_diff_s` (TracingInsights minus Jolpica) for the data check."""
    t = tyres.assign(driver=tyres["code"].map(codes)).dropna(subset=["driver"])
    t = t.rename(columns={"time_s": "ti_time_s", "stint": "stint_ti"})
    out = race.laps.merge(
        t[["driver", "lap", "ti_time_s", "compound", "life", "stint_ti", "hardness"]], on=["driver", "lap"], how="left"
    )
    out["time_diff_s"] = out["ti_time_s"] - out["time_s"]
    return out.drop(columns="ti_time_s")
