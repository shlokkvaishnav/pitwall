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
