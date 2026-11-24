import numpy as np
from scipy.special import expit

from pitwall.fastsim import NO_LAP, State, sample_plans, simulate
from pitwall.sim import SimInputs
from pitwall.strategy_env import Race, World


class Logit:
    """A small passing model: more likely when the car behind is faster and close."""

    def gbm_fast(self, circuit_id, gap, pace_delta, tyre_age_diff, race_frac, memo=False):
        return expit(-1.5 + 2.0 * pace_delta - 1.0 * gap)


def _world(laps=30, d=8, dnf=0.0, hazard=0.03, ego=4):
    inp = SimInputs(
        drivers=[f"d{i}" for i in range(d)], pace=np.linspace(0, 1.4, d), noise_s=0.5, pit_loss_s=20.0,
        wear_s_per_lap=0.08, stop_counts=np.array([1, 1, 2]), sc_rate=0.0, dnf_hazard=dnf, laps=laps,
        pace_shock_s=0.3,
    )  # fmt: skip
    return World(inp, np.full(laps + 1, hazard), Logit(), circuit_id=1, ego=ego)


def _old(world, runs, retirements=False):
    """`Race` with no ego car (ego index outside the field), so every car follows the plan rule inside `step`."""
    out = np.empty((runs, len(world.inp.drivers)), int)
    stops = np.empty_like(out)
    for i in range(runs):
        r = Race(world, i, retirements=retirements)
        while not r.done():
            r.step(False)
        out[i], stops[i] = r.finish_positions(), r.stops
    return out, stops


def test_same_distribution_as_the_one_race_simulator():
    w = _world(dnf=0.003, ego=99)
    old, old_stops = _old(w, 1500, retirements=True)
    new = simulate(w, 6000, seed=0)
    se = np.sqrt(old.var(0) / len(old) + new.positions.var(0) / len(new.positions))
    z = (old.mean(0) - new.positions.mean(0)) / se
    assert np.abs(z).max() < 4.0, z
    for p in (1, 3):  # chance of finishing in the top p
        a, b = (old <= p).mean(0), (new.positions <= p).mean(0)
        assert np.abs(a - b).max() < 0.05
    assert abs(old_stops.mean() - new.stops.mean()) < 0.05


def test_same_seed_same_races_and_positions_are_a_permutation():
    w = _world(dnf=0.01)
    a, b = simulate(w, 200, seed=7), simulate(w, 200, seed=7)
    assert np.array_equal(a.positions, b.positions)
    assert (np.sort(a.positions, 1) == np.arange(1, 9)).all()
    assert not np.array_equal(a.positions, simulate(w, 200, seed=8).positions)


def test_plans_are_sorted_unique_and_inside_the_race():
    w = _world()
    p = sample_plans(w, np.random.default_rng(0), 500)
    real = p[p < NO_LAP]
    assert real.min() >= 2 and real.max() <= w.inp.laps - 1
    for row in p.reshape(-1, p.shape[-1]):
        r = row[row < NO_LAP]
        assert len(set(r)) == len(r) and list(r) == sorted(r)


def test_start_from_a_race_in_progress_and_a_fixed_ego_plan():
    w = _world(hazard=0.0)
    s = State(lap=20, cum=np.arange(8) * 30.0, age=np.full(8, 20.0), stops=np.zeros(8, int), alive=np.ones(8, bool))
    b = simulate(w, 300, seed=0, state=s, ego=4, ego_plan=np.array([25]))
    assert (b.stops[:, 4] == 1).all()  # the ego car stops once, on its plan
    assert (b.stops >= 1).all()  # cars that have not stopped yet must stop
    assert (b.positions[:, 0] == 1).mean() > 0.9  # a 30 s lead with 10 laps left holds
    late = simulate(w, 300, seed=0, state=s, ego=4, ego_plan=np.array([NO_LAP]))
    assert (late.stops[:, 4] == 0).all()
