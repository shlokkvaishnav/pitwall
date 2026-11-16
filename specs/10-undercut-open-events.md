# Spec 10 — Undercut on open events: a direct comparison with published work

Status: We committed this file before the first run. Before this commit, we counted the events. We did not look at the outcomes.

## 1. Objective
An independent preprint (Santillana, arXiv 2607.06495, July 2026) has an undercut model on 2,134 events:
train up to 2023, test 2024 to 2025, logistic regression on the gap, the tyre-age difference and log remaining laps,
a base rate of 25%, and a Brier skill score (BSS) of 0.107. Our duels (specs 07 to 09) need a response of B within 5 laps,
and their base rate is near 50%. Thus, the numbers are not comparable.

This spec uses events without the response condition, and the same split as the preprint.
A negative result is a valid result.

## 2. Events (`open_duels` in `src/pitwall/undercut.py`)
- A pits at the end of lap L. At the end of lap L − 1, B is directly ahead, at most 3.0 s ahead. B does not pit on lap L − 1 or L.
- The outcome lap: one lap after the next stop of B (any wait). If B does not stop again, the last lap that both cars completed.
- Outcome: A is ahead of B at the end of the outcome lap.
- There is no neutralised lap from L − 1 to the outcome lap.

Counts: 2018: 90, 2019: 131, 2020: 95, 2021: 132, 2022: 136, 2023: 165, 2024: 198, 2025: 182; 2026 rounds 1 to 12: 69.
The events with a response within 5 laps are the duels of specs 07 and 09 (the counts are the same).

## 3. Models
Logistic regression: scikit-learn, L2, C = 1.0, standardised inputs, no tuning.
| Name | Inputs (all known when A pits) |
|---|---|
| `base_rate` | none |
| `pitwall_style` | gap, tyre-age difference (B − A), log remaining laps (the inputs of the preprint) |
| `decision` | `pitwall_style` + race fraction + `fresh_a` (spec 08) |
| `two_stage` | A response model: multinomial logistic regression on the inputs of `decision` for the wait class of B (1, 2, 3, 4, 5, 6 to 10, more than 10 laps, no stop). A success model: `decision` + the wait (capped at 11) + a no-stop flag. P(success) = Σ over the classes of P(class) × P(success given the class). For a class with a range, the wait is the mid value (8, 11). |

`fresh_a` comes from the TracingInsights tyre life (spec 08). Events without the tyre life of A are dropped (report the count).

## 4. Split and rules
Train: 2018 to 2023. Test: 2024 and 2025.
| Rule | Pass condition |
|---|---|
| O1 Replication of the preprint (report) | The BSS of `pitwall_style` on the test events, with the base rate. |
| O2 Better than the preprint model | `two_stage` has a lower pooled log loss than `pitwall_style` on the test events. A block bootstrap by race (10,000 samples, seed 0) gives p < 0.05. |
| O3 2026 (report) | The same models, trained on 2018 to 2025, on 2026 rounds 4 to 12. |

## 5. Output
`results/10-undercut-open-events.json`: the counts, the scores, the rule result, the coefficients and the git commit SHA.

## Result (2026-11-16, commit bd5dc3d)
O2 fails. On open events, `two_stage` is not better than the model of the preprint.

Events: 1,198; 1,190 with the tyre life of A. Train 744 (2018 to 2023), test 377 (2024 and 2025). Base rate on the test events: 45.9%.

| Model | Log loss, test 2024 to 2025 | BSS | Log loss, 2026 rounds 4 to 12 (64 events) | BSS |
|---|---|---|---|---|
| base_rate | 0.695 | 0 | 0.667 | 0 |
| pitwall_style | 0.575 | 0.22 | 0.601 | 0.11 |
| decision | 0.573 | 0.22 | 0.601 | 0.11 |
| two_stage | 0.576 | 0.22 | 0.600 | 0.12 |

- O1: the preprint model works on our events, with a BSS of 0.22 (the preprint reports 0.107 on its events).
  Our base rate is 46%, not 25%. Thus, the two event definitions are still different. A position swap in the preprint
  is probably a stricter outcome. We could not read its exact definition.
- O2: `two_stage` against `pitwall_style`: +0.001 per event, p = 0.56. The response model adds no information.
  `decision` (with the race fraction and `fresh_a`) is also equal to `pitwall_style`.
- **A difference from the preprint.** In our fit, the tyre-age difference has a large weight (+0.80, standardised),
  larger than the gap (−0.54). The preprint reports a weak tyre-age weight (+0.01, not standardised, thus not directly comparable).

**Consequence for the project.** The decision-time two-stage method is not a contribution: a simple logistic model
with the gap, the tyre-age difference and the remaining laps is as good. The results that stay:
1. The simple undercut model works in three eras (2018 to 2023 train, 2024 to 2025 test, 2026), with public data only.
2. The duels where B responds within 5 laps (specs 07 to 09) and the open events give the same conclusion.
3. The tyre-age difference is a strong input in our data. This is different from the preprint.
