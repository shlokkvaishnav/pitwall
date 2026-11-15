"""Forecast comparison with a block bootstrap by race (specs/03-lap-model.md, rule S2)."""

from __future__ import annotations

import numpy as np


def dm_block_bootstrap(err_model, err_base, groups, n_boot: int = 10_000, seed: int = 0) -> dict:
    """One-sided Diebold-Mariano test on absolute errors, with a block bootstrap over groups (races).

    H0: the model is not better (mean loss difference d = |e_model| - |e_base| >= 0).
    The p-value is the fraction of bootstrap means of the centred d that are <= the observed mean.
    """
    d = np.abs(np.asarray(err_model, float)) - np.abs(np.asarray(err_base, float))
    groups = np.asarray(groups)
    labels = np.unique(groups)
    sums = np.array([d[groups == g].sum() for g in labels])
    counts = np.array([(groups == g).sum() for g in labels])
    observed = d.mean()
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(labels), size=(n_boot, len(labels)))
    boot = sums[idx].sum(1) / counts[idx].sum(1) - observed  # centred under H0
    p = float((boot <= observed).mean())
    return {"mean_diff": float(observed), "p_value": p, "n": int(d.size), "n_groups": len(labels)}
