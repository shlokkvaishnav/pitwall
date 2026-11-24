import json
import math
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from pitwall.data import Race
from pitwall.engine import live_pace, pit_window, plan_from, state_at, tyre_deg, undercut_probability
from pitwall.fastsim import State
from pitwall.laps import lap_table
from pitwall.sim import SimInputs
from pitwall.strategy_env import World

ROOT = Path(__file__).resolve().parents[1]


class NoPass:
    def gbm_fast(self, circuit_id, gap, pace_delta, tyre_age_diff, race_frac, memo=False):
        return np.zeros(len(gap))


def _race(deg=0.1, fuel=-0.05, laps=30):
    """Three cars, one stop each on lap 15 (car c retires after lap 20). Lap time = base + deg*age + fuel*lap."""
    rows, pits = [], []
    for i, d in enumerate("abc"):
        for lap in range(1, laps + 1):
            if d == "c" and lap > 20:
                break
            age = lap if lap <= 15 else lap - 15
            rows.append({"driver": d, "lap": lap, "position": i + 1, "time_s": 90 + i * 0.5 + deg * age + fuel * lap})
        pits.append({"driver": d, "lap": 15, "stop": 1, "duration_s": 22.0})
    res = pd.DataFrame({"driver": list("abc"), "grid": [1, 2, 3], "position": [1, 2, 3], "laps": [laps, laps, 20],
                        "status": ["Finished"] * 3, "classified": [True, True, False]})  # fmt: skip
    return Race(2025, 1, "T", date(2025, 3, 1), pd.DataFrame(rows), pd.DataFrame(pits), res)


def test_state_uses_only_laps_up_to_the_decision_lap():
    r = _race()
    s = state_at(r, ["a", "b", "c"], 10)
    t = r.laps
    assert math.isclose(s.cum[0], t[(t.driver == "a") & (t.lap <= 10)].time_s.sum())
    assert list(s.stops) == [0, 0, 0] and list(s.age) == [10, 10, 10] and s.alive.all()
    late = state_at(r, ["a", "b", "c"], 25)
    assert list(late.stops) == [1, 1, 1] and late.age[0] == 10
    assert not late.alive[2] and late.laps_done[2] == 20


def test_tyre_wear_is_net_of_fuel():
    assert abs(tyre_deg(_race(deg=0.1, fuel=-0.05)) - 0.1) < 1e-6


def test_live_pace_moves_from_the_prior_to_the_laps_run():
    r = _race(deg=0.0, fuel=0.0)
    t = lap_table(r)
    pace, w = live_pace(t, ["a", "b", "c"], 12, np.zeros(3))
    assert pace[0] < 0 < pace[2] and np.all(w < 1)


def test_undercut_probability_equals_the_site_test_vectors():
    model = json.loads((ROOT / "site" / "data" / "undercut-model.json").read_text())
    for v in model["test_vectors"]:
        p = undercut_probability(model, v["gap_s"], v["age_b"] - v["age_a"], v["laps_left"])
        assert abs(p - v["p"]) < 1e-5


def test_pit_window_finds_a_middle_stop_when_tyres_wear():
    inp = SimInputs(
        drivers=[f"d{i}" for i in range(8)], pace=np.linspace(0, 1.4, 8), noise_s=0.5, pit_loss_s=20.0,
        wear_s_per_lap=0.3, stop_counts=np.array([1]), sc_rate=0.0, dnf_hazard=0.0, laps=40,
    )  # fmt: skip
    w = World(inp, np.zeros(41), NoPass(), circuit_id=1)  # strong wear: one stop near half distance is best
    s = State(lap=1, cum=np.arange(8) * 0.3, age=np.ones(8), stops=np.zeros(8, int), alive=np.ones(8, bool))
    win = pit_window(w, s, 4, range(2, 39), runs=40, seed=0)
    assert 12 <= win.best <= 28 and win.contains(win.best)
    assert plan_from(10, 1, 40) == [10, 25]
