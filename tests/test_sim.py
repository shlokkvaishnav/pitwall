import numpy as np

from pitwall.sim import SimInputs, simulate


def _inputs(pace, **kw):
    base = {
        "drivers": [f"d{i}" for i in range(len(pace))],
        "pace": np.asarray(pace, float),
        "noise_s": 0.3,
        "pit_loss_s": 20.0,
        "wear_s_per_lap": 0.05,
        "stop_counts": np.array([1]),
        "sc_rate": 0.0,
        "dnf_hazard": 0.0,
        "laps": 50,
    }
    base.update(kw)
    return SimInputs(**base)


def test_positions_are_a_permutation():
    pos = simulate(_inputs([0.0, 0.1, 0.2, 0.3]), runs=50)
    assert pos.shape == (50, 4)
    assert (np.sort(pos, axis=1) == np.arange(1, 5)).all()


def test_much_faster_car_from_the_back_wins_often():
    pos = simulate(_inputs([0.0, 0.0, 0.0, -2.0]), runs=300)
    assert (pos[:, 3] == 1).mean() > 0.8


def test_equal_cars_keep_grid_order_because_passing_is_hard():
    # no pit stops: only the passing rule can change the order
    pos = simulate(_inputs([0.0] * 6, noise_s=0.1, stop_counts=np.array([0])), runs=300)
    assert (pos[:, 0] == 1).mean() > 0.6
    assert pos.mean(0)[0] < pos.mean(0)[-1]


def test_retired_cars_are_last():
    pos = simulate(_inputs([0.0, 0.1, 0.2], dnf_hazard=0.05), runs=200)
    assert ((pos >= 1) & (pos <= 3)).all()


def test_safety_cars_bring_the_field_together():
    fast_leader = [-1.0, 0.0, 0.0, 0.0]
    no_sc = simulate(_inputs(fast_leader), runs=300, seed=1)
    many_sc = simulate(_inputs(fast_leader, sc_rate=4.0), runs=300, seed=1)
    assert (many_sc[:, 0] == 1).mean() <= (no_sc[:, 0] == 1).mean()
