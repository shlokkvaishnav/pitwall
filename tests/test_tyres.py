import json
from datetime import date

import pandas as pd

from pitwall.data import Race
from pitwall.tyres import join, parse, url


def test_url_quotes_the_grand_prix_name():
    assert url(2026, "Australian Grand Prix").endswith(
        "/2026/main/Australian%20Grand%20Prix/Race/session_laptimes.json"
    )


def test_parse_and_join(tmp_path):
    f = tmp_path / "r.json"
    f.write_text(
        json.dumps(
            {
                "drv": ["AAA", "AAA", "BBB"],
                "lap": [1, 2, 1],
                "time": [90.0, "None", 91.0],
                "compound": ["SOFT", "HARD", "INTERMEDIATE"],
                "life": [1, 1, 3],
                "stint": [1, 2, 1],
            }
        )
    )
    t = parse(f)
    assert t["hardness"].tolist()[:2] == [1, 3]
    assert pd.isna(t["hardness"].iloc[2])
    laps = pd.DataFrame({"driver": ["alpha", "alpha", "beta"], "lap": [1, 2, 1], "time_s": [90.0, 89.0, 91.0]})
    race = Race(2026, 1, "x", date(2026, 3, 1), laps, pd.DataFrame(), pd.DataFrame())
    j = join(race, t, {"AAA": "alpha", "BBB": "beta"})
    assert j["compound"].tolist() == ["SOFT", "HARD", "INTERMEDIATE"]
    assert j["time_diff_s"].iloc[0] == 0.0
