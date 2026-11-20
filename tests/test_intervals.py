import math

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from pitwall.intervals import conformal_offsets, coverage


def test_offsets_are_order_statistics():
    r = np.arange(1, 100, dtype=float)  # 1 .. 99, n = 99
    lo, hi = conformal_offsets(r, 0.2)
    # rank = ceil(100 * 0.9) = 90: hi is the 90th smallest, lo is the 90th largest (= 10th smallest)
    assert hi == 90.0 and lo == 10.0


def test_too_few_residuals_give_an_infinite_interval():
    lo, hi = conformal_offsets([0.1, -0.2, 0.3], 0.05)
    assert lo == -math.inf and hi == math.inf


def test_skewed_residuals_give_an_asymmetric_interval():
    rng = np.random.default_rng(0)
    r = rng.exponential(1.0, 5000) - 0.5  # long right tail, as laps in traffic
    lo, hi = conformal_offsets(r, 0.2)
    assert hi > abs(lo) * 2


def test_bad_input():
    with pytest.raises(ValueError):
        conformal_offsets([1.0], 0.0)
    with pytest.raises(ValueError):
        conformal_offsets([np.nan], 0.1)


def test_coverage_counts_the_ends():
    assert coverage([0, 1, 2, 3], [0, 0, 0, 0], [1, 1, 1, 1]) == 0.5


@settings(max_examples=40, deadline=None)
@given(seed=st.integers(0, 10_000), alpha=st.sampled_from([0.05, 0.1, 0.2]))
def test_exchangeable_residuals_reach_the_target_coverage(seed, alpha):
    # With exchangeable residuals, the average coverage over many new points is at least 1 - alpha (minus noise).
    rng = np.random.default_rng(seed)
    cal = rng.standard_t(3, 2000)
    new = rng.standard_t(3, 20_000)
    lo, hi = conformal_offsets(cal, alpha)
    cov = coverage(new, np.full(new.size, lo), np.full(new.size, hi))
    assert cov >= 1 - alpha - 0.03


@given(st.lists(st.floats(-50, 50), min_size=1, max_size=200), st.sampled_from([0.05, 0.2, 0.5]))
def test_lower_offset_never_above_upper(resid, alpha):
    lo, hi = conformal_offsets(resid, alpha)
    assert lo <= hi
