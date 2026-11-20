# Spec 13 — Out-of-sample test on 2026 rounds 19 to 23

Status: registered on 2026-11-21, before the data exists. The run waits for a Jolpica dump that has rounds 19 to 23
(after the last race, 6 December 2026). Only the power analysis of section 5 has been run.

## 1. Objective
Spec 11 tested the final models once on rounds 13 to 18. Rounds 19 to 23 (Mexico City, Brazil, Las Vegas, Qatar,
Abu Dhabi) were not in the pinned dump, so no model or person has seen them. We test the same models on them:
the lap-time model, its intervals (spec 12) and the undercut model. Nothing is tuned or changed before the run.

## 2. Data
- A new Jolpica dump with rounds 19 to 23, pinned by its SHA-256 in `scripts/fetch_dump.py` in the run commit.
- Check before the run: for every race from 2018 to 2026 round 18, the number of laps and pit stops for each race in the new dump
  equals the pinned 2026-11-01 dump. We report every difference. Development and spec 11 results are not recomputed.
- TracingInsights tyre files for rounds 19 to 23 (`fetch_tyres.py --holdout 19 20 21 22 23`).
- The loaders open rounds 19 to 23 with `allow_holdout=True`, in the spec 13 script only.

## 3. What is fixed
- **Lap-time model:** `gbm_pretrain` of spec 03, same settings. Walk-forward: for race k (19 to 23), train on
  2022 to 2025 and every 2026 race before k. This includes rounds 13 to 18. They were already used once as a test
  (spec 11); here they are only training data, which is how the model would be used live.
- **Intervals:** the `rolling` equal-tailed split conformal method of spec 12, unchanged: for race k, the calibration
  residuals are the walk-forward residuals of all 2026 races before k (rounds 1 to k − 1). The 95% interval failed
  C2 on development data (92.8%); we test it unchanged and do not fix it first.
- **Undercut model:** the model on the site, `site/data/undercut-model.json`, unchanged (same as spec 11).
- **Baselines:** `previous_lap`, `linear_stint`, `local_trend` (spec 02); the training base rate for the undercut.

## 4. Rules
| Rule | Pass condition |
|---|---|
| L1 Lap time | As spec 11 R1: pooled MAE of `gbm_pretrain` ≤ 0.95 × the best baseline on the same laps, and the block-bootstrap test by race against it gives p < 0.05 (10,000 samples, seed 0). |
| L2 Transfer | As spec 11 R3: `gbm_pretrain` has a lower pooled MAE than `gbm_2026`. |
| I1 80% coverage | Pooled coverage of the 80% interval is between 77% and 83%. |
| I2 95% coverage | Pooled coverage of the 95% interval is between 93% and 97%. |
| I3 Per race | The 80% interval covers at least 70% of the laps in at least 4 of the 5 races. |
| U1 Undercut skill | As spec 11: Brier skill score > 0 against the training base rate. |
| U2 Undercut significance | As spec 11: one-sided block-bootstrap test by race on log loss, model against base rate, p < 0.05. |

**The undercut rules count only with at least 80 open events** (section 5). Then:
- If rounds 19 to 23 have 80 events or more, U1 and U2 are tested on them.
- If they have fewer (expected: about 17 to 29), U1 and U2 are **not** tested on rounds 19 to 23. We report the
  Brier skill score with a 90% race-block bootstrap interval, labelled descriptive. The confirmatory test waits:
  we add 2027 races in date order, with the same fixed model, and test once, after the first race weekend at which
  the pooled count (rounds 19 to 23 plus 2027) reaches 80. No look before that.
- If the 2027 season ends with fewer than 80 pooled events, we report the descriptive numbers and close the test
  with "not enough events". We do not lower the threshold.

## 5. Power analysis (run on 2026-11-21, development data only)
Script: `scripts/undercut_power.py`. Output: `results/13-undercut-power.json` (commit 48c377e).
We resample whole development races with their real outcomes and out-of-sample model probabilities until we have
n events, then apply U1 and U2 (2,000 simulations; 2,000 bootstrap samples inside each). Power is the share of
simulations where both pass.

| Open events | Power, skill as 2024–25 (BSS 0.22, 377 events) | Power, skill as 2026 rounds 4–12 (BSS 0.11, 64 events) |
|---|---|---|
| 20 | 54% | 43% |
| 40 | 64% | 40% |
| 60 | 76% | 47% |
| **80** | **82%** | 49% |
| 100 | 89% | 57% |
| 120 | 92% | 63% |
| 150 | 96% | 67% |
| 200 | 99% | 76% |
| 250 | more than 99% | 83% |

- **80 events give 80% power** if the model is as good as on 2024 and 2025. This is the threshold of section 4.
- If the model is only as good as on the 2026 development rounds, about 250 events are needed. The 2026 cars
  make fewer undercut attempts: 69 events in 12 development races (5.75 per race), and 20 in the 6 locked races (3.3 per race).
  At that rate, 80 events need about 14 to 24 races, so the pooled test falls in the 2027 season.
- **Small samples make the test too liberal.** With 20 events (3 or 4 races), a model with no information (outcomes
  shuffled) passed 6.1% of the time, above the nominal 5%; with 40 events or more it passed 0.5% or less.
  This is one more reason not to test on fewer than 80 events. The power at 20 events is also inflated by this.
- Spec 11 had 20 events. Even with the 2024–25 skill, that test would have passed only about half the time.

## 6. Procedure
1. Download the new dump; pin its SHA-256; run the check of section 2.
2. Dry run of the spec 13 script on development rounds 7 to 12. It does not count.
3. One run on rounds 19 to 23. Output: `results/13-out-of-sample.json` with the git commit.
4. If needed, the pooled undercut test of section 4, once, in 2027. Output: `results/13-undercut-pooled.json`.
5. We keep and report every result, whatever it is.

## Result
Not run yet.
