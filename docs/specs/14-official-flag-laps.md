# Spec 14 — Official flag laps against the lap-time detector

Status: registered on 2026-11-22, before any flag data was fetched for analysis. Development data only.
One race (2023 Australian GP) was opened only to check the message format (section 2); no agreement number was computed on it.

## 1. Objective
Jolpica has no flag data, so `pitwall.laps` marks a lap as neutralised (safety car, virtual safety car or red flag) when the
field median lap time is more than 1.15 times the green median (`NEUTRAL_FACTOR`). The spec 12 result found that this
misses laps where only part of the field is slow. OpenF1 publishes the official race control messages. We measure how
often the detector agrees with them, and we decide by a fixed rule whether later specs should use the official laps.

## 2. Data
- OpenF1 `race_control` for every race (not sprint) session from 2023 to 2026 round 12, the development races that the
  loaders open with `allow_holdout=False`. Holdout races (on or after 2026-09-01) are not fetched.
- Raw JSON saved in `data/raw/openf1/` (not committed). Requests at most 2 per second.
- Format check (2023 Australia): messages have `category` (`SafetyCar`, `Flag`, `SessionStatus`, ...), `flag`,
  `scope`, `message` and `lap_number` (the leader's lap).
- Races are matched to Jolpica by season and date (same calendar day, UTC). A race that OpenF1 does not have, or that
  cannot be matched, is listed and left out.

## 3. Official neutral laps
A lap number L (leader lap) is officially neutral if any of these holds:
- **Safety car:** from the lap of `SAFETY CAR DEPLOYED` to the lap of the next `SAFETY CAR IN THIS LAP`, inclusive.
- **Virtual safety car:** from `VIRTUAL SAFETY CAR DEPLOYED` to the next `VIRTUAL SAFETY CAR ENDING`, inclusive.
- **Red flag:** from the lap of a track `RED` flag to the lap of the next `SESSION STARTED`, inclusive.
- Lap 1 is neutral, as in the detector (standing start).
A period with no closing message runs to the last lap. Sector yellow flags are not neutralisations; we count them but do
not use them.

## 4. Measures (per lap number of each race, pooled over races)
- Recall of the detector: official neutral laps that the detector also marks, divided by official neutral laps.
- Precision of the detector: detector laps that are officially neutral, divided by detector laps.
- Both split by kind (SC, VSC, red flag), lap 1 excluded from both (it is neutral in both by rule).
- Number of clean laps (`clean_mask`) that change status, and their effect on the spec 12 `rolling` 80% and 95%
  coverage of 2026 rounds 1 to 12 when officially neutral laps are also removed. This last item is exploratory: those
  races were already used to develop spec 12, so it is not a test.
- Interval for recall and precision: bootstrap over races (10,000 samples, seed 0), 95%.

## 5. Decision rule
- If the detector's pooled recall or precision is below 0.90, later specs use the official laps where OpenF1 has them
  (2023 on) and the detector before 2023 (`neutral_source="official"`).
- Otherwise the detector stays, because it works for every season.
- Either way, **spec 13 runs unchanged** with the detector, as registered. The new source is an option with the detector
  as its default, so the code path of spec 13 does not change.

## 6. Output
- `scripts/flag_laps.py` (fetch + measure), `results/flag_laps.json` (with the git commit).
- `src/pitwall/flags.py`: parse messages to official neutral laps; unit tests on hand-written message lists.
- Outcome appended below, with the decision.
