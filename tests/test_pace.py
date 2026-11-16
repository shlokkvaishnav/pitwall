import numpy as np
import pandas as pd
import pytest

from pitwall.pace import fit, form, qualifying_gap
from pitwall.sim import SimInputs, simulate


def test_qualifying_gap_fills_and_clips():
    best = pd.Series({"a": 80.0, "b": 81.0, "c": 99.0})
    gap = qualifying_gap(best, ["a", "b", "c", "d"])
    # median of [80, 81, 99, 99] is 90
    assert gap.tolist() == [-5.0, -5.0, 5.0, 5.0]
    gap = qualifying_gap(pd.Series({"a": 80.0, "b": 80.4, "c": 81.0}), ["a", "b", "c"])
    assert gap == pytest.approx([-0.4, 0.0, 0.6])


def test_form_is_mean_of_previous_races():
    assert form([{"a": 1.0}, {"a": 3.0, "b": 2.0}], ["a", "b", "c"]).tolist() == [2.0, 2.0, 0.0]


def test_fit_recovers_coefficients_and_skips_short_races():
    rng = np.random.default_rng(0)
    q, f = rng.normal(size=500), rng.normal(size=500)
    rows = pd.DataFrame({"q": q, "f": f, "pace": 0.8 * q + 0.3 * f + rng.normal(0, 0.1, 500), "clean_laps": 30})
    rows.loc[0, ["pace", "clean_laps"]] = [100.0, 3]
    p = fit(rows)
    assert p.beta_q == pytest.approx(0.8, abs=0.02)
    assert p.beta_f == pytest.approx(0.3, abs=0.02)
    assert p.sigma_r == pytest.approx(0.1, abs=0.02)
    assert p.n == 499


def test_pace_shock_spreads_the_result():
    base = {
        "drivers": ["a", "b", "c", "d"],
        "pace": np.array([0.0, 0.2, 0.4, 0.6]),
        "noise_s": 0.3,
        "pit_loss_s": 20.0,
        "wear_s_per_lap": 0.05,
        "stop_counts": np.array([1]),
        "sc_rate": 0.0,
        "dnf_hazard": 0.0,
        "laps": 50,
    }
    calm = simulate(SimInputs(**base), runs=400, seed=0)
    shaky = simulate(SimInputs(**base, pace_shock_s=0.5), runs=400, seed=0)
    assert (shaky[:, 0] == 1).mean() < (calm[:, 0] == 1).mean()
