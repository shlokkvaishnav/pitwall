# Spec 04 — A hidden energy regime in lap times

Status: We committed this file before the first run.

## 1. Question
In 2026, the battery gives up to 350 kW (Art. C5.2.7), but the car can recover only 8.5 MJ in each lap (Art. C5.2.10),
and the charge window is 4 MJ (Art. C5.2.9). Thus, a driver cannot use full deploy on all laps.
If drivers change between "push" laps and "harvest" laps, the lap times have a hidden regime that the features of spec 03 do not show.

We test two claims:
1. A hidden regime makes the next-lap prediction better.
2. The regime is stronger in 2026 than in 2022 to 2025 (MGU-K 120 kW).

A negative result is a valid result.

## 2. Residuals
- 2026 development races: the residual is lap time minus the `gbm_pretrain` prediction from the walk-forward of spec 03 (rounds 4 to 12).
- 2022 to 2025: the same model and settings, with leave-one-season-out training (train on the other three pre-training seasons).
Clean laps only (spec 02, section 3). A sequence is one stint of one driver, in lap order.

## 3. Models of the residual
| Name | Content |
|---|---|
| `none` | No correction (the `gbm_pretrain` prediction). |
| `ar1` | The next residual is φ × the last residual. φ is fitted by least squares on the training races. |
| `hmm2` | A 2-state Gaussian hidden Markov model. Parameters: two means, two standard deviations, a 2 × 2 transition matrix. We fit it by EM on the training races (seed 0, 200 iterations or less). The correction is the predicted mean of the next residual from the forward filter. |

Training races for each test race: the same as spec 03 (the 2026 development races before the test race).
For the 2022 to 2025 fit (rule E2), we fit `hmm2` on all 92 races.

## 4. Rules
| Rule | Pass condition |
|---|---|
| E1 Better prediction | `hmm2` has a lower pooled MAE than `none` on the 2026 test laps, with a block-bootstrap Diebold-Mariano p < 0.05 (by race, 10,000 samples, seed 0). |
| E2 Not only persistence | `hmm2` has a lower pooled MAE than `ar1` on the same laps, with p < 0.05 (same test). |
| E3 Stronger in 2026 | The state separation `|μ1 − μ0| / pooled σ` of `hmm2` is larger for 2026 (fit on all 12 development races) than for 2022 to 2025. The 95% bootstrap interval of the difference (by race, 2,000 samples, seed 0) does not contain 0. |

The claim "public lap times show an energy regime" needs E1, E2 and E3. If E1 passes and E2 fails, the result is "residual persistence", not an energy regime.

## 5. Output
`results/04-energy-regime.json`: the MAE for each model, the rule results, the fitted HMM parameters for 2026 and for 2022 to 2025, and the git commit SHA.
