# Spec 23 — Tyre wear per compound in the strategy engine

Status: registered on 2026-11-24, before the tyre model was fitted and before the new engine was run on any race.

## 1. Question
In spec 22 the engine's pit window held 29% of the top 5 finishers' real stops (2023 to 2025), below a fixed-lap rule
(37%). The simulator had one wear rate for every compound, so it cannot see why a team runs a long stint on hard tyres
or a short one on softs. With a wear rate and a pace offset per compound, does the window hold more real stops, and
does it beat the simple rules?

**Honesty note.** The same 2023 to 2025 stops were already scored once (spec 22), and that result led to this change.
Section 5 is a second look at development data, not a clean test. Section 6 registers the clean test.

## 2. Tyre model (`pitwall.tyrewear`), fitted once
- Races: 2019 to 2022 only (2018 is left out: its files use absolute names such as ULTRASOFT, not SOFT, MEDIUM and
  HARD for each race). No race from 2023 on is used.
- Each race: clean laps (as `laps.clean_mask`) with a dry compound and a tyre life from TracingInsights; least squares
  with driver effects: lap time = driver + offset(compound) + wear(compound) × tyre life + fuel × lap. A compound
  counts in a race with at least 30 such laps; the race counts with at least 2 compounds and 5 drivers.
- Pooling: for each compound, the median over races of wear (at least 0) and of the offset against MEDIUM (races
  that ran MEDIUM). Per circuit: the median over that circuit's races if it has at least 2 fitted races, else all races.
- Output: `scripts/tyre_model.py`, `results/23-tyre-model.json`.

## 3. Engine with compounds
Everything as spec 22, section 2 (world, cars, decision lap t0, candidate laps, extra stops, window ± 3, 5-lap
smoothing), except:
- Lap time in the simulator: pace + offset(compound) + wear(compound) × tyre life (in place of the single wear rate).
  The circuit's rates of section 2.
- State at t0: each car's real compound and tyre life at the end of t0 (TracingInsights; life from the Jolpica stint
  count if missing; MEDIUM if the compound is missing or not dry).
- Other cars fit the next compound by a fixed rule: SOFT → MEDIUM, MEDIUM → HARD, HARD → MEDIUM.
- The car's next stop is a pair (lap, compound), compound in {SOFT, MEDIUM, HARD}. If the car has run only one dry
  compound and no extra stop follows, its current compound is not allowed (the two-compound rule). Extra stops after
  it follow the rule of the other cars. 20 runs per pair, one batch, seed = race index. The best pair is the lowest
  smoothed mean finishing position (smoothing over laps, per compound); the window is its lap ± 3.

## 4. Baselines and measures
As spec 22, sections 3 and 4: B1 tyre-age rule and B2 fixed-lap rule (unchanged), containment rate, 95% race-block
bootstrap intervals (10,000 samples, seed 0), paired differences, median absolute error, stops not on a neutral lap.
Also the paired difference against the spec 22 engine on the same decisions (`results/22-decision-check.json`).

## 5. Development re-run: 2023 to 2025 (report only)
E2 = the 95% interval of (new engine − best baseline) is above 0. Reported either way.

## 6. Test, once: 2026 rounds 19 to 23
The same engine, tyre model and settings (fixed at the commit that records section 5), on the top 5 finishers of
rounds 19 to 23, when the dump and tyre files for those races exist (after 6 December 2026). Rule T1: the engine's
containment rate is higher than both B1's and B2's on the same decisions. With about 40 decisions this is a weak test;
we report the rates with their intervals. Output: `results/23-decision-check-test.json`.

## 7. Output
`scripts/tyre_model.py`, `scripts/decision_check.py --tyres` (`results/23-decision-check-tyres.json`).

## Note (2026-11-24, before the full run)
Tyre model fitted (`results/23-tyre-model.json`, 77 races, commit b1e1812): median wear 0.025 (SOFT), 0.026
(MEDIUM), 0.036 (HARD) s per lap of life; offsets +0.27 (SOFT) and −0.08 (HARD) s against MEDIUM. The race-level
estimates vary widely (SOFT wear: quartiles −0.04 to 0.09), and the soft offset has the wrong sign for fresh tyres,
which points to confounding (soft stints run early, in traffic, and are often managed). We use the model as
registered. A plumbing run of the script on one race (2023 Australia, 15 decisions, not kept) checked that it runs;
nothing was changed after it.
