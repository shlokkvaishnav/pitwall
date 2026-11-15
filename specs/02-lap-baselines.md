# Spec 02 — Next-lap-time baselines

Status: We committed this file before the baseline run.

## 1. Objective
1. Measure the next-lap-time error of each baseline on the 2026 development races.
2. Select the best baseline. This baseline is the bar for rule R1 (spec 00).

## 2. Data
- The 2026 races before 2026-09-01 (rounds 1 to 12), from the Jolpica cache of spec 01.
- A race that failed rule D1 or D2 in `results/01-data-check.json` is not used.

## 3. Laps that we score
A lap is **clean** if all of these are true:
- It is not lap 1.
- It is not an in-lap or an out-lap.
- It is not neutralised. A lap is neutralised if the median lap time of the field is more than 1.15 × the median of all laps of the race.
- It has a lap time.

Each prediction for lap n uses only clean laps of the same driver before lap n, in the same stint.

## 4. Baselines
| Name | Content |
|---|---|
| previous_lap | The last clean lap time in the stint |
| linear_stint | Least-squares line of lap time against tyre age, fitted on the earlier clean laps of the stint (3 laps or more) |
| local_trend | Kalman filter with a local linear trend per stint (pace and wear rate). This is a state-space tyre model without energy. |

## 5. Metrics
- Mean absolute error (MAE) in seconds on clean laps that have a prediction from all three baselines.
  Thus, all baselines use the same laps.
- MAE for each race.

## 6. Rules
| Rule | Condition |
|---|---|
| L1 Bar for R1 | The baseline with the lowest pooled MAE is the bar for rule R1. This is a choice, not a pass/fail rule. |
| L2 Pipeline check | previous_lap has a pooled MAE of less than 2.0 s. The fraction of neutralised laps is between 2% and 30% of all laps. If one fails, the pipeline has a defect, and we stop. |

## 7. Output
`results/02-lap-baselines.json`: the MAE for each baseline and each race, the selected bar, the neutralised fraction, and the git commit SHA.

## Amendment A1 (2026-11-15)
The data comes from the Jolpica CSV dump (spec 01, amendment A2), not from the API cache. The races and the rules do not change.
D3 is not used to exclude races (spec 01, result note).
