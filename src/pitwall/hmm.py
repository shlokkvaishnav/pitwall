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


def _pad(seqs: list[np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    n, t = len(seqs), max(len(x) for x in seqs)
    x = np.zeros((n, t))
    mask = np.zeros((n, t), dtype=bool)
    for i, s in enumerate(seqs):
        x[i, : len(s)] = s
        mask[i, : len(s)] = True
    return x, mask


def _e_step(x: np.ndarray, mask: np.ndarray, m: HMM2):
    """Scaled forward-backward for all padded sequences at once. Padded steps have emission 1."""
    n, t = x.shape
    z = (x[..., None] - m.mu) / m.sigma
    e = np.exp(-0.5 * z**2) / (np.sqrt(2 * np.pi) * m.sigma) + 1e-300
    e = np.where(mask[..., None], e, 1.0)
    alpha = np.zeros((n, t, 2))
    c = np.ones((n, t))
    a = m.start * e[:, 0]
    c[:, 0] = a.sum(1)
    alpha[:, 0] = a / c[:, :1]
    for k in range(1, t):
        a = (alpha[:, k - 1] @ m.trans) * e[:, k]
        a = np.where(mask[:, k : k + 1], a, alpha[:, k - 1])  # padded step: keep the belief
        c[:, k] = np.where(mask[:, k], a.sum(1), 1.0)
        alpha[:, k] = a / c[:, k : k + 1]
    beta = np.ones((n, t, 2))
    xi = np.zeros((2, 2))
    for k in range(t - 2, -1, -1):
        live = mask[:, k + 1]
        b = (e[:, k + 1] * beta[:, k + 1]) @ m.trans.T / c[:, k + 1 : k + 2]
        beta[:, k] = np.where(live[:, None], b, 1.0)
        pair = alpha[:, k, :, None] * m.trans * (e[:, k + 1] * beta[:, k + 1])[:, None, :] / c[:, k + 1, None, None]
        xi += pair[live].sum(0)
    gamma = alpha * beta
    gamma /= gamma.sum(-1, keepdims=True)
    gamma *= mask[..., None]
    return gamma, xi, float(np.log(c[mask]).sum())


def fit(
    seqs: list[np.ndarray], iters: int = 200, tol: float = 1e-6, seed: int = 0, init: HMM2 | None = None
) -> tuple[HMM2, list[float]]:
    """EM over many sequences. States are ordered so that mu[0] <= mu[1]. `init` gives a warm start."""
    seqs = [np.asarray(s, float) for s in seqs if len(s) > 0]
    x, mask = _pad(seqs)
    allx = x[mask]
    if init is None:
        rng = np.random.default_rng(seed)
        q = np.quantile(allx, [0.25, 0.75]) + rng.normal(0, 1e-6, 2)
        m = HMM2(
            mu=q,
            sigma=np.full(2, max(allx.std(), SIGMA_FLOOR)),
            trans=np.array([[0.9, 0.1], [0.1, 0.9]]),
            start=np.array([0.5, 0.5]),
        )
    else:
        m = init
    history: list[float] = []
    for _ in range(iters):
        gamma, xi_sum, ll = _e_step(x, mask, m)
        g_sum = gamma.sum((0, 1))
        mu = np.einsum("ntk,nt->k", gamma, x) / g_sum
        var = np.maximum(np.einsum("ntk,nt->k", gamma, x**2) / g_sum - mu**2, SIGMA_FLOOR**2)
        trans = xi_sum / xi_sum.sum(1, keepdims=True)
        start = gamma[:, 0].sum(0)
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
