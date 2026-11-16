"""Race splits and the holdout lock (see specs/00-charter.md, section 4)."""

from __future__ import annotations

from datetime import date

EARLY_SEASON = 2018  # charter amendment A2: 2018 to 2021 for the undercut replication (spec 09) only
FIRST_SEASON = 2022
ENERGY_SEASON = 2026  # first season of the current power unit rules
HOLDOUT_START = date(2026, 9, 1)


class HoldoutError(RuntimeError):
    """A development step tried to use a locked holdout race."""


def split_of(race_date: date) -> str:
    """Return 'early', 'pretrain', 'development' or 'holdout' for a race date."""
    if race_date.year < EARLY_SEASON:
        raise ValueError(f"race before {EARLY_SEASON} is out of scope: {race_date}")
    if race_date.year < FIRST_SEASON:
        return "early"
    if race_date.year < ENERGY_SEASON:
        return "pretrain"
    return "holdout" if race_date >= HOLDOUT_START else "development"


def assert_not_holdout(race_dates, *, allow_holdout: bool = False) -> None:
    """Raise HoldoutError if a race is in the holdout. Only the final spec sets allow_holdout."""
    items = [race_dates] if isinstance(race_dates, date) else list(race_dates)
    bad = sorted(d for d in items if split_of(d) == "holdout")
    if bad and not allow_holdout:
        raise HoldoutError(f"these races are in the locked holdout: {[d.isoformat() for d in bad]}")
