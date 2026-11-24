# Spec 21 — Simulator D: the grid as a prior, and randomness set from past races

Status: registered on 2026-11-24, before simulator D was run on any race outcome. The test of section 5 runs once,
on 2026 rounds 19 to 23, when a Jolpica dump with those races exists (after 6 December 2026).

## 1. Question
Simulators B and C order the field about as well as the grid but give worse podium chances (spec 20 development:
podium Brier 0.078 for C against 0.070 for the grid). Their pace input is one number per driver from qualifying and
form, and the lap noise (1.0 s) and the pace shock were never set to match real races. Simulator D keeps the race
model of C and changes only the inputs: it pulls each car's pace towards what its grid slot has meant in past races,
and it sets the lap noise from past laps. Does it beat the grid on podium chances?

## 2. Simulator D
The race model of simulator C (spec 20, section 2: spec 15 `M2` neutral-period hazard, spec 16 `gbm` passing, pit
reaction under a neutral period, retirements), run by the fast simulator (`pitwall.fastsim.simulate`, every car on
its plan, the same distribution as `strategy_env.Race`; `tests/test_fastsim.py`). For race k, only races before k
are used for every fit below.

| Input | Simulator D |
|---|---|
| Grid pace `g(s)` | Race pace (spec 05) against the grid slot `s` (1 = pole; pit-lane and unknown starters take the last slots, as `inputs_from_history`): least squares `pace = a + b log s` on all history driver rows with at least 10 clean laps (2022 to 2025 and 2026 races before k). |
| Pace | `(1 − w) × pace_B + w × g(s)`, with `pace_B` the spec 06 pace (qualifying gap and form). |
| Pace shock | `c × σ_r`, with σ_r of spec 06. |
| Lap noise | Median over history races of a robust SD (1.4826 × MAD) of clean-lap residuals after a straight-line fit of lap time on lap number within each driver's stint (stints with at least 6 clean laps). The start spread stays 2 × lap noise. |
| Hazard, passing | As simulator C: fitted on races before k (spec 20). |

Two settings are chosen on development data: `w` in {0, 0.25, 0.5, 0.75, 1} and `c` in {0.5, 0.75, 1, 1.5, 2}.

## 3. Development (no rule): 2026 rounds 4 to 12
- Each of the 25 settings: 1,000 runs per race, seed 0. Chosen setting: the lowest mean podium Brier.
- Honest development number: leave one round out (choose the setting on the other 8 rounds, score the 9th), mean
  over the 9 rounds.
- The chosen setting at 2,000 runs, seed 0: mean podium Brier and Spearman (tuned on these races, so optimistic).
- Measures as spec 20, section 3, against the grid baseline (podium frequency by grid slot in earlier races) and
  simulator C (spec 20 development file).

## 4. What is fixed for the test
The chosen `w` and `c`, the code at the commit that records the development result, 2,000 runs, seed 0. For race k
in 19 to 23, every fit uses all races before k. This includes rounds 13 to 18 as history, as in spec 13 (only
training data, the way the simulator would be used live); nothing is chosen on them.

## 5. Test, once: 2026 rounds 19 to 23
| Rule | Pass condition (test races) |
|---|---|
| D1 | Mean podium Brier of D < the grid baseline. |
| D2 | Mean podium Brier of D < simulator C (spec 20 code, same races). |
| D3 | Mean Spearman of D ≥ the grid's. |

D1 is the main question. We report each race and the relative Brier difference `1 − Brier_D / Brier_grid`.

## 6. Output
`scripts/race_sim_d.py` (development), `scripts/race_sim_d.py --test` (once, refuses before the data exists),
`results/21-simulator-d-dev.json`, later `results/21-simulator-d-test.json`.
