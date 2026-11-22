import numpy as np

from pitwall.sim import SimInputs
from pitwall.strategy_env import Race, World, fixed_policy, history_policy, run


class NoPass:
    def gbm_fast(self, circuit_id, gap, pace_delta, tyre_age_diff, race_frac):
        return np.zeros(len(gap))


def _world(hazard=0.0, laps=30):
    inp = SimInputs(
        drivers=[f"d{i}" for i in range(8)], pace=np.linspace(0, 1.4, 8), noise_s=0.2, pit_loss_s=20.0,
        wear_s_per_lap=0.08, stop_counts=np.array([1]), sc_rate=0.0, dnf_hazard=0.0, laps=laps,
    )  # fmt: skip
    return World(inp, np.full(laps + 1, hazard), NoPass(), circuit_id=1, ego=4)


def test_fixed_policy_pits_on_its_laps_and_finishes_in_the_field():
    pos, laps = run(_world(), seed=0, policy=fixed_policy([15]))
    assert laps == [15] and 1 <= pos <= 8


def test_no_stop_counts_as_last():
    pos, laps = run(_world(), seed=0, policy=lambda r: False)
    assert laps == [] and pos == 8


def test_same_seed_same_race_and_history_policy_stops_once():
    a = run(_world(), seed=3, policy=fixed_policy([12]))
    b = run(_world(), seed=3, policy=fixed_policy([12]))
    assert a == b
    _, laps = run(_world(), seed=3, policy=history_policy)
    assert len(laps) == 1


def test_neutral_period_bunches_the_field():
    r = Race(_world(hazard=1.0), seed=0)
    for _ in range(3):
        r.step(False)
    gaps = np.diff(np.sort(r.cum))
    assert r.sc_left >= 0 and np.all(gaps < 1.0)
    assert r.obs().shape == (7,)


def test_retirements_freeze_a_car_and_it_finishes_behind_the_runners():
    w = _world()
    w.inp.dnf_hazard = 0.05
    r = Race(w, seed=1, retirements=True)
    while not r.done():
        r.step(False)
    pos = r.finish_positions()
    assert sorted(pos) == list(range(1, 9))
    out = ~r.alive
    if out.any() and r.alive.any():
        assert pos[out].min() > pos[r.alive].max()
