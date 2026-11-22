"""Evaluate a fitted LightGBM binary classifier with numpy only, from its own model dump.

Used where LightGBM's OpenMP runtime must not run next to torch's (the RL environment), and as the reference for
a browser port. Supports numerical splits with `<=` and default-left/right for missing values.
"""

from __future__ import annotations

import numpy as np
from scipy.special import expit


class TreeEnsemble:
    def __init__(self, dump: dict):
        self.trees = [self._flatten(t["tree_structure"]) for t in dump["tree_info"]]

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
