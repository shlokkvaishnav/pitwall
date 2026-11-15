"""Two-state Gaussian hidden Markov model for lap-time residuals (specs/04-energy-regime.md)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

SIGMA_FLOOR = 1e-3


@dataclass
class HMM2:
    mu: np.ndarray  # (2,)
    sigma: np.ndarray  # (2,)
    trans: np.ndarray  # (2, 2), rows sum to 1
    start: np.ndarray  # (2,)

    def separation(self) -> float:
        """|mu1 - mu0| / pooled standard deviation."""
        return float(abs(self.mu[1] - self.mu[0]) / np.sqrt((self.sigma**2).mean()))

    def as_dict(self) -> dict:
        return {k: getattr(self, k).tolist() for k in ("mu", "sigma", "trans", "start")}


def _emission(x: np.ndarray, m: HMM2) -> np.ndarray:
    z = (x[:, None] - m.mu[None]) / m.sigma[None]
    return np.exp(-0.5 * z**2) / (np.sqrt(2 * np.pi) * m.sigma[None]) + 1e-300


def _forward_backward(x: np.ndarray, m: HMM2):
    t = len(x)
    e = _emission(x, m)
    alpha = np.zeros((t, 2))
    c = np.zeros(t)
    a = m.start * e[0]
    c[0] = a.sum()
    alpha[0] = a / c[0]
    for k in range(1, t):
        a = (alpha[k - 1] @ m.trans) * e[k]
        c[k] = a.sum()
        alpha[k] = a / c[k]
    beta = np.ones((t, 2))
    for k in range(t - 2, -1, -1):
        beta[k] = (m.trans @ (e[k + 1] * beta[k + 1])) / c[k + 1]
    gamma = alpha * beta
    xi = np.zeros((2, 2))
    for k in range(t - 1):
        xi += (alpha[k][:, None] * m.trans * (e[k + 1] * beta[k + 1])[None]) / c[k + 1]
    return gamma, xi, float(np.log(c).sum())


def fit(seqs: list[np.ndarray], iters: int = 200, tol: float = 1e-6, seed: int = 0) -> tuple[HMM2, list[float]]:
    """EM over many sequences. States are ordered so that mu[0] <= mu[1]."""
    seqs = [np.asarray(s, float) for s in seqs if len(s) > 0]
    allx = np.concatenate(seqs)
    rng = np.random.default_rng(seed)
    q = np.quantile(allx, [0.25, 0.75]) + rng.normal(0, 1e-6, 2)
    m = HMM2(
        mu=q,
        sigma=np.full(2, max(allx.std(), SIGMA_FLOOR)),
        trans=np.array([[0.9, 0.1], [0.1, 0.9]]),
        start=np.array([0.5, 0.5]),
    )
    history: list[float] = []
    for _ in range(iters):
        g_sum = np.zeros(2)
        gx = np.zeros(2)
        gxx = np.zeros(2)
        xi_sum = np.zeros((2, 2))
        start = np.zeros(2)
        ll = 0.0
        for x in seqs:
            gamma, xi, lls = _forward_backward(x, m)
            ll += lls
            g_sum += gamma.sum(0)
            gx += gamma.T @ x
            gxx += gamma.T @ (x**2)
            xi_sum += xi
            start += gamma[0]
        mu = gx / g_sum
        var = np.maximum(gxx / g_sum - mu**2, SIGMA_FLOOR**2)
        trans = xi_sum / xi_sum.sum(1, keepdims=True)
        m = HMM2(mu=mu, sigma=np.sqrt(var), trans=trans, start=start / start.sum())
        history.append(ll)
        if len(history) > 1 and abs(history[-1] - history[-2]) < tol * abs(history[-2]):
            break
    if m.mu[0] > m.mu[1]:
        order = [1, 0]
        m = HMM2(m.mu[order], m.sigma[order], m.trans[np.ix_(order, order)], m.start[order])
    return m, history


def predict_next(x: np.ndarray, m: HMM2) -> np.ndarray:
    """For each position t, the expected value of x[t] given x[:t] only (causal)."""
    x = np.asarray(x, float)
    out = np.empty(len(x))
    belief = m.start.copy()  # state probability for the next element, before it is seen
    for t, v in enumerate(x):
        out[t] = belief @ m.mu
        post = belief * _emission(np.array([v]), m)[0]
        post /= post.sum()
        belief = post @ m.trans
    return out


def fit_ar1(seqs: list[np.ndarray]) -> float:
    """Least-squares phi for x[t] = phi * x[t-1], over all sequences."""
    num = sum(float(np.dot(s[1:], s[:-1])) for s in seqs if len(s) > 1)
    den = sum(float(np.dot(s[:-1], s[:-1])) for s in seqs if len(s) > 1)
    return num / den if den > 0 else 0.0
