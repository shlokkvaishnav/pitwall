import numpy as np
import pytest

from pitwall.battery import simulate_lap
from pitwall.regs import deploy_limit_kw, race_limits


def test_deploy_curve_normal_mode():
    v = np.array([100.0, 290.0, 300.0, 339.0, 340.0, 344.0, 345.0, 360.0])
    # 1800 - 5v is capped at 350 kW up to 290 km/h; 100 kW at 340; 20 kW at 344; 0 from 345
    assert deploy_limit_kw(v).tolist() == [350.0, 350.0, 300.0, 105.0, 100.0, 20.0, 0.0, 0.0]


def test_deploy_curve_is_continuous_at_340():
    left = deploy_limit_kw(339.999)
    assert float(left) == pytest.approx(100.0, abs=0.01)


def test_overtake_mode():
    v = np.array([300.0, 337.5, 350.0, 355.0])
    assert deploy_limit_kw(v, overtake=True).tolist() == [350.0, 350.0, 100.0, 0.0]


def test_power_limited_mode():
    v = np.array([200.0, 309.0, 310.0, 345.0])
    assert deploy_limit_kw(v, power_limited=True).tolist() == [250.0, 250.0, 250.0, 0.0]
    with pytest.raises(ValueError):
        deploy_limit_kw(v, overtake=True, power_limited=True)


def test_race_limits():
    assert race_limits().max_harvest_per_lap_mj == 8.5
    assert race_limits(reduced_recharge=True).max_harvest_per_lap_mj == 7.0
    assert race_limits(extra_harvest=True).max_harvest_per_lap_mj == 9.0
    assert race_limits().capacity_mj == 4.0


def test_speed_dependent_deploy_cap_in_the_battery():
    speeds = np.array([250.0, 330.0, 346.0])
    r = simulate_lap(np.full(3, 350.0), 1.0, 4.0, race_limits(), deploy_cap_kw=deploy_limit_kw(speeds))
    assert r.power_kw.tolist() == [350.0, 150.0, 0.0]
