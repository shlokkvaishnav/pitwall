import numpy as np
import pandas as pd

from pitwall.hazard import Models, event_laps, log_loss, race_rows


def test_events_merge_sc_into_red_and_skip_start_mark():
    off = {1: {"start"}, 5: {"sc"}, 6: {"sc", "red"}, 7: {"red"}, 9: {"vsc"}}
    t = event_laps(off, 10).set_index("lap")
    assert not t.loc[1, "event"] and t.loc[1, "at_risk"]
    assert t.loc[5, "event"] and t.loc[5, "kind"] == "sc"
    assert not t.loc[6, "at_risk"] and not t.loc[7, "at_risk"] and not t.loc[8, "at_risk"]
    assert t.loc[9, "event"] and t.loc[9, "kind"] == "vsc"
    assert t["event"].sum() == 2


def test_lap_one_period_is_an_event():
    t = event_laps({1: {"start", "sc"}, 2: {"sc"}}, 5).set_index("lap")
    assert t.loc[1, "event"] and not t.loc[2, "at_risk"]


def test_m2_learns_a_lap_one_effect_and_beats_m0():
    rng = np.random.default_rng(0)
    rows = []
    for i in range(300):
        circuit = i % 10
        off = {1: {"start"}}
        if rng.random() < 0.4:
            off[1] = {"start", "sc"}
        else:
            for lap in range(2, 50):
                if rng.random() < 0.01:
                    off[lap] = {"vsc"}
                    break
        rows.append(race_rows(off, 50, season=2020 + i % 4, round=i, circuit_id=circuit))
    t = pd.concat(rows, ignore_index=True)
    m = Models(t)
    p = m.predict(t)
    assert m.w[1] > 2.0  # lap 1 is much riskier than other laps
    y = t["event"].to_numpy()
    assert log_loss(y, p["M2"]) < log_loss(y, p["M0"])
