# Spec 15 — When does a safety car or VSC come out?

Status: registered on 2026-11-22, before any model was fitted. Development: the 80 races of spec 14 (2023 to 2026
round 12). Test: 2026 rounds 13 to 23. No flag data of the test races has been fetched (spec 14 stopped at round 12).

## 1. Objective
The race simulator (spec 05) draws the number of neutral periods from a Poisson law with the mean of the same circuit
(detector periods), starts each one on a uniformly random lap and makes it 4 laps long. We fit a per-lap hazard model on
the official periods of spec 14 and test whether it predicts when periods start better than that rule. Using it in the
simulator is a later spec; this one only tests the forecast.

## 2. Events
From `pitwall.flags.neutral_laps` (spec 14 definition, with its note). Lap 1's "start" mark is ignored here.
A **period** is a maximal run of consecutive laps that have an SC, VSC or red-flag mark (so an SC that turns into a red
flag is one period). An **event** is the first lap of a period; its kind is the kind on that lap. The at-risk laps are
lap 1 and every lap L ≥ 2 whose previous lap is not in a period; the outcome is 1 if a period starts on L.

## 3. Models
| Name | Per-lap hazard of an event | Role |
|---|---|---|
| `M0 global` | Events / at-risk laps in the training races. | Baseline. |
| `M1 circuit mean` | The simulator rule: mean periods per race at this circuit in training (global mean if none), divided by the laps of the race, the same on every lap. | Baseline (current simulator). |
| `M2 hazard` | Logistic: intercept + lap-1 term + laps 2 to 3 term + circuit effect. Circuit effect: empirical-Bayes shrinkage of the circuit's event rate toward the global rate (beta-binomial, prior strength fitted by maximum marginal likelihood on training). | Candidate. |
Kinds are pooled (any SC, VSC or red-flag start). The share of each kind is reported, not modelled.
Circuits: the Jolpica `circuit_id` of the race.

## 4. Development check (no rule)
Leave-one-season-out over 2023, 2024, 2025, 2026 (rounds 1 to 12): fit on 3 seasons, score the fourth. Report the pooled
per-lap log loss of M0, M1 and M2. If M2 is not better than M1 here, we still run the test as registered and report it.

## 5. Test
- After the last 2026 race (6 December 2026): fetch OpenF1 race control for 2026 rounds 13 to 23 once, with
  `scripts/sc_hazard.py --test` (the only code path that loads them).
- Fit every model on all 80 development races. Score each test race.

| Rule | Pass condition |
|---|---|
| H1 | Pooled per-lap log loss of M2 < M1 on the test races. |
| H2 | Pooled per-lap log loss of M2 < M0 on the test races. |
| H3 | Block bootstrap by race (10,000 samples, seed 0): the 95% interval of (log loss M1 − M2) is above 0. |

Spec 15 passes if H1 and H2 pass. H3 is reported; with about 11 races and perhaps 10 events it will often fail, and that
is a power limit, not evidence against the model. Race-level Brier of "at least one event" is reported for all models.

## 6. Output
`src/pitwall/hazard.py`, `scripts/sc_hazard.py`, `results/15-sc-hazard-dev.json` (section 4) and later
`results/15-sc-hazard-test.json` (section 5). Results appended below.
