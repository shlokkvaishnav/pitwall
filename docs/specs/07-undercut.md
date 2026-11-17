# Spec 07 — When does an undercut work?

Status: We committed this file before the first run. Before this commit, we counted the duels. We did not look at the outcomes.

## 1. Question
An undercut: driver A is directly behind driver B. A pits first. B pits some laps later. Does A come out ahead?
The full race simulator is blocked (specs 05 and 06). This spec tests one strategy decision without the simulator.

We test three claims:
1. Public timing data predicts the result of an undercut better than the base rate.
2. A model from 2022 to 2025 also works on 2026 races.
3. The success rate of the undercut is different in 2026. (The 2026 cars have new tyres and less downforce.)

A negative result is a valid result.

## 2. Duels
From each race (`src/pitwall/undercut.py`):
- A pits at the end of lap L. At the end of lap L − 1, B is directly ahead of A, at most 3.0 s ahead, and B does not pit on lap L − 1 or L.
- B pits at the end of a lap L_B, with L < L_B ≤ L + 5. If B does not pit in these laps, it is not a duel.
- There is no neutralised lap from L − 1 to L_B + 1.
- Outcome: A is ahead of B at the end of lap L_B + 1 (the out-lap of B).

Counts: 2022: 65, 2023: 76, 2024: 87, 2025: 57; 2026 rounds 4 to 12: 29.

## 3. Models
| Name | Content |
|---|---|
| `base_rate` | The success rate in the training duels. |
| `gap_only` | Logistic regression on the gap. |
| `full` | Logistic regression on the gap, the wait (L_B − L), the tyre-age difference (B − A) at lap L, and the race fraction L / race laps. |

Logistic regression: scikit-learn, L2, C = 1.0, standardised inputs, no tuning.

## 4. Rules
| Rule | Pass condition |
|---|---|
| U1 Signal | Leave-one-season-out on 2022 to 2025: the pooled log loss of `full` is lower than `base_rate`. A block bootstrap by race (10,000 samples, seed 0) gives p < 0.05 for the difference. |
| U2 Transfer | On the 29 duels of 2026 rounds 4 to 12, `full` (trained on 2022 to 2025 and the 2026 rounds before the test race) has a lower pooled log loss than `base_rate` (trained on the same duels). Report the bootstrap p-value by race. With 29 duels, this test has low power. |
| U3 2026 change (report) | The success rate in 2026 rounds 1 to 12 minus the rate in 2022 to 2025, with a 95% bootstrap interval by race (2,000 samples, seed 0). |

We also report the Brier score and the coefficients of `full`.

## 5. Output
`results/07-undercut.json`: the duel counts, the scores, the rule results, the coefficients and the git commit SHA.

## Result (2026-11-16, commit addd44b)
U1 and U2 pass. U3 shows no clear change in 2026.

| Model | Log loss, 2022 to 2025 (LOSO, 285 duels) | Log loss, 2026 rounds 4 to 12 (29 duels) |
|---|---|---|
| base_rate | 0.696 | 0.694 |
| gap_only | 0.662 | 0.609 |
| full | **0.615** | **0.558** |

- U1: `full` is better than `base_rate`. The mean difference is −0.080 per duel, p = 0.001 (75 race blocks).
- U2: `full` is also better on 2026: −0.136 per duel. The bootstrap gave p < 0.0001, but it has only 9 race blocks. Thus, this p-value is not precise.
- U3: success rate 45% in 2026 (31 duels) and 49% in 2022 to 2025. The difference is −4 points, with a 95% interval of −22 to +11 points. We cannot say that the undercut is different in 2026.

Coefficients of `full` (2022 to 2025, standardised inputs):
| Input | Coefficient | Meaning |
|---|---|---|
| gap | −0.63 | A larger gap makes the undercut less probable to work. |
| wait (L_B − L) | +0.60 | Each lap that B stays out gives A more time on new tyres. |
| tyre-age difference (B − A) | +0.24 | Older tyres on B help A. |
| race fraction | −0.28 | Late stops work less. |

**Limit.** Jolpica has no tyre compounds. A change of compound can explain a part of the error.
The outcome is the order after the out-lap of B. A can lose the position again later.
The wait (L_B − L) is known only after B reacts. Thus, at the time when A pits, the model gives the probability of success
for each possible wait, not one probability.
