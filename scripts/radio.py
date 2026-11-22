"""Spec 19: team radio and pit stops.

Usage:
  PYTHONPATH=src:scripts .venv/bin/python scripts/radio.py --transcribe   # download + transcribe (resumable)
  PYTHONPATH=src:scripts .venv/bin/python scripts/radio.py                # analysis -> results/19-radio.json
Needs faster-whisper for --transcribe. Audio and transcripts stay in data/ (not committed).
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
from flag_laps import API, RAW, get
from sklearn.linear_model import LogisticRegression

from pitwall.dump import Dump
from pitwall.features import build
from pitwall.laps import clean_mask, lap_table
from pitwall.radio import lap_of, tags

ROOT = Path(__file__).resolve().parents[1]
AUDIO = RAW / "radio"
TRANSCRIPTS = ROOT / "data" / "derived" / "radio.csv"
COLS = ["session_key", "season", "round", "driver_number", "acronym", "date", "lap", "file", "text"]
X_LAP = ["tyre_age", "stint", "race_lap_frac", "gap_ahead", "gap_behind"]


def races() -> list[dict]:
    return json.loads((ROOT / "results" / "flag_laps.json").read_text())["races"]


def download(url: str, path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "pitwall-research"})
    with urllib.request.urlopen(req, timeout=60) as r:
        path.write_bytes(r.read())
    time.sleep(0.5)


def transcribe() -> None:
    from faster_whisper import WhisperModel

    model = WhisperModel("small.en", device="cpu", compute_type="int8")
    done = set()
    if TRANSCRIPTS.exists():
        done = set(pd.read_csv(TRANSCRIPTS)["file"])
    TRANSCRIPTS.parent.mkdir(parents=True, exist_ok=True)
    new = not TRANSCRIPTS.exists()
    with TRANSCRIPTS.open("a", newline="") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(COLS)
        for r in races():
            key = r["session_key"]
            clips = get(f"{API}/team_radio?session_key={key}", RAW / f"team_radio_{key}.json")
            laps = get(f"{API}/laps?session_key={key}", RAW / f"laps_{key}.json")
            drivers = get(f"{API}/drivers?session_key={key}", RAW / f"drivers_{key}.json")
            acr = {d["driver_number"]: d["name_acronym"] for d in drivers}
            starts: dict[int, list[tuple[str, int]]] = {}
            for lap in laps:
                if lap.get("date_start"):
                    starts.setdefault(lap["driver_number"], []).append((lap["date_start"], lap["lap_number"]))
            for v in starts.values():
                v.sort()
            for c in clips:
                name = c["recording_url"].rsplit("/", 1)[-1]
                rel = f"{key}/{name}"
                if rel in done:
                    continue
                path = AUDIO / rel
                download(c["recording_url"], path)
                segs, _ = model.transcribe(str(path), beam_size=5, temperature=0.0, language="en")
                text = " ".join(s.text.strip() for s in segs)
                lap = lap_of(c["date"], starts.get(c["driver_number"], []))
                w.writerow([key, r["season"], r["round"], c["driver_number"], acr.get(c["driver_number"], ""), c["date"],
                            lap, rel, text])  # fmt: skip
                fh.flush()
            print(r["season"], r["round"], r["name"], len(clips), "clips", flush=True)


def units(dump: Dump, radio: pd.DataFrame) -> pd.DataFrame:
    """(driver, lap) units of spec 19, section 4, with lap features, radio flags and the outcome."""
    codes = dump.driver_codes  # Jolpica reference -> abbreviation
    out = []
    for r in races():
        t = lap_table(dump.race(r["season"], r["round"]))
        f = build(t)
        f["clean"] = clean_mask(t).to_numpy()
        f["code"] = f["driver"].map(codes)
        last = int(t["lap"].max())
        pit_next = set(zip(t.loc[t["in_lap"], "driver"], t.loc[t["in_lap"], "lap"] - 1))
        rr = radio[(radio["session_key"] == r["session_key"]) & radio["lap"].notna()]
        flags = {k: set() for k in ("box", "tyres")}
        for _, c in rr.iterrows():
            for k in tags(c["text"]) & set(flags):
                for d in range(3):  # a clip on lap l counts for units L = l, l + 1, l + 2
                    flags[k].add((c["acronym"], int(c["lap"]) + d))
        f = f[f["clean"] & f["lap"].between(3, last - 2)].copy()
        f["pit_next"] = [int((d, lap) in pit_next) for d, lap in zip(f["driver"], f["lap"])]
        for k in flags:
            f[f"radio_{k}"] = [float((c, lap) in flags[k]) for c, lap in zip(f["code"], f["lap"])]
        f["season"], f["round"] = r["season"], r["round"]
        out.append(f)
    return pd.concat(out, ignore_index=True)


def log_loss(y, p) -> float:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def analyse() -> None:
    radio = pd.read_csv(TRANSCRIPTS)
    radio["text"] = radio["text"].fillna("")
    dump = Dump(ROOT / "data" / "raw" / "jolpica-dump" / "csv")
    u = units(dump, radio).dropna(subset=X_LAP)
    xr = X_LAP + ["radio_box", "radio_tyres"]
    preds = {"lapdata": np.zeros(len(u)), "lapdata+radio": np.zeros(len(u))}
    for s in sorted(u["season"].unique()):
        tr, te = u["season"] != s, u["season"] == s
        for name, cols in (("lapdata", X_LAP), ("lapdata+radio", xr)):
            m = LogisticRegression(max_iter=2000).fit(u.loc[tr, cols], u.loc[tr, "pit_next"])
            preds[name][te.to_numpy()] = m.predict_proba(u.loc[te, cols])[:, 1]
    y = u["pit_next"].to_numpy()
    race = (u["season"].astype(str) + "-" + u["round"].astype(str)).to_numpy()
    keys = np.unique(race)
    idx = {k: np.flatnonzero(race == k) for k in keys}
    rng = np.random.default_rng(0)
    diffs = []
    for _ in range(10_000):
        pick = np.concatenate([idx[k] for k in rng.choice(keys, len(keys))])
        diffs.append(log_loss(y[pick], preds["lapdata"][pick]) - log_loss(y[pick], preds["lapdata+radio"][pick]))
    ci = [float(np.quantile(diffs, 0.025)), float(np.quantile(diffs, 0.975))]
    ll = {k: log_loss(y, p) for k, p in preds.items()}
    tag_counts = {k: int(sum(k in tags(t) for t in radio["text"])) for k in ("box", "tyres", "pace", "issue")}
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    out = {
        "spec": "19-team-radio",
        "commit": sha,
        "clips": len(radio),
        "clips_with_lap": int(radio["lap"].notna().sum()),
        "tag_counts": tag_counts,
        "units": len(u),
        "pit_next_rate": float(y.mean()),
        "units_with_box_flag": int(u["radio_box"].sum()),
        "units_with_tyres_flag": int(u["radio_tyres"].sum()),
        "pit_rate_given_box_flag": float(u.loc[u["radio_box"] == 1, "pit_next"].mean()),
        "log_loss": ll,
        "rules": {
            "R1_pass": ll["lapdata+radio"] < ll["lapdata"],
            "R2_ci_lapdata_minus_radio": ci,
            "R2_pass": ci[0] > 0,
        },
    }
    (ROOT / "results" / "19-radio.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--transcribe", action="store_true")
    args = ap.parse_args()
    transcribe() if args.transcribe else analyse()


if __name__ == "__main__":
    main()
