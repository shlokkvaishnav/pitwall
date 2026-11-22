import numpy as np
import pandas as pd
import pytest

torch = pytest.importorskip("torch")

from pitwall.features import FEATURES
from pitwall.seqmodel import SeqModel, fit_predict_seq


def _frame(n_drivers=6, laps=30, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for d in range(n_drivers):
        for lap in range(2, laps):
            f = {k: rng.normal() for k in FEATURES}
            f["last1"] = 90.0 + rng.normal()
            rows.append({"season": 2025, "round": 1, "driver": f"d{d}", "lap": lap, **f, "delta": 0.5 * f["tyre_age"]})
    return pd.DataFrame(rows)


def test_causal_mask_hides_later_rows():
    m = SeqModel(dim=16, heads=2, depth=1, dropout=0.0).eval()
    x = torch.randn(1, 10, len(FEATURES))
    pad = torch.zeros(1, 10, dtype=torch.bool)
    a = m(x, pad)
    x2 = x.clone()
    x2[0, 6:] += 5.0  # change only later rows
    b = m(x2, pad)
    assert torch.allclose(a[0, :6], b[0, :6], atol=1e-5)


def test_fit_predict_learns_a_simple_rule_and_keeps_row_order():
    train, test = _frame(seed=0), _frame(seed=1).sample(frac=1.0, random_state=0)
    pred = fit_predict_seq(train, test, "cpu", epochs=30)
    err = np.abs(pred - (test["last1"] + test["delta"]).to_numpy()).mean()
    base = np.abs(test["delta"]).mean()
    assert pred.shape == (len(test),) and err < 0.5 * base
