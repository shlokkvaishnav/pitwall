from datetime import date

import numpy as np
import pandas as pd

from pitwall.data import Race
from pitwall.evaluate import dm_block_bootstrap
from pitwall.features import FEATURES, build
from pitwall.laps import lap_table


def _race():
    rows = []
    for lap in range(1, 21):
        rows.append({"driver": "a", "lap": lap, "position": 1, "time_s": 90.0 + 0.1 * lap})
        rows.append({"driver": "b", "lap": lap, "position": 2, "time_s": 90.5 + 0.1 * lap})
    laps = pd.DataFrame(rows)
    empty = pd.DataFrame(columns=["driver", "lap", "stop", "duration_s"])
    res = pd.DataFrame(columns=["driver", "grid", "position", "laps", "status", "classified"])
    return Race(2026, 1, "T", date(2026, 3, 8), laps, empty, res)


def test_features_are_causal():
    f = build(lap_table(_race())).set_index(["driver", "lap"])
    assert set(FEATURES) <= set(f.columns)
    assert f.loc[("a", 5), "last1"] == 90.4 and f.loc[("a", 5), "last2"] == 90.3 and f.loc[("a", 5), "last3"] == 90.2
    assert f.loc[("a", 5), "delta"] == np.float64(90.5) - 90.4
    assert np.isnan(f.loc[("a", 2), "last1"])  # lap 1 is neutral, so lap 2 has no earlier clean lap


def test_gap_to_car_ahead_uses_the_previous_lap():
    f = build(lap_table(_race())).set_index(["driver", "lap"])
    # after lap 3, b is 3 x 0.5 s behind a
    assert np.isclose(f.loc[("b", 4), "gap_ahead"], 1.5)
    assert np.isnan(f.loc[("a", 4), "gap_ahead"])
    assert f.loc[("b", 4), "ahead_lt_2s"] == 1.0 and f.loc[("b", 4), "ahead_lt_1s"] == 0.0


def test_dm_detects_a_better_model_and_not_an_equal_one():
    rng = np.random.default_rng(1)
    groups = np.repeat(np.arange(10), 100)
    base = rng.normal(0, 1.0, 1000)
    better = base * 0.7
    assert dm_block_bootstrap(better, base, groups)["p_value"] < 0.01
    same = rng.normal(0, 1.0, 1000)
    assert dm_block_bootstrap(same, base, groups)["p_value"] > 0.05
