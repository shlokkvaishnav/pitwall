# Spec 19 — Does team radio tell you a pit stop is coming?

Status: registered on 2026-11-22, before any radio clip was downloaded or transcribed.

## 1. Objective
Teams talk to drivers before a stop ("box, box", "tyres are gone"). OpenF1 publishes a selection of race radio clips
(not all of them). We transcribe them, tag each clip's topic, and test whether a recent radio mention of tyres or a
stop improves a pit-next-lap model built from lap data only.

## 2. Data
- The 80 development races of spec 14 (2023 to 2026 round 12). OpenF1 `team_radio` (clip time, driver, mp3 URL) and
  `laps` (lap start time per driver). Audio cached in `data/raw/openf1/radio/` (not committed). Requests at most 2 per
  second. A clip belongs to the driver's lap whose start time is the last one before the clip.
- Transcription: faster-whisper, model `small.en`, CPU, beam size 5, temperature 0, no prompt. Transcripts are kept in
  `data/derived/radio.csv` (not committed).

## 3. Topics
Each clip gets zero or more tags from fixed keyword rules (case-insensitive, whole words), written now:
- `box`: box, boxing, pit this lap, pit now, stay out, plan a, plan b, plan c, extend.
- `tyres`: tyre, tyres, tire, tires, grip, deg, degradation, graining, blistering, rears, fronts, softs, mediums, hards.
- `pace`: push, pace, gap, delta, faster, slower, lift and coast, manage.
- `issue`: problem, issue, damage, broken, lost power, engine, gearbox, brakes, puncture.
**Check:** 100 clips drawn at random (seed 0) are tagged by hand, blind to the rules, by the assistant that wrote this
spec (not by the owner). Agreement per tag is reported. The hand tags are not used for anything else.

## 4. Test
Unit: (driver, lap L) for every clean racing lap of `pitwall.laps.lap_table`, laps 3 to the last but two. Outcome: the
driver pits at the end of lap L + 1 (`in_lap` on L + 1).
- `lapdata`: logistic regression on tyre age, stint, race fraction, gap ahead and behind (from `pitwall.features`).
- `lapdata+radio`: the same plus two flags: a `box` clip and a `tyres` clip for this driver in laps L − 2 to L.
Evaluation: leave-one-season-out over 2023, 2024, 2025, 2026 (to round 12); pooled log loss.

| Rule | Pass condition |
|---|---|
| R1 | Pooled log loss of `lapdata+radio` < `lapdata`. |
| R2 | Block bootstrap by race (10,000 samples, seed 0): 95% interval of (log loss `lapdata` − `lapdata+radio`) above 0. |

This is development data with no separate test; a pass is exploratory evidence, stated as such. OpenF1 picks which clips
to publish, after the race, so a clip's presence can itself carry information that a team would not have.
The site shows no quotes, only per-lap topic counts.

## 5. Output
`src/pitwall/radio.py` (download, lap matching, tags), `scripts/radio.py`, `results/19-radio.json`.
