# Spec 17 — Does a transformer beat LightGBM on the next lap time?

Status: registered on 2026-11-22, before the model was trained or run on any data.

## 1. Objective
`gbm_pretrain` (spec 03) predicts the next lap time as "last lap + a LightGBM correction" from per-lap features. A
sequence model can read a driver's whole race so far instead of a few summary features. We test whether it does better.

## 2. Model `seq`
- Input: for each (race, driver), the rows of `pitwall.lapmodel.race_features` in lap order (only usable laps), with
  the 13 `FEATURES` standardised by the training mean and standard deviation.
- A causal transformer: linear embedding to width 64, learned position embedding for up to 100 rows, 3 layers,
  4 heads, feed-forward 128, dropout 0.1. Each row attends only to itself and earlier rows of the same driver and race.
- Output per row: the correction `delta` (s); prediction = `last1` + output, as `gbm_pretrain`.
- Loss: L1 (the same objective as `gbm_pretrain`). AdamW, learning rate 1e-3, weight decay 1e-2, 15 epochs, batch of
  32 sequences, seed 0. Fixed now; not tuned.

## 3. Development comparison (no pass rule)
Walk-forward over 2026 rounds 4 to 12, exactly as spec 03: for round k, both models train on 2022 to 2025 and the 2026
rounds before k. Pooled MAE on the same laps; difference `seq` − `gbm_pretrain` with a block bootstrap by race
(10,000 samples, seed 0). These rounds were used to choose `gbm_pretrain` in spec 03, so this is development only.

## 4. Test (run once, with spec 13)
2026 rounds 19 to 23, after the December dump. Same walk-forward (training on everything before each race, rounds 13 to
18 included as training data, as spec 13 does for `gbm_pretrain`).

| Rule | Pass condition |
|---|---|
| D1 | Pooled MAE of `seq` < `gbm_pretrain` on the test races. |
| D2 | Block bootstrap by race: the 95% interval of (MAE `seq` − MAE `gbm_pretrain`) is below 0. |

If `seq` loses, the README says so.

## 5. Output
`src/pitwall/seqmodel.py` (needs the optional `deep` extra: torch), `scripts/deep_lap_model.py`,
`results/17-deep-lap-dev.json`, later `results/17-deep-lap-test.json`.

## Development result (2026-11-22, commit a5ebf63; 2026 rounds 4 to 12, no rule)
Raw numbers: `results/17-deep-lap-dev.json`. 9,034 laps, walk-forward.

| Model | MAE |
|---|---|
| gbm_pretrain | 1.027 s |
| seq | **0.925 s** |

The transformer is 0.10 s better (95% interval of the difference −0.15 to −0.05 s). It wins on 8 of 9 races; it loses
on rounds 4 and 6. This is a development result; the rules are decided on rounds 19 to 23.
