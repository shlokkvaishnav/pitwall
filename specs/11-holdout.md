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
