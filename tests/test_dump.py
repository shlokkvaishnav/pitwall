import pytest

from pitwall.dump import Dump
from pitwall.splits import HoldoutError

TABLES = {
    "season": "id,api_id,championship_system_id,wikipedia,year\n1,s,1,w,2026\n",
    "round": (
        "id,api_id,circuit_id,date,is_cancelled,name,number,race_number,season_id,wikipedia\n"
        "10,r,1,2026-03-08,f,Test GP,1,1,1,w\n"
        "11,r,1,2026-10-04,f,Late GP,2,2,1,w\n"
        "12,r,1,2026-04-12,t,Cancelled GP,3,3,1,w\n"
    ),
    "session": (
        "id,api_id,completed_distance,completed_laps,has_time_data,is_cancelled,number,point_system_id,round_id,"
        "scheduled_laps,timestamp,timezone,type\n"
        "100,x,,,t,f,1,1,10,2,2026-03-08,UTC,Q1\n"
        "101,x,,,t,f,2,1,10,2,2026-03-08,UTC,R\n"
        "102,x,,,t,f,2,1,11,2,2026-10-04,UTC,R\n"
    ),
    "sessionentry": (
        "id,api_id,detail,driver_of_the_day_percentage,driver_of_the_day_winner,fastest_lap_rank,grid,is_classified,"
        "is_eligible_for_points,laps_completed,points,position,round_entry_id,session_id,status,time\n"
        "1000,e,Finished,,,,2,t,t,2,25,1,500,101,0,\n"
        "1001,e,Retired,,,,1,f,t,1,0,2,501,101,1,\n"
    ),
    "roundentry": "id,api_id,car_number,round_id,team_driver_id\n500,re,1,10,700\n501,re,2,10,701\n",
    "teamdriver": "id,api_id,driver_id,role,season_id,team_id\n700,t,900,,1,1\n701,t,901,,1,1\n",
    "driver": (
        "id,abbreviation,api_id,country_code,date_of_birth,forename,nationality,permanent_car_number,reference,"
        "surname,wikipedia\n900,AAA,d,X,2000-01-01,A,X,1,alpha,A,w\n901,BBB,d,X,2000-01-01,B,X,2,beta,B,w\n"
    ),
    "lap": (
        "id,api_id,average_speed,is_deleted,is_entry_fastest_lap,number,position,session_entry_id,time\n"
        "1,l,,f,t,,,1000,00:01:29.000\n"
        "2,l,,f,f,1,1,1000,00:01:30.000\n"
        "3,l,,f,f,2,1,1000,00:01:29.500\n"
        "4,l,,f,f,1,2,1001,00:01:31.000\n"
        "5,l,,t,f,2,2,1001,00:01:31.000\n"
    ),
    "pitstop": "id,api_id,duration,lap_id,local_timestamp,number,session_entry_id\n1,p,00:00:22.500,2,12:00,1,1000\n",
}


@pytest.fixture
def dump(tmp_path):
    for name, text in TABLES.items():
        (tmp_path / f"formula_one_{name}.csv").write_text(text)
    return Dump(tmp_path)


def test_schedule_skips_cancelled_rounds(dump):
    s = dump.schedule(2026)
    assert s["round"].tolist() == [1, 2]
    assert s["circuit_id"].tolist() == [1, 1]


def test_race_joins_tables(dump):
    r = dump.race(2026, 1)
    assert sorted(zip(r.laps["driver"], r.laps["lap"])) == [("alpha", 1), ("alpha", 2), ("beta", 1)]
    assert r.laps.loc[(r.laps["driver"] == "alpha") & (r.laps["lap"] == 2), "time_s"].item() == pytest.approx(89.5)
    assert r.pitstops[["driver", "lap", "stop"]].values.tolist() == [["alpha", 1, 1]]
    assert r.pitstops["duration_s"].item() == pytest.approx(22.5)
    assert r.results.set_index("driver")["classified"].to_dict() == {"alpha": True, "beta": False}


def test_holdout_race_is_refused(dump):
    with pytest.raises(HoldoutError):
        dump.race(2026, 2)
