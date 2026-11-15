from datetime import date

import pytest

from pitwall.splits import HoldoutError, assert_not_holdout, split_of


def test_split_by_date():
    assert split_of(date(2024, 5, 26)) == "pretrain"
    assert split_of(date(2026, 3, 8)) == "development"
    assert split_of(date(2026, 8, 31)) == "development"
    assert split_of(date(2026, 9, 1)) == "holdout"
    with pytest.raises(ValueError):
        split_of(date(2021, 12, 12))


def test_holdout_is_locked():
    with pytest.raises(HoldoutError):
        assert_not_holdout([date(2026, 6, 1), date(2026, 10, 25)])
    assert_not_holdout(date(2026, 10, 25), allow_holdout=True)
    assert_not_holdout([date(2025, 12, 7), date(2026, 6, 1)])
