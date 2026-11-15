"""Lap table features from Jolpica data: stints, tyre age, pit laps, neutralised laps."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .data import Race

NEUTRAL_FACTOR = 1.15  # a lap is neutralised if the field median is this much slower than the green median


def lap_table(race: Race) -> pd.DataFrame:
    """One row per driver and lap, sorted by driver and lap.

    Columns: driver, lap, position, time_s, stint, tyre_age, in_lap, out_lap, neutral, race_lap_frac.
    - stint starts at 1 and adds 1 after each pit stop.
    - tyre_age is the number of laps on the current tyres (1 on the first lap of a stint).
    - in_lap: the driver pits at the end of this lap. out_lap: the first lap after a pit stop.
    - neutral: safety car, virtual safety car or red flag. Jolpica has no flag data, so we detect it
      from the field: the median lap time of the lap is more than NEUTRAL_FACTOR x the median of all laps.
    """
    laps = race.laps.sort_values(["driver", "lap"]).reset_index(drop=True).copy()
    pits = race.pitstops[["driver", "lap"]].drop_duplicates()
    pit_keys = set(zip(pits["driver"], pits["lap"]))
    laps["in_lap"] = [(d, n) in pit_keys for d, n in zip(laps["driver"], laps["lap"])]
    laps["out_lap"] = [(d, n - 1) in pit_keys for d, n in zip(laps["driver"], laps["lap"])]
    laps["stint"] = laps.groupby("driver")["out_lap"].cumsum().astype(int) + 1
    laps["tyre_age"] = laps.groupby(["driver", "stint"]).cumcount() + 1

    field = laps.groupby("lap")["time_s"].median()
    green = float(np.nanmedian(field.values))
    neutral_laps = set(field.index[field > NEUTRAL_FACTOR * green])
    laps["neutral"] = laps["lap"].isin(neutral_laps)
    laps.loc[laps["lap"] == 1, "neutral"] = True  # standing start: not a normal racing lap
    total = int(laps["lap"].max())
    laps["race_lap_frac"] = laps["lap"] / total
    return laps


def clean_mask(laps: pd.DataFrame) -> pd.Series:
    """Laps that a pace model can use: not neutralised, not an in-lap or out-lap, with a lap time."""
    return ~laps["neutral"] & ~laps["in_lap"] & ~laps["out_lap"] & laps["time_s"].notna()
