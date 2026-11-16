from datetime import date

import pandas as pd

from pitwall.data import Race
from pitwall.undercut import duels


def _race(times_a, times_b, pit_a, pit_b, extra=None):
    rows = []
    for d, ts in (("a", times_a), ("b", times_b), *(extra or [])):
        rows += [{"driver": d, "lap": i + 1, "position": pd.NA, "time_s": t} for i, t in enumerate(ts)]
    pits = pd.DataFrame(
        {"driver": ["a", "b"], "lap": pd.array([pit_a, pit_b], dtype="Int64"), "stop": [1, 1], "duration_s": [2.5, 2.5]}
    )
    return Race(2026, 1, "Test", date(2026, 3, 1), pd.DataFrame(rows), pits, pd.DataFrame())


def test_successful_undercut():
    # b leads by 1 s after lap 4 (b starts 1 s ahead). a pits on lap 5, b on lap 7. a is faster on new tyres.
    a = [91.0, 90, 90, 90, 110, 88, 88, 88, 90, 90]
    b = [90.0, 90, 90, 90, 90, 90, 90, 110, 89, 90]
    d = duels(_race(a, b, 5, 7))
    assert len(d) == 1
    row = d.iloc[0]
    assert (row["a"], row["b"], row["lap_a"], row["lap_b"], row["wait_laps"]) == ("a", "b", 5, 7, 2)
    assert row["gap_s"] == 1.0
    assert row["age_a"] == 5 and row["age_b"] == 5
    assert bool(row["a_ahead"])


def test_no_duel_when_gap_is_large_or_no_response():
    a = [95.0, 90, 90, 90, 110, 88, 88, 88, 90, 90]
    b = [90.0, 90, 90, 90, 90, 90, 90, 110, 89, 90]
    assert duels(_race(a, b, 5, 7)).empty  # 5 s gap
    a[0] = 91.0
    assert duels(_race(a, b, 5, 10)).empty  # b pits 5 laps later but lap 11 does not exist
    assert duels(_race(a, b, 5, 2)).empty  # b pitted before a


def test_no_duel_with_a_neutralised_lap():
    a = [91.0, 90, 90, 90, 110, 88, 140, 88, 90, 90]
    b = [90.0, 90, 90, 90, 90, 90, 140, 110, 89, 90]
    c = [93.0, 90, 90, 90, 90, 90, 140, 90, 90, 90]
    assert duels(_race(a, b, 5, 7, extra=[("c", c)])).empty
