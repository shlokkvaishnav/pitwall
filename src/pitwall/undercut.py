"""Undercut duels (docs/specs/07-undercut.md): a driver pits first to pass the car directly ahead."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .laps import lap_table

MAX_GAP_S = 3.0
MAX_RESPONSE_LAPS = 5


def cumulative_times(t: pd.DataFrame) -> pd.DataFrame:
    """(lap x driver) cumulative race time. NaN after a missing lap time."""
    wide = t.pivot(index="lap", columns="driver", values="time_s").sort_index()
    return wide.cumsum(skipna=False)


class CumTable:
    """Cumulative race times as a numpy array, with lap and driver indexes (faster and typed lookups)."""

    def __init__(self, cum: pd.DataFrame):
        self.values = cum.to_numpy(dtype=float)
        self.laps = [int(x) for x in cum.index]
        self.drivers = [str(x) for x in cum.columns]
        self._lap = {lap: i for i, lap in enumerate(self.laps)}
        self._drv = {d: j for j, d in enumerate(self.drivers)}

    def has_lap(self, lap: int) -> bool:
        return lap in self._lap

    def get(self, lap: int, driver: str) -> float:
        i, j = self._lap.get(lap), self._drv.get(driver)
        return float("nan") if i is None or j is None else float(self.values[i, j])

    def car_ahead(self, lap: int, driver: str) -> tuple[str, float] | None:
        """The car directly ahead of `driver` at the end of `lap` and the gap to it (the first one on a tie)."""
        mine = self.get(lap, driver)
        row = self.values[self._lap[lap]]
        ok = np.isfinite(row) & (row < mine)
        if not ok.any():
            return None
        j = int(np.where(ok, row, -np.inf).argmax())
        return self.drivers[j], mine - float(row[j])

    def last_common_lap(self, a: str, b: str) -> int | None:
        both = np.isfinite(self.values[:, self._drv[a]]) & np.isfinite(self.values[:, self._drv[b]])
        return None if not both.any() else int(np.asarray(self.laps)[both].max())


@dataclass
class _Race:
    """Lookups shared by `duels` and `open_duels`."""

    season: int
    round: int
    cum: CumTable
    neutral: dict[int, bool]
    pit_laps: dict[str, set[int]]
    age: dict[tuple[str, int], int]
    total: int

    def any_neutral(self, first: int, last: int) -> bool:
        """True if a lap from `first` to `last` is neutralised or has no data."""
        return any(self.neutral.get(lap, True) for lap in range(first, last + 1))


def _prepare(race) -> _Race:
    t = lap_table(race)
    pits = race.pitstops.dropna(subset=["lap"])
    return _Race(
        season=race.season,
        round=race.round,
        cum=CumTable(cumulative_times(t)),
        neutral=dict(zip(t["lap"].astype(int).tolist(), t.groupby("lap")["neutral"].transform("any").tolist())),
        pit_laps={str(d): {int(x) for x in g["lap"]} for d, g in pits.groupby("driver")},
        age={(str(d), int(lap)): int(a) for d, lap, a in zip(t["driver"], t["lap"], t["tyre_age"])},
        total=int(t["lap"].max()),
    )


def _attempts(r: _Race, pits: pd.DataFrame):
    """Yield (a, lap_a, b, gap): `a` pits at the end of lap_a, `b` is directly ahead at the end of lap_a - 1,
    at most MAX_GAP_S ahead, and `b` does not pit on lap_a - 1 or lap_a."""
    for a, lap_a in zip(pits["driver"], pits["lap"].astype(int)):
        a, lap_a, before = str(a), int(lap_a), int(lap_a) - 1
        if before < 2 or not r.cum.has_lap(before) or np.isnan(r.cum.get(before, a)):
            continue
        ahead = r.cum.car_ahead(before, a)
        if ahead is None:
            continue
        b, gap = ahead
        if gap > MAX_GAP_S or {before, lap_a} & r.pit_laps.get(b, set()):
            continue
        yield a, lap_a, b, gap


def duels(race) -> pd.DataFrame:
    """One row per undercut duel. `a` pits at the end of lap `lap_a`; `b` was directly ahead of `a` at the end
    of lap `lap_a` - 1, at most MAX_GAP_S ahead, and pits at the end of lap `lap_b` (lap_a < lap_b <= lap_a + 5).
    There is no neutralised lap from lap_a - 1 to lap_b + 1. Outcome `a_ahead`: `a` is ahead after lap_b + 1.
    """
    r = _prepare(race)
    rows = []
    for a, lap_a, b, gap in _attempts(r, race.pitstops.dropna(subset=["lap"])):
        later = sorted(x for x in r.pit_laps.get(b, set()) if lap_a < x <= lap_a + MAX_RESPONSE_LAPS)
        if not later:
            continue
        lap_b = later[0]
        end = lap_b + 1
        if not r.cum.has_lap(end) or r.any_neutral(lap_a - 1, end):
            continue
        ca, cb = r.cum.get(end, a), r.cum.get(end, b)
        if np.isnan(ca) or np.isnan(cb):
            continue
        rows.append(
            {
                "season": r.season,
                "round": r.round,
                "a": a,
                "b": b,
                "lap_a": lap_a,
                "lap_b": lap_b,
                "gap_s": gap,
                "wait_laps": lap_b - lap_a,
                "age_a": r.age.get((a, lap_a), 0),
                "age_b": r.age.get((b, lap_a), 0),
                "race_lap_frac": lap_a / r.total,
                "a_ahead": bool(ca < cb),
            }
        )
    return pd.DataFrame(rows)


def open_duels(race) -> pd.DataFrame:
    """Spec 10: undercut events without the response condition. `a` pits at the end of lap `lap_a` while `b` is
    directly ahead (at most MAX_GAP_S) and `b` does not pit on lap_a - 1 or lap_a. `lap_b` is the next stop of `b`
    after lap_a (any wait). If `b` does not stop again, the outcome lap is the last lap that both completed.
    Outcome `a_ahead`: `a` is ahead after the outcome lap. No neutralised lap from lap_a - 1 to the outcome lap.
    """
    r = _prepare(race)
    rows = []
    for a, lap_a, b, gap in _attempts(r, race.pitstops.dropna(subset=["lap"])):
        later = sorted(x for x in r.pit_laps.get(b, set()) if x > lap_a)
        last_both = r.cum.last_common_lap(a, b)
        if last_both is None:
            continue
        lap_b: int | None
        if later:
            lap_b, end = later[0], later[0] + 1
        else:
            lap_b, end = None, last_both
        if end > last_both or end <= lap_a or r.any_neutral(lap_a - 1, end):
            continue
        rows.append(
            {
                "season": r.season,
                "round": r.round,
                "a": a,
                "b": b,
                "lap_a": lap_a,
                "lap_b": lap_b,
                "b_responds": lap_b is not None,
                "gap_s": gap,
                "age_a": r.age.get((a, lap_a), 0),
                "age_b": r.age.get((b, lap_a), 0),
                "race_lap_frac": lap_a / r.total,
                "remaining_laps": r.total - lap_a,
                "a_ahead": bool(r.cum.get(end, a) < r.cum.get(end, b)),
            }
        )
    return pd.DataFrame(rows)
