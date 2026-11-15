from itertools import pairwise

import numpy as np
import pytest

from pitwall.hmm import HMM2, fit, fit_ar1, predict_next


def _simulate(n_seq=200, length=30, seed=0):
    rng = np.random.default_rng(seed)
    trans = np.array([[0.8, 0.2], [0.3, 0.7]])
    mu, sigma = np.array([-0.5, 0.8]), np.array([0.3, 0.4])
    seqs = []
    for _ in range(n_seq):
        s = rng.integers(2)
        xs = []
        for _ in range(length):
            xs.append(rng.normal(mu[s], sigma[s]))
            s = rng.choice(2, p=trans[s])
        seqs.append(np.array(xs))
    return seqs, mu, sigma, trans


def test_em_recovers_the_parameters():
    seqs, mu, sigma, trans = _simulate()
    m, ll = fit(seqs)
    assert np.allclose(m.mu, mu, atol=0.05)
    assert np.allclose(m.sigma, sigma, atol=0.05)
    assert np.allclose(m.trans, trans, atol=0.05)
    assert all(b >= a - 1e-6 for a, b in pairwise(ll))  # EM does not decrease the likelihood


def test_prediction_is_causal_and_beats_the_mean():
    seqs, *_ = _simulate(seed=1)
    m, _ = fit(seqs[:150])
    x = seqs[150]
    p = predict_next(x, m)
    changed = x.copy()
    changed[10:] += 100.0
    assert np.allclose(predict_next(changed, m)[:11], p[:11])  # x[t] and later do not change prediction t
    test = seqs[150:]
    err_hmm = np.mean([np.abs(predict_next(s, m) - s).mean() for s in test])
    err_mean = np.mean([np.abs(s - np.concatenate(seqs[:150]).mean()).mean() for s in test])
    assert err_hmm < err_mean


def test_separation_and_ar1():
    m = HMM2(np.array([0.0, 2.0]), np.array([1.0, 1.0]), np.eye(2), np.array([0.5, 0.5]))
    assert m.separation() == pytest.approx(2.0)
    rng = np.random.default_rng(0)
    x = [0.0]
    for _ in range(5000):
        x.append(0.6 * x[-1] + rng.normal())
    assert fit_ar1([np.array(x)]) == pytest.approx(0.6, abs=0.03)
