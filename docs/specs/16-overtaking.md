# Spec 16 — A learned overtaking model

Status: registered on 2026-11-22, before any pair-lap was built or any model fitted.

## 1. Objective
The race simulator decides passes with one fixed rule: the car behind passes if it is at least `PASS_MARGIN_S` = 0.4 s
faster on that lap, otherwise it stays 0.2 s behind. Real overtaking depends on the circuit, the gap, tyre age and DRS.
We fit the chance that a car passes the car ahead on the next lap from real races, and test it against simpler rules.
Putting it into the simulator is a later spec.

## 2. Pair-laps
From the Jolpica laps (`pitwall.laps.lap_table`). At the end of lap L − 1, take every pair of consecutive cars
(A ahead, B behind) with gap g = cum_B − cum_A ≤ 3.0 s. The outcome is 1 if B is ahead of A at the end of lap L.
A pair-lap is left out if, on lap L − 1 or L, either car has an in-lap or out-lap, lap L is neutral (detector, as the
simulator uses), lap L ≤ 2, either car has no time on lap L, or either car retires on lap L.

## 3. Features (all known at the end of lap L − 1)
- `gap`: g (s), and `drs`: g ≤ 1.0.
- `pace_delta`: A's mean of its last 3 clean laps minus B's (s; positive = B faster).
- `tyre_age_diff`: A's tyre age minus B's (laps).
- `circuit_rate`: the circuit's pass rate in training pair-laps, shrunk to the overall rate with 200 pseudo-pair-laps.
- `race_frac`: L / total laps.

## 4. Models
| Name | Chance that B passes | Role |
|---|---|---|
| `base` | The training pass rate. | Baseline. |
| `sim_rule` | Logistic on `pace_delta − 0.4` alone (the simulator's rule made smooth). | Baseline. |
| `logit` | Logistic on all features. | Comparison. |
| `gbm` | LightGBM on all features (100 trees, depth 4, learning rate 0.05, min 50 per leaf, seed 0). | Candidate. |

## 5. Data and tests
- Training: 2018 to 2025 (all races). Development check: 2026 rounds 1 to 12 (no rule; reported).
- **Test, run once:** 2026 rounds 19 to 23 when the December dump exists (with spec 13), models fitted on 2018 to 2026
  round 12 (rounds 13 to 18 not used; spent holdout).

| Rule | Pass condition (test races) |
|---|---|
| O1 | Log loss of `gbm` < `sim_rule`. |
| O2 | Log loss of `gbm` < `base`. |
| O3 | Block bootstrap by race (10,000 samples, seed 0): 95% interval of (log loss `sim_rule` − `gbm`) above 0. |

## 6. Output
`src/pitwall/overtake.py`, `scripts/overtaking.py` (`--test` for section 5), `results/16-overtaking-dev.json`,
later `results/16-overtaking-test.json`. Results appended below.

## Development check (section 5, 2026-11-22, commit 53c4209)
Training: 79,723 pair-laps from 2018 to 2025, pass rate 5.6%. Scored on 2026 rounds 1 to 12: 4,982 pair-laps,
352 passes. Raw numbers: `results/16-overtaking-dev.json`.

| Model | Log loss |
|---|---|
| base | 0.257 |
| sim_rule (the simulator's rule, smooth) | 0.249 |
| logit | 0.177 |
| **gbm** | **0.154** |

The gap to the car ahead carries most of the signal, then the pace difference; tyre-age difference and the circuit's
pass rate add some. The simulator's pace-only rule is barely better than the base rate. The test (rounds 19 to 23)
runs once after 6 December.
