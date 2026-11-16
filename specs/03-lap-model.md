# Spec 03 — Next-lap-time model, version A

Status: We committed this file before the first run.

## 1. Objective
Make the first model that predicts the next lap time better than the bar of spec 02 (`previous_lap`, MAE 1.05 s).
We test it with development data only. The final test (rule R1) uses the holdout later.

## 2. Features
For each clean lap n of a driver, the features use only laps before lap n (causal):
- the last three clean lap times of the stint, and their mean;
- tyre age, stint number, and race-lap fraction (a fuel proxy);
- the gap to the car ahead and to the car behind at the end of lap n − 1, from the cumulative race times;
- flags: gap to the car ahead < 1.0 s (Overtake mode can be active), gap < 2.0 s;
- the number of laps since the last neutralised lap;
- the field median of clean lap times on lap n − 1 (track evolution and conditions).

The target is the change: lap time n minus the last clean lap time. Thus, the model learns a correction to `previous_lap`.

## 3. Candidates
| Name | Model | Training data |
|---|---|---|
| `gbm_pretrain` | LightGBM, L1 loss | 2022 to 2025 races, plus the 2026 development races before the test race |
| `gbm_2026` | LightGBM, L1 loss, same settings | Only the 2026 development races before the test race |

Settings (fixed now): 400 trees, learning rate 0.03, 31 leaves, minimum 50 rows in a leaf, feature fraction 0.8, seed 0.
There is no tuning on the test races.

## 4. Test
Walk-forward over the 2026 development races: for test race k (rounds 4 to 12), train on all allowed races before round k.
We score all candidates and `previous_lap` on the same laps: clean laps with a prediction from all of them.

## 5. Rules (development data, a preview of R1 and R3)
| Rule | Pass condition |
|---|---|
| S1 Error | The pooled MAE of the best candidate is at most 0.95 × the MAE of `previous_lap` on the same laps. |
| S2 Significance | A one-sided Diebold-Mariano test on absolute errors (best candidate against `previous_lap`) gives p < 0.05. We use a block bootstrap by race (10,000 samples, seed 0) for the p-value, because laps in one race are not independent. |
| S3 Transfer | `gbm_pretrain` has a lower pooled MAE than `gbm_2026`. |

## 6. Output
`results/03-lap-model.json`: the MAE for each candidate and race, the rule results, the feature importance, and the git commit SHA.

## Result (2026-11-16, commit 11b962c)
S1, S2 and S3 pass.

| Model | Pooled MAE (9,034 laps, rounds 4 to 12) |
|---|---|
| previous_lap | 1.161 s |
| gbm_pretrain | 1.027 s |
| gbm_2026 | 1.748 s |

- S1: the ratio is 0.885 (the pass condition is 0.95 or less).
- S2: the mean difference is −0.133 s. No bootstrap sample of the 9 race blocks gave a difference of 0 or more (p < 0.0001).
- S3: `gbm_pretrain` is better than `gbm_2026`. The 2022 to 2025 data helps, although the 2026 cars are different.
