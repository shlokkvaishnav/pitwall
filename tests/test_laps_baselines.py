from datetime import date

import numpy as np
import pandas as pd
import pytest

from pitwall.baselines import linear_stint, local_trend, mae, previous_lap
from pitwall.data import Race
from pitwall.laps import clean_mask, lap_table


def _race(n_laps=30, pit_lap=15, sc_lap=None):
    """Two drivers. Lap time = 90 s + 0.1 s per lap of tyre age. Driver 'a' pits once."""
    rows = []
    for d, base in (("a", 90.0), ("b", 90.5)):
        age = 0
        for lap in range(1, n_laps + 1):
            age += 1
            t = base + 0.1 * age
            if sc_lap and lap == sc_lap:
                t *= 1.4
            rows.append({"driver": d, "lap": lap, "position": 1 if d == "a" else 2, "time_s": t})
            if d == "a" and lap == pit_lap:
                age = 0
    laps = pd.DataFrame(rows)
    pits = pd.DataFrame([{"driver": "a", "lap": pit_lap, "stop": 1, "duration_s": 22.0}])
    res = pd.DataFrame(columns=["driver", "grid", "position", "laps", "status", "classified"])
    return Race(2026, 1, "Test GP", date(2026, 3, 8), laps, pits, res)


def test_stints_tyre_age_and_pit_flags():
    t = lap_table(_race())
    a = t[t["driver"] == "a"].set_index("lap")
    assert a.loc[15, "in_lap"] and a.loc[16, "out_lap"]
    assert a.loc[15, "stint"] == 1 and a.loc[16, "stint"] == 2
    assert a.loc[16, "tyre_age"] == 1 and a.loc[30, "tyre_age"] == 15
    assert (t[t["driver"] == "b"]["stint"] == 1).all()


def test_neutral_lap_detection():
    t = lap_table(_race(sc_lap=10))
    assert t.loc[t["lap"] == 10, "neutral"].all()
    assert t.loc[t["lap"] == 1, "neutral"].all()
    assert not t.loc[t["lap"] == 11, "neutral"].any()
    assert not clean_mask(t)[t["lap"] == 10].any()


def test_official_neutral_laps_replace_the_detector():
    t = lap_table(_race(sc_lap=10), official_neutral={1, 20, 21})
    assert t.loc[t["lap"].isin([1, 20, 21]), "neutral"].all()
    assert not t.loc[t["lap"] == 10, "neutral"].any()  # slow lap, but not officially neutral


def test_baselines_are_causal_and_linear_is_exact():
    t = lap_table(_race())
    lin = linear_stint(t)
    enough = t["tyre_age"] >= 6  # at least 3 earlier clean laps in the stint
    assert mae(lin[enough], t[enough]) == pytest.approx(0.0, abs=1e-9)
    prev = previous_lap(t)
    assert mae(prev, t) == pytest.approx(0.1, abs=1e-9)  # one lap of wear behind
    # the first lap of each stint has no earlier clean lap, so no prediction
    assert np.isnan(prev[(t["driver"] == "a") & (t["lap"] == 2)]).all()


def test_local_trend_learns_the_wear_rate():
    t = lap_table(_race(n_laps=60, pit_lap=59))
    pred = local_trend(t)
    late = (t["lap"] > 40) & clean_mask(t) & pred.notna()
    assert (pred[late] - t.loc[late, "time_s"]).abs().max() < 0.1
