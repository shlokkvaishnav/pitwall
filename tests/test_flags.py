from pitwall.flags import neutral_laps, sector_yellows


def m(lap, cat, msg="", flag=None, scope=None, t=None):
    return {"lap_number": lap, "category": cat, "message": msg, "flag": flag, "scope": scope, "date": t or f"{lap:03d}"}


def test_safety_car_inclusive_and_lap_one():
    msgs = [m(5, "SafetyCar", "SAFETY CAR DEPLOYED"), m(8, "SafetyCar", "SAFETY CAR IN THIS LAP")]
    laps = neutral_laps(msgs, 50)
    assert sorted(laps) == [1, 5, 6, 7, 8]
    assert laps[1] == {"start"} and laps[6] == {"sc"}


def test_vsc_is_not_read_as_safety_car():
    msgs = [m(10, "SafetyCar", "VIRTUAL SAFETY CAR DEPLOYED"), m(11, "SafetyCar", "VIRTUAL SAFETY CAR ENDING")]
    laps = neutral_laps(msgs, 50)
    assert laps[10] == {"vsc"} and laps[11] == {"vsc"} and 12 not in laps


def test_red_flag_until_restart_and_unclosed_period_runs_to_end():
    msgs = [
        m(20, "Flag", "RED FLAG", flag="RED", scope="Track", t="a"),
        m(20, "SessionStatus", "SESSION ABORTED", t="b"),
        m(21, "SessionStatus", "SESSION STARTED", t="c"),
        m(48, "SafetyCar", "SAFETY CAR DEPLOYED", t="d"),
    ]
    laps = neutral_laps(msgs, 50)
    assert laps[20] == {"red"} and laps[21] == {"red"} and 22 not in laps
    assert all(laps[k] == {"sc"} for k in (48, 49, 50))


def test_messages_without_lap_and_sector_yellows_are_ignored():
    msgs = [
        m(None, "SafetyCar", "SAFETY CAR DEPLOYED", t="000"),
        m(3, "Flag", "YELLOW IN TRACK SECTOR 2", flag="YELLOW", scope="Sector"),
    ]
    assert sorted(neutral_laps(msgs, 10)) == [1]
    assert sector_yellows(msgs) == 1
