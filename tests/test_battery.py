import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from pitwall.battery import Limits, simulate_lap

# Test values only. They are not the FIA limits.
LIM = Limits(capacity_mj=4.0, max_deploy_kw=350.0, max_harvest_kw=350.0, max_harvest_per_lap_mj=7.0)


def test_power_is_clipped_to_the_power_limits():
    r = simulate_lap(np.array([500.0, -500.0]), 1.0, 2.0, LIM)
    assert r.power_kw.tolist() == [350.0, -350.0]


def test_cannot_deploy_more_than_the_charge():
    r = simulate_lap(np.full(10, 350.0), 1.0, 1.0, LIM)
    assert r.deployed_mj == pytest.approx(1.0)
    assert r.charge_mj[-1] == pytest.approx(0.0)


def test_cannot_charge_above_capacity():
    r = simulate_lap(np.full(20, -350.0), 1.0, 3.5, LIM)
    assert r.charge_mj.max() == pytest.approx(4.0)
    assert r.harvested_mj == pytest.approx(0.5)


def test_harvest_budget_per_lap():
    small = Limits(capacity_mj=100.0, max_deploy_kw=350.0, max_harvest_kw=350.0, max_harvest_per_lap_mj=1.0)
    r = simulate_lap(np.full(10, -350.0), 1.0, 0.0, small)
    assert r.harvested_mj == pytest.approx(1.0)


@settings(max_examples=200)
@given(
    st.lists(st.floats(-1000, 1000), min_size=1, max_size=60),
    st.floats(0.05, 2.0),
    st.floats(0.0, 4.0),
)
def test_energy_balance_and_bounds(power, dt, charge0):
    r = simulate_lap(np.array(power), dt, charge0, LIM)
    assert np.all(r.charge_mj >= -1e-9) and np.all(r.charge_mj <= LIM.capacity_mj + 1e-9)
    assert r.charge_mj[-1] == pytest.approx(charge0 + r.harvested_mj - r.deployed_mj, abs=1e-9)
    assert r.harvested_mj <= LIM.max_harvest_per_lap_mj + 1e-9


def test_bad_inputs_raise():
    with pytest.raises(ValueError):
        Limits(capacity_mj=0.0, max_deploy_kw=1.0, max_harvest_kw=1.0, max_harvest_per_lap_mj=1.0)
    with pytest.raises(ValueError):
        simulate_lap(np.zeros(3), 1.0, 5.0, LIM)
    with pytest.raises(ValueError):
        simulate_lap(np.zeros(3), 0.0, 1.0, LIM)
