# Spec 09 — Undercut replication on 2018 to 2021

Status: We committed this file before the first run. Before this commit, we counted the duels. We did not look at the outcomes.

## 1. Objective
In spec 08, the decision-time model `two_stage` missed rule W1 by a small margin (p = 0.054, the bar is 0.05).
We do not test the same 2022 to 2025 duels again. Instead, we replicate the test on duels that no model has seen:
the seasons 2018 to 2021 (charter amendment A2). A negative result is a valid result.

These seasons had different cars (the aerodynamic rules before 2022). Thus, this is also a transfer test.

## 2. Data
- Duels: the definition of spec 07. Compounds: TracingInsights, as in spec 08.
- 2018 uses absolute compound names (HYPERSOFT and others). They have no hardness, so these duels are dropped (spec 08, section 3).
- Counts (duels with compounds / all duels): 2018: 7 / 27, 2019: 39 / 40, 2020: 32 / 37, 2021: 58 / 60. Total: 136 / 164.
- Lap times are the same in the two sources (difference < 0.01 s) for 99.99% to 100% of laps.

## 3. Models
The models of spec 08 (`base_rate`, `full07`, `full_c`, `direct`, `two_stage`) with the same settings.
Training: all duels of 2022 to 2025 with compounds (260). There is no other fit.

## 4. Rules
| Rule | Pass condition |
|---|---|
| R9-W1 Replication | On the 136 duels of 2018 to 2021, `two_stage` has a lower pooled log loss than `base_rate`. A block bootstrap by race (10,000 samples, seed 0) gives p < 0.05. |
| R9-F (report) | The same comparison for `full_c` (with the wait known), and the Brier skill score of all models. |

## 5. Output
`results/09-undercut-replication.json`: the counts, the scores, the rule result and the git commit SHA.

## Result (2026-11-16, commit fe613f4)
R9-W1 passes. The decision-time model of spec 08 works on 136 duels that no model saw before.

| Model | Known when A pits? | Log loss (136 duels, 2018 to 2021) | Brier skill score |
|---|---|---|---|
| base_rate | yes | 0.694 | 0 |
| full07 | no | 0.606 | 0.17 |
| full_c | no | 0.613 | 0.15 |
| direct | yes | 0.632 | 0.12 |
| two_stage | yes | 0.633 | 0.12 |

- R9-W1: `two_stage` is better than `base_rate` by −0.061 per duel, p = 0.016 (51 race blocks).
- R9-F: `full_c` (with the wait known) is better by −0.082 per duel, p = 0.009.
- The response model is correct for 51% of duels.
- The success rate is 43% in 2018 to 2021, and 50% in the training duels of 2022 to 2025.

**Consequence.** Together with spec 08, the decision-time undercut model works on three periods:
2022 to 2025 (Brier skill 0.09, p = 0.054), 2018 to 2021 (0.12, p = 0.016) and 2026 (0.21, 29 duels).
The compounds still add nothing: `full_c` is a little worse than `full07` on these duels.
