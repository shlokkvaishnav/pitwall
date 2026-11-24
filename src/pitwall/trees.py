"""Evaluate a fitted LightGBM binary classifier with numpy only, from its own model dump.

Used where LightGBM's OpenMP runtime must not run next to torch's (the RL environment), and as the reference for
a browser port. Supports numerical splits with `<=` and default-left/right for missing values.
"""

from __future__ import annotations

import numpy as np
from scipy.special import expit


MEMO_CELLS = 400_000


class TreeEnsemble:
    def __init__(self, dump: dict):
        self.trees = [self._flatten(t["tree_structure"]) for t in dump["tree_info"]]
        nf = int(dump.get("max_feature_idx", max(int(t["feat"].max()) for t in self.trees))) + 1
        self._cuts = [np.unique(np.concatenate([t["thr"][t["feat"] == f] for t in self.trees])) for f in range(nf)]
        self._sizes = np.array([len(c) + 1 for c in self._cuts], np.int64)
        self._radix = np.concatenate([np.cumprod(self._sizes[::-1])[::-1][1:], [1]]).astype(np.int64)
        self._keys = np.zeros(0, np.int64)  # memo of `proba_memo`: sorted cell ids and their raw scores
        self._vals = np.zeros(0)

    @staticmethod
    def _flatten(node: dict) -> dict[str, np.ndarray]:
        feat: list[int] = []
        thr: list[float] = []
        left: list[int] = []
        right: list[int] = []
        value: list[float] = []
        dleft: list[bool] = []

        def add(n: dict) -> int:
            i = len(feat)
            feat.append(-1)
            thr.append(0.0)
            left.append(-1)
            right.append(-1)
            value.append(0.0)
            dleft.append(True)
            if "leaf_value" in n:
                value[i] = n["leaf_value"]
                return i
            if n.get("decision_type", "<=") != "<=":
                raise ValueError("only numerical <= splits are supported")
            feat[i], thr[i], dleft[i] = n["split_feature"], n["threshold"], n.get("default_left", True)
            left[i] = add(n["left_child"])
            right[i] = add(n["right_child"])
            return i

        add(node)
        return {
            k: np.array(v)
            for k, v in zip(("feat", "thr", "left", "right", "value", "dleft"), (feat, thr, left, right, value, dleft))
        }

    def raw(self, x: np.ndarray) -> np.ndarray:
        out = np.zeros(len(x))
        rows = np.arange(len(x))
        for t in self.trees:
            node = np.zeros(len(x), int)
            while True:
                inner = t["feat"][node] >= 0
                if not inner.any():
                    break
                f = np.where(inner, t["feat"][node], 0)
                v = x[rows, f]
                go_left = np.where(np.isnan(v), t["dleft"][node], v <= t["thr"][node])
                node = np.where(inner, np.where(go_left, t["left"][node], t["right"][node]), node)
            out += t["value"][node]
        return out

    def proba(self, x: np.ndarray) -> np.ndarray:
        return expit(self.raw(np.asarray(x, float)))

    def proba_memo(self, x: np.ndarray) -> np.ndarray:
        """Same values as `proba` for inputs without NaN, faster when the same cells come back (a simulation).

        The split thresholds cut the feature space into cells where the model is constant. Each input row is mapped
        to its cell; a cell is evaluated once, at a point inside it (the threshold just above the row's value),
        and then read from a memo of the cells seen so far.
        """
        x = np.asarray(x, float)
        idx = np.column_stack([np.searchsorted(c, x[:, j], side="left") for j, c in enumerate(self._cuts)])
        ids = (idx * self._radix).sum(1)
        u, inv = np.unique(ids, return_inverse=True)
        pos = np.searchsorted(self._keys, u)
        known = np.zeros(len(u), bool)
        ok = pos < len(self._keys)
        known[ok] = self._keys[pos[ok]] == u[ok]
        if not known.all():
            if len(self._keys) > MEMO_CELLS:  # keep each update cheap: start a new memo (values do not change)
                self._keys, self._vals = np.zeros(0, np.int64), np.zeros(0)
                known[:] = False
            first = np.empty(len(u), int)
            first[inv[::-1]] = np.arange(len(ids))[::-1]  # one row of each cell
            i = idx[first[~known]]
            rep = np.column_stack(
                [np.append(c, c[-1] + 1.0 if len(c) else 0.0)[i[:, j]] for j, c in enumerate(self._cuts)]
            )  # a point inside each cell: the threshold just above it, or above the last one
            keys = np.concatenate([self._keys, u[~known]])
            vals = np.concatenate([self._vals, self.raw(rep)])
            o = np.argsort(keys, kind="stable")
            self._keys, self._vals = keys[o], vals[o]
            pos = np.searchsorted(self._keys, u)
        return expit(self._vals[pos][inv])
