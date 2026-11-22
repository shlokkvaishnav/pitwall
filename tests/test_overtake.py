from datetime import date

import pandas as pd

from pitwall.data import Race
from pitwall.overtake import pair_laps


def _race():
    """Three cars, 10 laps. 'b' is 0.3 s/lap faster than 'a' and starts 1.0 s behind, so it passes on lap 4."""
    rows = []
    for d, base, start in (("a", 90.0, 0.0), ("b", 89.7, 1.0), ("c", 91.0, 5.0)):
        cum = 0.0
        for lap in range(1, 11):
            t = base + (start if lap == 1 else 0.0)
            cum += t
            rows.append({"driver": d, "lap": lap, "time_s": t, "_cum": cum})
    laps = pd.DataFrame(rows)
    laps["position"] = laps.groupby("lap")["_cum"].rank().astype(int)
    pits = pd.DataFrame(columns=["driver", "lap", "stop", "duration_s"])
    res = pd.DataFrame(columns=["driver", "grid", "position", "laps", "status", "classified"])
    return Race(2025, 1, "Test GP", date(2025, 3, 1), laps.drop(columns="_cum"), pits, res)


def test_pair_laps_label_the_pass_and_measure_the_gap():
    p = pair_laps(_race(), circuit_id=7)
    ab = p[(p["a"] == "a") & (p["b"] == "b")]
    assert ab["passed"].sum() == 1  # one pass between a and b
    first = ab.iloc[0]
    assert abs(first["gap"] - 0.4) < 1e-9 and first["drs"] == 1.0 and abs(first["pace_delta"] - 0.3) < 1e-9
    assert (p["gap"] <= 3.0).all() and (p["lap"] >= 3).all()
