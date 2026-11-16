"""Compare results/*.json and site/data/*.json with the committed versions (git HEAD).

Usage: python scripts/compare_results.py [--tol 1e-9]
The "commit" field is not compared. Numbers must agree within the tolerance (relative or absolute).
Exit code 1 if a file is different.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def diff(a, b, tol, path="") -> list[str]:
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            if k == "commit":
                continue
            if k not in a or k not in b:
                out.append(f"{path}/{k}: missing on one side")
            else:
                out += diff(a[k], b[k], tol, f"{path}/{k}")
        return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [f"{path}: length {len(a)} != {len(b)}"]
        return [m for i, (x, y) in enumerate(zip(a, b)) for m in diff(x, y, tol, f"{path}[{i}]")]
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        if math.isclose(a, b, rel_tol=tol, abs_tol=tol) or (math.isnan(a) and math.isnan(b)):
            return []
        return [f"{path}: {a} != {b}"]
    return [] if a == b else [f"{path}: {a!r} != {b!r}"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tol", type=float, default=1e-9)
    args = ap.parse_args()
    bad = 0
    files = sorted([*ROOT.glob("results/*.json"), *ROOT.glob("site/data/*.json")])
    for f in files:
        rel = f.relative_to(ROOT).as_posix()
        old = subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=ROOT, capture_output=True, text=True, check=False)
        if old.returncode != 0:
            print(f"new  {rel}")
            continue
        problems = diff(json.loads(old.stdout), json.loads(f.read_text()), args.tol)
        print(("same " if not problems else "DIFF ") + rel)
        for p in problems[:5]:
            print("     ", p)
        bad += bool(problems)
    print(f"{len(files) - bad} of {len(files)} files are the same")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
