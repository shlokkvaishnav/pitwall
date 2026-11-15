import math

import pytest

from pitwall.data import Jolpica, check_race, load_race, parse_time
from pitwall.splits import HoldoutError

RACE = {"season": "2026", "round": "1", "raceName": "Test GP", "date": "2026-03-08"}


def _page(races, total, limit=100):
    return {"MRData": {"limit": str(limit), "total": str(total), "RaceTable": {"Races": races}}}


def _fake_api(calls):
    def fetch(url):
        calls.append(url)
        if "/2026/1/laps/" in url:
            # one lap split over two pages
            if "offset=0" in url:
                lap = {"number": "1", "Timings": [{"driverId": "a", "position": "1", "time": "1:30.000"}]}
                return _page([{**RACE, "Laps": [lap]}], total=3, limit=1)
            if "offset=1" in url:
                lap = {"number": "1", "Timings": [{"driverId": "b", "position": "2", "time": "1:31.500"}]}
                return _page([{**RACE, "Laps": [lap]}], total=3, limit=1)
            lap = {"number": "2", "Timings": [{"driverId": "a", "position": "1", "time": "1:29.000"}]}
            return _page([{**RACE, "Laps": [lap]}], total=3, limit=1)
        if "/2026/1/pitstops/" in url:
            return _page([{**RACE, "PitStops": [{"driverId": "a", "lap": "1", "stop": "1", "duration": "22.5"}]}], 1)
        if "/2026/1/results/" in url:
            res = [
                {
                    "Driver": {"driverId": "a"},
                    "grid": "2",
                    "position": "1",
                    "positionText": "1",
                    "laps": "2",
                    "status": "Finished",
                },
                {
                    "Driver": {"driverId": "b"},
                    "grid": "1",
                    "position": "2",
                    "positionText": "R",
                    "laps": "1",
                    "status": "Retired",
                },
            ]
            return _page([{**RACE, "Results": res}], 2)
        if url.split("?")[0].endswith("/2026/"):
            late = {"season": "2026", "round": "2", "raceName": "Late GP", "date": "2026-10-04"}
            return _page([RACE, late], 2)
        raise AssertionError(url)

    return fetch


def test_parse_time():
    assert parse_time("1:23.456") == pytest.approx(83.456)
    assert parse_time("23.4") == pytest.approx(23.4)
    assert parse_time("00:01:16.29") == pytest.approx(76.29)
    assert math.isnan(parse_time(None)) and math.isnan(parse_time(float("nan")))
    assert math.isnan(parse_time("")) and math.isnan(parse_time("DNF"))


def test_load_race_merges_pages_and_caches(tmp_path):
    calls = []
    client = Jolpica(tmp_path, min_interval_s=0, fetch=_fake_api(calls))
    race = load_race(client, 2026, 1)
    assert sorted(zip(race.laps["driver"], race.laps["lap"])) == [("a", 1), ("a", 2), ("b", 1)]
    assert race.pitstops["duration_s"].tolist() == [22.5]
    assert race.results["classified"].tolist() == [True, False]
    n = len(calls)
    load_race(client, 2026, 1)
    assert len(calls) == n  # second load uses the cache only

    check = check_race(race)
    assert check["lap_coverage"] == 1.0 and check["pitstop_on_known_lap"] == 1.0
    assert check["last_lap_order_match"] == 1.0


def test_holdout_race_is_refused_before_download(tmp_path):
    calls = []
    client = Jolpica(tmp_path, min_interval_s=0, fetch=_fake_api(calls))
    with pytest.raises(HoldoutError):
        load_race(client, 2026, 2)
    assert not any("/2026/2/" in c for c in calls)
