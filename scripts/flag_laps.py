"""Spec 14: official flag laps (OpenF1 race control) against the lap-time neutral detector.

Usage: PYTHONPATH=src .venv/bin/python scripts/flag_laps.py
Fetches OpenF1 race control for 2023 to 2026 round 12 into data/raw/openf1/ (cached), writes results/flag_laps.json.
No holdout race is fetched or loaded.
"""

from __future__ import annotations

import json
import subprocess
import time
import urllib.request
from datetime import date
from pathlib import Path

import numpy as np

from pitwall.dump import Dump
from pitwall.flags import KINDS, neutral_laps, sector_yellows
from pitwall.laps import lap_table
from pitwall.splits import split_of

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "openf1"
API = "https://api.openf1.org/v1"
SEASONS = (2023, 2024, 2025, 2026)
LAST_2026_ROUND = 12
_last_request = 0.0


def get(url: str, cache: Path):
    global _last_request
    if cache.exists():
        return json.loads(cache.read_text())
    wait = 0.5 - (time.monotonic() - _last_request)  # at most 2 requests per second (spec 14, section 2)
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(url, headers={"User-Agent": "pitwall-research"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read())
            break
        except Exception:
            if attempt == 3:
                raise
            time.sleep(5 * (attempt + 1))
    _last_request = time.monotonic()
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(data))
    return data


def ratio(a: int, b: int) -> float | None:
    return a / b if b else None


def counts(races: list[dict]) -> dict:
    tp = sum(r["tp"] for r in races)
    det = sum(r["detector_laps"] for r in races)
    off = sum(r["official_laps"] for r in races)
    return {"tp": tp, "detector_laps": det, "official_laps": off, "recall": ratio(tp, off), "precision": ratio(tp, det)}


def bootstrap(races: list[dict], n: int = 10_000, seed: int = 0) -> dict:
    rng = np.random.default_rng(seed)
    tp = np.array([r["tp"] for r in races], float)
    det = np.array([r["detector_laps"] for r in races], float)
    off = np.array([r["official_laps"] for r in races], float)
    idx = rng.integers(0, len(races), size=(n, len(races)))
    rec = tp[idx].sum(1) / off[idx].sum(1)
    prec = tp[idx].sum(1) / det[idx].sum(1)
    q = lambda x: [float(np.nanquantile(x, 0.025)), float(np.nanquantile(x, 0.975))]
    return {"recall_95ci": q(rec), "precision_95ci": q(prec)}


def main() -> None:
    dump = Dump(ROOT / "data" / "raw" / "jolpica-dump" / "csv")
    races, unmatched = [], []
    for season in SEASONS:
        sessions = get(f"{API}/sessions?year={season}&session_name=Race", RAW / f"sessions_{season}.json")
        by_day: dict[date, list[dict]] = {}
        for s in sessions:
            if s.get("session_type") == "Race" and not s.get("is_cancelled"):
                by_day.setdefault(date.fromisoformat(s["date_start"][:10]), []).append(s)
        for _, row in dump.schedule(season).iterrows():
            rnd, day = int(row["round"]), row["date"]
            if split_of(day) == "holdout" or (season == 2026 and rnd > LAST_2026_ROUND):
                continue
            match = by_day.get(day, [])
            if len(match) != 1:
                unmatched.append(
                    {"season": season, "round": rnd, "name": row["name"], "date": str(day), "openf1": len(match)}
                )
                continue
            key = match[0]["session_key"]
            msgs = get(f"{API}/race_control?session_key={key}", RAW / f"race_control_{key}.json")
            laps = lap_table(dump.race(season, rnd))
            last = int(laps["lap"].max())
            det = {int(x) for x in laps.loc[laps["neutral"], "lap"].unique()} - {1}
            off_map = neutral_laps(msgs, last)
            off = set(off_map) - {1}
            clean = ~laps["neutral"] & ~laps["in_lap"] & ~laps["out_lap"] & laps["time_s"].notna()
            rec = {
                "season": season,
                "round": rnd,
                "name": row["name"],
                "session_key": key,
                "laps": last,
                "detector_laps": len(det),
                "official_laps": len(off),
                "tp": len(det & off),
                "missed": sorted(off - det),
                "extra": sorted(det - off),
                "clean_laps_now_neutral": int((clean & laps["lap"].isin(off)).sum()),
                "sector_yellows": sector_yellows(msgs),
            }
            for k in KINDS:
                lk = {lap for lap, kinds in off_map.items() if k in kinds} - {1}
                rec[f"{k}_laps"], rec[f"{k}_detected"] = len(lk), len(lk & det)
            races.append(rec)
            print(
                season, rnd, row["name"], f"official {len(off)} detector {len(det)} both {len(det & off)}", flush=True
            )

    by_kind = {
        k: {
            "laps": sum(r[f"{k}_laps"] for r in races),
            "recall": ratio(sum(r[f"{k}_detected"] for r in races), sum(r[f"{k}_laps"] for r in races)),
        }
        for k in KINDS
    }
    pooled = {**counts(races), **bootstrap(races)}
    use_official = bool((pooled["recall"] or 0) < 0.90 or (pooled["precision"] or 0) < 0.90)
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True)
    out = {
        "spec": "14-official-flag-laps",
        "commit": sha.stdout.strip(),
        "races_scored": len(races),
        "unmatched": unmatched,
        "pooled": pooled,
        "by_kind": by_kind,
        "clean_laps_now_neutral": sum(r["clean_laps_now_neutral"] for r in races),
        "decision": {"use_official": use_official, "rule": "official if detector recall or precision < 0.90"},
        "races": races,
    }
    (ROOT / "results" / "flag_laps.json").write_text(json.dumps(out, indent=2))
    print(
        json.dumps(
            {k: out[k] for k in ("races_scored", "pooled", "by_kind", "clean_laps_now_neutral", "decision")}, indent=2
        )
    )
    print("unmatched:", unmatched)


if __name__ == "__main__":
    main()
