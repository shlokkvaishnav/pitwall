# Spec 08 — Undercut, version B: tyre compounds and a decision-time model

Status: We committed this file before the first run. Before this commit, we counted the duels with compounds.
We did not look at the outcomes.

## 1. Objective
Spec 07 has two limits:
1. **No tyre compounds.** Jolpica does not give the compound.
2. **The wait is known only after the event.** The input "wait" (L_B − L) is known only when B pits.
   Thus, the spec 07 model cannot give one probability at the time when A pits.

This spec removes both limits. A negative result is a valid result.

## 2. Tyre data
Source: TracingInsights open data (github.com/TracingInsights/2022 to 2026, MIT and Apache-2.0),
the file `<Grand Prix>/Race/session_laptimes.json`. It has the compound, the tyre life and the stint for each lap.
`scripts/fetch_tyres.py` downloads the race files of 2022 to 2025 and of the 2026 development races.
It does not download holdout races. It writes the SHA-256 of each file.

Data check (done before this spec, on all 104 races):
| Check | Result |
|---|---|
| Jolpica laps with a TracingInsights row (driver code and lap) | 97.9% to 100% for each season |
| The lap time is the same (difference < 0.01 s) | 100% for 2022 to 2025, 99.6% for 2026 |

Compound hardness: SOFT = 1, MEDIUM = 2, HARD = 3. INTERMEDIATE and WET have no hardness.

## 3. Duels
The duels of spec 07. We keep a duel only if both of these have a hardness:
the new tyre of A (lap L + 1) and the tyre of B at lap L. Count: 291 of 316 duels (92%).
We score all models on these 291 duels, also the spec 07 models.

New inputs, all known at the time when A pits:
- `compound_step` = hardness of B at lap L − hardness of the new tyre of A. A positive value: A is on a softer tyre than B.
- `fresh_a` = 1 if the new tyre of A is a new set (life = 1 at lap L + 1), else 0.

## 4. Models
Logistic regression: scikit-learn, L2, C = 1.0, standardised inputs, no tuning.
| Name | Inputs | Known when A pits? |
|---|---|---|
| `base_rate` | none | yes |
| `full07` | gap, wait, tyre-age difference, race fraction (spec 07) | no |
| `full_c` | `full07` + compound_step + fresh_a | no |
| `direct` | gap, tyre-age difference, race fraction, compound_step, fresh_a | yes |
| `two_stage` | A response model: multinomial logistic regression for the wait (1 to 5 laps) on the inputs of `direct`. Then P(success) = Σ_w P(wait = w) × P_full_c(success given w). | yes |

## 5. Rules
| Rule | Pass condition |
|---|---|
| C1 Compounds | Leave-one-season-out (LOSO) on 2022 to 2025: `full_c` has a lower pooled log loss than `full07`. A block bootstrap by race (10,000 samples, seed 0) gives p < 0.05. |
| W1 Decision time | LOSO on 2022 to 2025: `two_stage` has a lower pooled log loss than `base_rate`, with p < 0.05 (same test). |
| W2 (report) | LOSO: `two_stage` against `direct`, and the loss from not knowing the wait (`two_stage` against `full_c`). |
| T1 Transfer | 2026 rounds 4 to 12, walk-forward as in spec 07: `two_stage` has a lower pooled log loss than `base_rate`. Report the p-value (9 race blocks, low power). |

We also report the Brier skill score against `base_rate`, the response model accuracy and the coefficients.

## 6. Output
`results/08-undercut-b.json`: the counts, the scores, the rule results, the coefficients and the git commit SHA.

## Result (2026-11-16, commit e061a29)
C1 fails. W1 fails by a small margin (p = 0.054). T1 passes.

| Model | Known when A pits? | Log loss, LOSO 2022 to 2025 (260 duels) | BSS | Log loss, 2026 rounds 4 to 12 (29 duels) | BSS |
|---|---|---|---|---|---|
| base_rate | yes | 0.696 | 0 | 0.694 | 0 |
| full07 | no | 0.602 | 0.18 | 0.562 | 0.24 |
| full_c | no | 0.600 | 0.18 | 0.544 | 0.26 |
| direct | yes | 0.652 | 0.09 | 0.583 | 0.20 |
| two_stage | yes | 0.652 | 0.09 | 0.581 | 0.21 |

- **C1 fails.** The compounds do not make the spec 07 model better: −0.002 per duel, p = 0.41.
  In the coefficients, `fresh_a` (a new set) has a weight of +0.34, but `compound_step` has only +0.03.
  Thus, a new set of tyres is more important than the compound. Most duels (229 of 291) have a step of −1 or 0.
- **W1 fails by a small margin.** At decision time, `two_stage` is better than `base_rate` by −0.044 per duel, but p = 0.054 (the rule is p < 0.05).
  We do not change the rule after the result.
- **W2.** `two_stage` and `direct` are equal (p = 0.51). The response model is correct for 44% of duels (LOSO).
  The cost of not knowing the wait is +0.052 per duel (`two_stage` against `full_c`). Thus, the wait of B is the largest unknown at decision time.
- **T1 passes.** On 2026, `two_stage` is better than `base_rate`: −0.114 per duel, p = 0.0003 with 9 race blocks (not precise).

**Comparison.** An independent preprint (arXiv 2607.06495) uses 2,134 undercut events, features from pit time only, and reports a Brier skill score of 0.107.
Our decision-time models get 0.09 (LOSO 2022 to 2025) and 0.21 (2026, few duels). The two studies use different duel definitions.

**Status of the two limits of spec 07.**
1. Compounds: fixed in the data (TracingInsights, 92% of duels). The compound adds no information, but a new set does.
2. Wait: fixed in the method (`two_stage` gives one probability at decision time). The signal at decision time is about half of the signal with the wait.
