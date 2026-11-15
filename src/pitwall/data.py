"""Jolpica-F1 data layer (see specs/01-energy-limits-and-data.md, amendment A1)."""

from __future__ import annotations

import json
import re
import time
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from .splits import assert_not_holdout

BASE = "https://api.jolpi.ca/ergast/f1"
PAGE = 100


def parse_time(text: str | None) -> float:
    """'1:23.456' -> 83.456 s, '23.456' -> 23.456 s, '00:01:16.29' -> 76.29 s. Missing or bad text gives NaN."""
    if not isinstance(text, str) or not text.strip():
        return float("nan")
    parts = text.strip().split(":")
    if len(parts) > 3 or not all(re.fullmatch(r"\d+(?:\.\d+)?", x) for x in parts):
        return float("nan")
    value = 0.0
    for x in parts:
        value = value * 60 + float(x)
    return value


def _http_get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "pitwall-research"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


class Jolpica:
    """Paginated client with a disk cache and a minimum time between requests."""

    def __init__(self, cache_dir: str | Path, min_interval_s: float = 8.0, fetch: Callable[[str], dict] = _http_get):
        self.cache = Path(cache_dir)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.min_interval_s = min_interval_s
        self.fetch = fetch
        self._last = 0.0

    def _request(self, url: str) -> dict:
        wait = self._last + self.min_interval_s - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()
        return self.fetch(url)

    def get_races(self, path: str) -> list[dict]:
        """Get all pages of `path` (for example '2026/1/laps') and return the merged RaceTable races."""
        file = self.cache / (path.strip("/").replace("/", "_") + ".json")
        if file.exists():
            return json.loads(file.read_text())
        pages, offset = [], 0
        while True:
            data = self._request(f"{BASE}/{path.strip('/')}/?limit={PAGE}&offset={offset}")["MRData"]
            pages.append(data["RaceTable"]["Races"])
            offset += int(data["limit"])
            if offset >= int(data["total"]):
                break
        races = _merge_pages(pages)
        file.write_text(json.dumps(races))
        return races


def _merge_pages(pages: list[list[dict]]) -> list[dict]:
    """Pages can split one race, and one lap, over two pages. Join the lists in the same race and lap."""
    merged: dict[tuple, dict] = {}
    for page in pages:
        for race in page:
            key = (race["season"], race["round"])
            target = merged.setdefault(key, {k: v for k, v in race.items() if not isinstance(v, list)})
            for field, value in race.items():
                if not isinstance(value, list):
                    continue
                if field == "Laps":
                    laps = {lap["number"]: lap for lap in target.setdefault("Laps", [])}
                    for lap in value:
                        if lap["number"] in laps:
                            laps[lap["number"]]["Timings"].extend(lap["Timings"])
                        else:
                            target["Laps"].append({"number": lap["number"], "Timings": list(lap["Timings"])})
                            laps[lap["number"]] = target["Laps"][-1]
                else:
                    target.setdefault(field, []).extend(value)
    return list(merged.values())


@dataclass
class Race:
    season: int
    round: int
    name: str
    date: date
    laps: pd.DataFrame  # driver, lap, position, time_s
    pitstops: pd.DataFrame  # driver, lap, stop, duration_s
    results: pd.DataFrame  # driver, grid, position, laps, status, classified


def schedule(client: Jolpica, season: int) -> pd.DataFrame:
    races = client.get_races(f"{season}")
    return pd.DataFrame(
        [{"round": int(r["round"]), "name": r["raceName"], "date": date.fromisoformat(r["date"])} for r in races]
    ).sort_values("round", ignore_index=True)


def load_race(client: Jolpica, season: int, rnd: int, *, allow_holdout: bool = False) -> Race:
    """Load one race. The date check runs before the download of laps, pit stops and results."""
    sched = schedule(client, season)
    row = sched.loc[sched["round"] == rnd]
    if row.empty:
        raise KeyError(f"no round {rnd} in {season}")
    race_date = row["date"].iloc[0]
    assert_not_holdout(race_date, allow_holdout=allow_holdout)

    lap_rows = [
        {
            "driver": t["driverId"],
            "lap": int(lap["number"]),
            "position": int(t["position"]),
            "time_s": parse_time(t.get("time")),
        }
        for race in client.get_races(f"{season}/{rnd}/laps")
        for lap in race.get("Laps", [])
        for t in lap["Timings"]
    ]
    pit_rows = [
        {
            "driver": p["driverId"],
            "lap": int(p["lap"]),
            "stop": int(p["stop"]),
            "duration_s": parse_time(p.get("duration")),
        }
        for race in client.get_races(f"{season}/{rnd}/pitstops")
        for p in race.get("PitStops", [])
    ]
    res_rows = [
        {
            "driver": r["Driver"]["driverId"],
            "grid": int(r["grid"]),
            "position": int(r["position"]),
            "laps": int(r["laps"]),
            "status": r["status"],
            "classified": r["positionText"].isdigit(),
        }
        for race in client.get_races(f"{season}/{rnd}/results")
        for r in race.get("Results", [])
    ]
    return Race(
        season=season,
        round=rnd,
        name=row["name"].iloc[0],
        date=race_date,
        laps=pd.DataFrame(lap_rows, columns=["driver", "lap", "position", "time_s"]),
        pitstops=pd.DataFrame(pit_rows, columns=["driver", "lap", "stop", "duration_s"]),
        results=pd.DataFrame(res_rows, columns=["driver", "grid", "position", "laps", "status", "classified"]),
    )


def check_race(race: Race) -> dict:
    """Data check rules D1 to D3 for one race (spec 01, amendment A1)."""
    cls = race.results[race.results["classified"]]
    expected = int(cls["laps"].sum())
    have = int(race.laps[race.laps["driver"].isin(cls["driver"])].shape[0])
    lap_keys = set(zip(race.laps["driver"], race.laps["lap"]))
    pit_ok = [(d, lap) in lap_keys for d, lap in zip(race.pitstops["driver"], race.pitstops["lap"])]
    last = race.laps.sort_values("lap").groupby("driver").tail(1).set_index("driver")["position"]
    order_ok = [last.get(d) == p for d, p in zip(cls["driver"], cls["position"])]
    return {
        "season": race.season,
        "round": race.round,
        "name": race.name,
        "lap_coverage": have / expected if expected else float("nan"),
        "pitstop_on_known_lap": sum(pit_ok) / len(pit_ok) if pit_ok else 1.0,
        "last_lap_order_match": sum(order_ok) / len(order_ok) if order_ok else float("nan"),
        "n_pitstops": len(pit_ok),
        "n_classified": int(cls.shape[0]),
    }
