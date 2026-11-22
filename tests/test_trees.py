import numpy as np
import pytest

lgb = pytest.importorskip("lightgbm")

from pitwall.trees import TreeEnsemble


def test_numpy_trees_equal_lightgbm():
    rng = np.random.default_rng(0)
    x = rng.normal(size=(3000, 6))
    x[rng.random(x.shape) < 0.02] = np.nan
    y = (np.nan_to_num(x[:, 0]) + 0.5 * np.nan_to_num(x[:, 2]) + rng.normal(0, 1, 3000) > 0.8).astype(int)
    m = lgb.LGBMClassifier(n_estimators=100, max_depth=4, learning_rate=0.05, min_child_samples=50, random_state=0,
                           verbose=-1).fit(x, y)  # fmt: skip
    test = rng.normal(size=(500, 6))
    test[rng.random(test.shape) < 0.05] = np.nan
    ours = TreeEnsemble(m.booster_.dump_model()).proba(test)
    theirs = m.predict_proba(test)[:, 1]
    assert np.allclose(ours, theirs, atol=1e-9)
