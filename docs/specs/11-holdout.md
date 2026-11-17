# Spec 11 — Final test on the locked 2026 races

Status: committed before any holdout race was loaded. This is the only run on the holdout.

## 1. Objective
Test the final models, unchanged, on the 2026 races on or after 1 September (the holdout of the charter, section 4).
The pinned Jolpica dump (2026-11-01, SHA-256 in `scripts/fetch_dump.py`) has laps for rounds 13 to 18:
Italy, Spain (Madrid), Azerbaijan, Bahrain (in Malaysia), Singapore, United States. We test on these 6 races.
We keep the pinned dump, so all development results stay as they are. Rounds 19 to 23 are not tested.

## 2. What is fixed
- **Undercut model:** the model on the site. Logistic regression on gap, tyre-age difference and log remaining laps
  (spec 10, `pitwall_style`), trained on all open events of 2018 to 2025 and the 2026 development rounds.
  The coefficients must equal `site/data/undercut-model.json`.
- **Lap-time model:** `gbm_pretrain` and `gbm_2026` of spec 03, same settings. Walk-forward: for holdout race k,
  train on all races before k (2022 to 2025, 2026 rounds 1 to k − 1). This uses only data that was known before race k.
- **Simulator:** version B of spec 06, same walk-forward, 2,000 runs, seed 0.
- **Tyre data:** TracingInsights files for rounds 13 to 18, downloaded only for this spec (`fetch_tyres.py --holdout`).

## 3. Rules
| Rule | Pass condition |
|---|---|
| U1 Undercut skill | Brier skill score > 0 against the training base rate, on the holdout open events. |
| U2 Undercut significance | One-sided block-bootstrap test by race (`dm_block_bootstrap`, 10,000 samples, seed 0) on log loss, model against base rate: p < 0.05. |
| R1 Lap time (charter) | Pooled MAE of `gbm_pretrain` ≤ 0.95 × the best baseline on the same laps, and the block-bootstrap test against that baseline gives p < 0.05. Baselines: `previous_lap`, `linear_stint`, `local_trend` (spec 02). |
| R2 Straights (charter) | Not tested (amendment A1: no car data). |
| R3 Tyre transfer (charter) | `gbm_pretrain` has a lower pooled MAE than `gbm_2026` on the same laps. |
| R4 Simulator (charter) | Mean Spearman of version B > mean Spearman of the grid order, and mean podium Brier of B < the grid baseline. |
| R5 Strategy (charter) | Not tested (amendment A3). |

We also report: the number of events and laps, the per-race numbers, and the undercut calibration table.
Six races is a small sample, and a bootstrap over 6 race blocks is coarse. We report it as it is.

## 4. Procedure
1. A dry run of `scripts/holdout.py --dry-run` on development rounds 7 to 12 (train on the races before them) checks the code.
   It does not count.
2. One run on rounds 13 to 18. Output: `results/11-holdout.json` with the git commit.
3. We keep and report the result, whatever it is. No second run on the holdout.

## Result (2026-11-17, commit 75c2066) — the one holdout run
The undercut model in the run is the model on the site (`same_as_site: true`).

| Rule | Result | Numbers |
|---|---|---|
| U1 Undercut skill | **Fail** | Brier skill −0.09. Log loss 0.690 against 0.658 for the base rate. |
| U2 Undercut significance | **Fail** | p = 0.64 (20 events in 4 races). |
| R1 Lap time | **Pass** | MAE 0.779 s against 0.939 s for `previous_lap` (ratio 0.83), p = 0.0002, 5,354 laps. Better than the baseline in all 6 races. |
| R2 Straights | Not tested | |
| R3 Tyre transfer | **Pass** | `gbm_pretrain` 0.779 s against `gbm_2026` 0.869 s. |
| R4 Simulator | **Fail** | Spearman 0.84 against 0.76 for the grid (better), but podium Brier 0.071 against 0.058 (worse). |
| R5 Strategy | Not tested | |

**Interpretation.**
- **Undercut: no evidence on the holdout, and too little data to say much.** Only 20 open events in the 6 races
  (the development years have about 130 per season). The success rate was 35% against 42% in training, and the model
  was over-confident in the 0.6–0.8 bin (5 events, 1 success). With 20 events, this test cannot tell a useful model
  from a useless one. The earlier evidence (spec 09: 136 events, p = 0.016; spec 10: 2024–2025) stays as it is,
  but the model did not show skill on the newest races.
- **Lap time: the clearest result of the project.** 17% lower error than the best baseline, on races no model saw.
- **Simulator:** it orders the field better than the grid, but its podium probabilities are worse. It stays a fidelity check.
