# Spec 12 — Prediction intervals for the lap-time model

Status: We committed this file before the first run. Development data only.

## 1. Objective
The lap-time model of spec 03 (`gbm_pretrain`, L1 loss) gives one number per lap. We add a range around it:
an interval that should contain the real lap time 80% of the time (and a wider one for 95%).
We test it on development data only. The locked holdout races (2026 races on or after 1 September, spec 11)
are not loaded, not used to fit, not used to calibrate and not used to evaluate. The loaders keep their
default `allow_holdout=False`, so the code stops with `HoldoutError` if a holdout race is asked for.

## 2. Method: split conformal intervals on the residuals
The residual of a lap is the real time minus the forecast. For a set of out-of-sample residuals r₁ … rₙ and a
miscoverage α (0.20 for 80%, 0.05 for 95%), the interval for a new lap with forecast ŷ is

  [ŷ + lo, ŷ + hi],  hi = the ⌈(n + 1)(1 − α/2)⌉-th smallest rᵢ,  lo = −(the ⌈(n + 1)(1 − α/2)⌉-th smallest −rᵢ).

This is the equal-tailed form of split conformal prediction: each tail gets α/2. We use it, not the symmetric
form (± a quantile of |r|), because lap-time residuals are skewed: a lap in traffic can be several seconds slow,
but a lap is rarely much faster than the forecast. If the residuals are exchangeable with the new lap, the coverage
is at least 1 − α. Laps in a season are not exchangeable (cars, tracks and weather change), so we test it.
The model and its settings do not change (spec 03, section 3). There is no tuning on the test races.

Two ways to choose the calibration residuals:
| Name | Calibration residuals for 2026 race k | Role |
|---|---|---|
| `rolling` | The walk-forward residuals of 2026 rounds 1 to k − 1. Each one comes from a model trained on 2022 to 2025 and the 2026 races before that round, as in spec 03. | Primary. It is what a live forecast could use. |
| `static_2025` | The residuals on all 2025 races of one model trained on 2022 to 2024. | Comparison only, no pass rule. Shows what happens if the 2026 cars are ignored. |

Only clean laps are scored, as in spec 03 (no lap 1, no in-laps or out-laps, no neutralised laps).

## 3. Test
Walk-forward over the 2026 development rounds 4 to 12, the same 9 races and laps as spec 03.
For each round k, the forecast is the spec 03 `gbm_pretrain` forecast for round k, and the interval uses the
calibration residuals of section 2. Rounds 1 to 3 are calibration only.

## 4. Rules
| Rule | Pass condition |
|---|---|
| C1 80% coverage | The pooled coverage of the `rolling` 80% interval on rounds 4 to 12 is between 77% and 83%. |
| C2 95% coverage | The pooled coverage of the `rolling` 95% interval on rounds 4 to 12 is between 93% and 97%. |
| C3 Per race | The `rolling` 80% interval covers at least 70% of the laps in at least 7 of the 9 races. |

The spec passes if C1, C2 and C3 pass. We also report, with no rule: the mean interval width, the per-race coverage,
the coverage of `static_2025`, and the coverage by group (car ahead closer than 1 s, tyre age above 20 laps).

## 5. Site replay
The site shows one development race, chosen now: round 12 (Dutch Grand Prix), the last development race.
It shows the three drivers classified first to third, every clean lap they did: the real lap time, the forecast and
the `rolling` 80% interval. The file `site/data/lap-replay.json` has only these model numbers and lap times.

## 6. Output
`results/12-lap-intervals.json`: the calibration offsets for each race, the coverage and width for each race and
interval, the rule results and the git commit SHA. The script is `scripts/lap_intervals.py`.

## Result (2026-11-21, commit 3251764)
C1 and C3 pass. C2 fails by 0.2 points. **The spec fails.**

| Rule | Result | Numbers |
|---|---|---|
| C1 80% coverage | **Pass** | 78.3% of 9,034 laps (pass band 77% to 83%). Mean width 1.54 s. |
| C2 95% coverage | **Fail** | 92.8% (pass band 93% to 97%). Mean width 4.87 s. |
| C3 Per race | **Pass** | The 80% interval covers at least 70% of the laps in 8 of 9 races. Canada (round 5) is the exception: 64.2%. |

The point forecast on these laps is the same as in spec 03 (MAE 1.027 s).

| Calibration | 80% coverage | 95% coverage | Mean width 80% / 95% |
|---|---|---|---|
| `rolling` (2026 rounds before k) | 78.3% | 92.8% | 1.54 s / 4.87 s |
| `static_2025` (no rule) | 71.1% | 88.2% | 1.10 s / 2.81 s |

By group (`rolling`, no rule): car ahead closer than 1 s, 73.2% (80%) and 94.3% (95%), 1,568 laps;
tyre age above 20 laps, 75.9% and 91.7%, 1,990 laps.

**Interpretation.**
- **The 80% interval works on development data.** It is close to its target pooled and in 8 of 9 races.
  It is asymmetric (about −0.7 s to +0.9 s from the forecast), as expected for lap times.
- **The 95% interval is a little too narrow.** The early 2026 races have fewer large errors than the later ones:
  the upper 95% offset grows from +2.2 s (calibrated on rounds 1 to 3) to +3.2 s (rounds 1 to 11).
  We do not change the method to make C2 pass. A new method needs a new spec on new data.
- **The 2026 cars need 2026 calibration.** Residuals from 2025 give intervals that are too narrow (71% for 80%).
- **Laps in traffic are less predictable.** With the car ahead closer than 1 s, the 80% interval covers 73%.
  The interval has one width for all laps; it does not adapt to traffic.
- **The neutral-lap detector misses laps where only part of the field is slow.** In the Dutch race, the leaders did
  the restart lap after the red flag in about 140 s, but the field median stayed under the threshold. That lap then
  counts as the last clean lap, and the next forecast is far off. This is the spec 03 behaviour; the replay on the site shows it.
