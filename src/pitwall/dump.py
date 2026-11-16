"""Read the Jolpica CSV dump into Race objects (spec 01, amendment A2)."""

from __future__ import annotations

from datetime import date
from functools import cached_property
from pathlib import Path

import pandas as pd

from .data import Race, parse_time
from .splits import assert_not_holdout

QUALIFYING_TYPES = ("Q1", "Q2", "Q3")


def _bool(s: pd.Series) -> pd.Series:
    return s.astype(str).str.lower().isin(("t", "true", "1"))


class Dump:
    """Lazy reader for the formula_one_*.csv files of a Jolpica dump."""

    def __init__(self, csv_dir: str | Path):
        self.dir = Path(csv_dir)

    def _read(self, name: str, **kw) -> pd.DataFrame:
        return pd.read_csv(self.dir / f"formula_one_{name}.csv", low_memory=False, **kw)

    @cached_property
    def rounds(self) -> pd.DataFrame:
        seasons = self._read("season")[["id", "year"]].rename(columns={"id": "season_id"})
        r = self._read("round")[["id", "season_id", "circuit_id", "number", "name", "date", "is_cancelled"]]
        r = r.merge(seasons, on="season_id")
        r = r[~_bool(r["is_cancelled"])].copy()
        r["date"] = pd.to_datetime(r["date"]).dt.date
        return r.rename(columns={"id": "round_id"})

    @cached_property
    def race_sessions(self) -> pd.DataFrame:
        s = self._read("session")[["id", "round_id", "type", "is_cancelled"]]
        s = s[(s["type"] == "R") & ~_bool(s["is_cancelled"])]
        return s.rename(columns={"id": "session_id"}).merge(self.rounds, on="round_id")

    @cached_property
    def entries(self) -> pd.DataFrame:
        e = self._read("sessionentry")[
            ["id", "session_id", "round_entry_id", "grid", "position", "is_classified", "laps_completed", "detail"]
        ]
        re_ = self._read("roundentry")[["id", "team_driver_id"]].rename(columns={"id": "round_entry_id"})
        td = self._read("teamdriver")[["id", "driver_id"]].rename(columns={"id": "team_driver_id"})
        dr = self._read("driver")[["id", "reference"]].rename(columns={"id": "driver_id"})
        e = e.merge(re_, on="round_entry_id").merge(td, on="team_driver_id").merge(dr, on="driver_id")
        return e.rename(columns={"id": "session_entry_id", "reference": "driver"})

    @cached_property
    def laps(self) -> pd.DataFrame:
        lap = self._read("lap", usecols=["id", "session_entry_id", "number", "position", "time", "is_deleted"])
        lap = lap[~_bool(lap["is_deleted"]) & lap["number"].notna()]
        return lap.rename(columns={"id": "lap_id"})

    @cached_property
    def pitstops(self) -> pd.DataFrame:
        return self._read("pitstop")[["session_entry_id", "lap_id", "number", "duration"]]

    @cached_property
    def timed_laps(self) -> pd.DataFrame:
        """All laps with a time, also the rows without a lap number (fastest-lap rows)."""
        lap = self._read("lap", usecols=["session_entry_id", "time", "is_deleted"])
        return lap[~_bool(lap["is_deleted"]) & lap["time"].notna()]

    @cached_property
    def qualifying_sessions(self) -> pd.DataFrame:
        s = self._read("session")[["id", "round_id", "type", "is_cancelled"]]
        s = s[s["type"].isin(QUALIFYING_TYPES) & ~_bool(s["is_cancelled"])]
        return s.rename(columns={"id": "session_id"}).merge(self.rounds, on="round_id")

    def qualifying(self, season: int, rnd: int, *, allow_holdout: bool = False) -> pd.Series:
        """Best qualifying lap (s) of each driver over Q1, Q2 and Q3 of one round (spec 06)."""
        s = self.qualifying_sessions
        s = s[(s["year"] == season) & (s["number"] == rnd)]
        if s.empty:
            return pd.Series(dtype=float, name="best_s")
        assert_not_holdout(s["date"].iloc[0], allow_holdout=allow_holdout)
        ent = self.entries[self.entries["session_id"].isin(s["session_id"])]
        ids = ent.set_index("session_entry_id")["driver"]
        lap = self.timed_laps[self.timed_laps["session_entry_id"].isin(ids.index)]
        times = pd.Series([parse_time(t) for t in lap["time"]], index=lap["session_entry_id"].map(ids).values)
        return times.groupby(level=0).min().rename("best_s")

    def schedule(self, season: int) -> pd.DataFrame:
        s = self.race_sessions[self.race_sessions["year"] == season]
        out = s[["number", "name", "date", "circuit_id"]].rename(columns={"number": "round"})
        return out.sort_values("round", ignore_index=True)

    def race(self, season: int, rnd: int, *, allow_holdout: bool = False) -> Race:
        s = self.race_sessions[(self.race_sessions["year"] == season) & (self.race_sessions["number"] == rnd)]
        if s.empty:
            raise KeyError(f"no race session for {season} round {rnd} in the dump")
        row = s.iloc[0]
        race_date: date = row["date"]
        assert_not_holdout(race_date, allow_holdout=allow_holdout)

        ent = self.entries[self.entries["session_id"] == row["session_id"]]
        ids = ent.set_index("session_entry_id")["driver"]
        lap = self.laps[self.laps["session_entry_id"].isin(ids.index)]
        laps = pd.DataFrame(
            {
                "driver": lap["session_entry_id"].map(ids).values,
                "lap": lap["number"].astype(int).values,
                "position": pd.to_numeric(lap["position"], errors="coerce").astype("Int64").values,
                "time_s": [parse_time(t) for t in lap["time"]],
            }
        )
        pit = self.pitstops[self.pitstops["session_entry_id"].isin(ids.index)]
        pit = pit.merge(self.laps[["lap_id", "number"]].rename(columns={"number": "lap"}), on="lap_id", how="left")
        pitstops = pd.DataFrame(
            {
                "driver": pit["session_entry_id"].map(ids).values,
                "lap": pd.to_numeric(pit["lap"], errors="coerce").astype("Int64").values,
                "stop": pit["number"].astype(int).values,
                "duration_s": [parse_time(t) for t in pit["duration"]],
            }
        )
        results = pd.DataFrame(
            {
                "driver": ent["driver"].values,
                "grid": pd.to_numeric(ent["grid"], errors="coerce").fillna(0).astype(int).values,
                "position": pd.to_numeric(ent["position"], errors="coerce").astype("Int64").values,
                "laps": pd.to_numeric(ent["laps_completed"], errors="coerce").fillna(0).astype(int).values,
                "status": ent["detail"].fillna("").values,
                "classified": _bool(ent["is_classified"]).values,
            }
        )
        return Race(
            season=season,
            round=rnd,
            name=row["name"],
            date=race_date,
            laps=laps.sort_values(["driver", "lap"], ignore_index=True),
            pitstops=pitstops.sort_values(["driver", "stop"], ignore_index=True),
            results=results,
        )
