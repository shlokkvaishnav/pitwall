# Spec 06 — Race simulator, version B

Status: We committed this file before the first run.

## 1. Objective
Version A (spec 05) was worse than the grid, and it was over-confident. Spec 05 gives three possible causes:
1. The driver pace came from few races, and it was noisy.
2. The simulator had no uncertainty in the pace of a driver for the full race. Only the lap noise was random, and it cancels over many laps.
3. The simulator had no qualifying information. The grid only gives the order.

Version B changes the pace input and adds race-level pace uncertainty. All other parts of version A stay the same.
We test only one version B. The two ablations in section 4 are for the report only. They do not change the rules.

## 2. Changes to the inputs (for test race k)
| Input | Version B |
|---|---|
| Qualifying gap `q` | The best lap of the driver in all qualifying sessions of race k (Q1, Q2, Q3), minus the median of these best laps in the field, in seconds. A driver without a time gets the slowest time in the field. We clip `q` to −5 s … +5 s. |
| Form `f` | The mean race pace of the driver (spec 05, section 2) over the races of the same season before the race. 0 if no race. |
| Pace | `pace = β_q × q + β_f × f`. We fit β_q and β_f by least squares without intercept on all history races (pretrain seasons and 2026 races before k). The target is the race pace of the driver in that race. Drivers with fewer than 10 clean laps are not used for the fit. |
| Pace shock σ_r | The standard deviation of the residuals of the same fit. |

## 3. Change to the simulation
In each run, each driver gets one pace shock ε ~ N(0, σ_r) for the full race. The lap time is
`pace + ε + wear × tyre age + lap noise`. The lap noise stays 1.0 s.

## 4. Rules (development rounds 4 to 12, as spec 05)
| Rule | Pass condition |
|---|---|
| S1 Order | The mean Spearman correlation of version B with the official classification is higher than for the grid order. |
| S2 Podium | The mean podium Brier score of version B is lower than for the grid baseline of spec 05. |
| S3 Calibration (report only) | Reliability of the podium probabilities in 5 bins. |
| Ablations (report only) | (a) qualifying pace without the pace shock, (b) version A pace with the pace shock. |

If S1 and S2 pass, we can run the R4 holdout test of spec 00 with version B. If one rule fails, stage 3 stays blocked.

## 5. Output
`results/06-race-simulator-b.json`: β_q, β_f, σ_r and the scores for each race, the rule results, the ablations, and the git commit SHA.
