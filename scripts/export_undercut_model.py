"""Export the undercut model of spec 10 (`pitwall_style`) for the in-browser tool on the site.

Usage: PYTHONPATH=src .venv/bin/python scripts/export_undercut_model.py
Writes site/data/undercut-model.json: the coefficients, the scaler, the test scores, a calibration table,
and test vectors (inputs and Python probabilities) that tests/js/undercut.test.mjs checks.
No raw data is in the file.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import undercut_open as uo

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "site" / "data" / "undercut-model.json"


def params(model) -> dict:
    scaler, lr = model[0], model[-1]
    return {
        "mean": scaler.mean_.round(6).tolist(),
        "scale": scaler.scale_.round(6).tolist(),
        "coef": lr.coef_[0].round(6).tolist(),
        "intercept": round(float(lr.intercept_[0]), 6),
    }


def main() -> None:
    d = uo.load(range(2018, 2027)).dropna(subset=["life_a_new"]).reset_index(drop=True)
    y = d["a_ahead"].astype(int)

    # calibration on the spec 10 test seasons, with the spec 10 training seasons
    train, test = d[d["season"] <= 2023], d[d["season"].isin([2024, 2025])]
    m_test = uo.logistic().fit(train[uo.PITWALL], train["a_ahead"].astype(int))
    p = m_test.predict_proba(test[uo.PITWALL])[:, 1]
    yt = test["a_ahead"].astype(int).to_numpy()
    edges = np.linspace(0, 1, 6)
    bins = np.clip(np.digitize(p, edges[1:-1]), 0, 4)
    calib = [
        {"lo": float(edges[b]), "hi": float(edges[b + 1]), "n": int((bins == b).sum()),
         "mean_p": float(p[bins == b].mean()) if (bins == b).any() else None,
         "freq": float(yt[bins == b].mean()) if (bins == b).any() else None}
        for b in range(5)
    ]  # fmt: skip
    brier = float(((p - yt) ** 2).mean())
    base = float(((train["a_ahead"].mean() - yt) ** 2).mean())

    # the deployed model: all events that are not in the holdout (2018 to 2026 development rounds)
    final = uo.logistic().fit(d[uo.PITWALL], y)
    rng = np.random.default_rng(0)
    vectors = []
    for _ in range(25):
        gap = float(rng.uniform(0.05, 3.0))
        age_a, age_b = int(rng.integers(1, 40)), int(rng.integers(1, 40))
        left = int(rng.integers(3, 60))
        x = [[gap, age_b - age_a, float(np.log(left))]]
        prob = float(final.predict_proba(np.array(x))[:, 1][0])
        vectors.append({"gap_s": gap, "age_a": age_a, "age_b": age_b, "laps_left": left, "p": prob})

    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True)
    out = {
        "model": "logistic regression on the gap, the tyre-age difference (B - A) and log remaining laps (spec 10)",
        "features": uo.PITWALL,
        "params": params(final),
        "trained_on": {"events": len(d), "seasons": "2018 to 2026 (development rounds only)"},
        "test": {"train": "2018 to 2023", "test": "2024 and 2025", "events": len(test), "brier": brier,
                 "brier_base_rate": base, "bss": 1 - brier / base, "calibration": calib},
        "test_vectors": vectors,
        "commit": sha.stdout.strip(),
    }  # fmt: skip
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2))
    print(json.dumps({k: out[k] for k in ("params", "trained_on", "test")}, indent=2))


if __name__ == "__main__":
    main()
