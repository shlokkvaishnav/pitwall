# Method and results

This page is the one place to read how pitwall was tested. The detailed plans live in [`docs/specs/`](specs/).

## How the work was done
- **A written plan before every experiment.** Each spec lists the data, the models and pass/fail rules with numbers.
  It was committed before the first run. Changes after that are dated amendments.
- **A locked final test.** The 2026 races from 1 September could not be loaded by the code (`pitwall.splits`)
  until the final spec. They were used once, at the end ([spec 11](specs/11-holdout.md)).
- **Failures stay in.** A failed rule is reported as a failure, and the next step is a new spec, not a quiet retry.
- **Every number has a source.** Each result is a JSON file in `results/` with the git commit that made it.
  `make reproduce` rebuilds all of them from the public data and compares them with the committed files.

## Data
- [Jolpica-F1](https://github.com/jolpica/jolpica-f1) database dump of 2026-11-01 (pinned SHA-256): laps, positions, pit stops, grid, results.
- [TracingInsights](https://github.com/TracingInsights) per-lap tyre compound and tyre life, 2018 to 2026.
- No car telemetry. F1 live timing needs a paid account, so everything is built from lap-level data.

## All experiments
| Spec | Question | Result |
|---|---|---|
| [00](specs/00-charter.md) | Charter: goals, splits, final rules | — |
| [01](specs/01-energy-limits-and-data.md) | Is the lap data complete enough? | Yes for laps and pit stops. Finishing order from laps matches the result 84% of the time (rule failed; known timing gaps). |
| [02](specs/02-lap-baselines.md) | How good are simple lap-time forecasts? | "Next lap = last lap" is the best: 1.05 s mean error. |
| [03](specs/03-lap-model.md) | Can LightGBM beat it? | **Yes.** 1.027 s vs 1.161 s on 2026 rounds 4 to 12 (p < 0.0001). Pre-training on 2022 to 2025 helps. |
| [04](specs/04-energy-regime.md) | Do lap times show a hidden battery-use state? | **No.** A 2-state HMM finds an outlier state (traffic, incidents), not an energy regime. Code archived (tag `energy-experiment`). |
| [05](specs/05-race-simulator.md) | Does a Monte Carlo simulator beat the grid order? | **No.** Spearman 0.724 vs 0.785. |
| [06](specs/06-race-simulator-b.md) | Version B with qualifying pace and pace noise | **No.** Spearman 0.744 vs 0.785. |
| [07](specs/07-undercut.md) | When does an undercut work? | Gap, tyre-age difference and race phase predict it (log loss 0.615 vs 0.696, p = 0.001). |
| [08](specs/08-undercut-b.md) | Do tyre compounds and a decision-time model help? | Compounds: no. Decision-time model: just short of the bar (p = 0.054). |
| [09](specs/09-undercut-replication.md) | Does the decision-time model hold on 2018 to 2021? | **Yes.** 136 unseen duels, p = 0.016. |
| [10](specs/10-undercut-open-events.md) | Is it better than a published model ([arXiv 2607.06495](https://arxiv.org/abs/2607.06495))? | **No.** Equal to the simpler published-style model (Brier skill 0.22 on 2024 and 2025). The site uses the simpler model. |
| [11](specs/11-holdout.md) | Final test on 6 locked 2026 races | Lap-time model **passes** (0.779 s vs 0.939 s, better in all 6 races). Undercut model **fails** (20 events, no skill). Simulator **fails**. |
| [12](specs/12-lap-intervals.md) | Do conformal ranges around the lap-time forecast hold their coverage? (development rounds 4 to 12) | 80% range: 78.3% of 9,034 laps (pass). 95% range: 92.8% (**fails**, the band was 93% to 97%). Ranges calibrated on 2025 are too narrow (71.1% for 80%). |
| [13](specs/13-out-of-sample-rounds.md) | Registered test on 2026 rounds 19 to 23 (lap time, ranges, undercut) | Not run yet (needs the December dump). Power analysis: 80 undercut events give 82% power at the 2024–25 skill; 20 events give 54%. |
| [14](specs/14-official-flag-laps.md) | Does the lap-time neutral detector agree with official race control (OpenF1, 80 races 2023 to 2026)? | **Partly.** It finds 96% of safety-car laps and all red-flag laps, but only 40% of VSC laps (recall 0.72, precision 0.81). New specs use the official laps from 2023. Exploratory: without the official laps, lap-time error on rounds 4 to 12 falls from 1.03 s to 0.78 s. |
| [15](specs/15-sc-hazard.md) | When does a safety car or VSC come out? Per-lap hazard model against the simulator's circuit-mean rule | Development (leave one season out, 80 races): log loss 0.097 against 0.114 for the simulator's rule and 0.103 for one constant rate. Lap 1 is about 15 times riskier. Locked test on 2026 rounds 13 to 23 after 6 December. |
| [16](specs/16-overtaking.md) | Can a learned model say when a car passes the car ahead? | Development (2026 rounds 1 to 12, 4,982 pair-laps): LightGBM log loss 0.154 against 0.249 for the simulator's pace rule and 0.257 for the base rate. Gap matters most. Locked test on rounds 19 to 23 in December. |
| [20](specs/20-simulator-c.md) | Do the safety-car and overtaking layers make a better race simulator? | **No, not yet.** Development (rounds 4 to 12): simulator C podium Brier 0.078 against 0.0785 for B and 0.070 for the grid; Spearman 0.754, 0.744 and 0.785. The pace input limits the simulator, not the race events. |

## Known limitations
- **Selection bias in the undercut model.** It learns from undercuts that teams chose to try. It gives the chance that an
  attempted undercut works, not the effect of pitting versus staying out. The site shows odds, not advice.
- **Small samples.** The final test has 6 races and only 20 undercut attempts. A bootstrap over 6 race blocks is coarse.
  The spec 13 power analysis shows that a model as good as on 2024 and 2025 passes a 20-event test only 54% of the time.
- **The lap-time range has one width.** It does not get wider in traffic: with the car ahead closer than 1 s, the 80% range
  holds 73.2% of laps (spec 12). The 95% range is slightly too narrow.
- **Missed neutral laps.** Jolpica has no flag data. When only part of the field is slow (the restart after a red flag,
  a VSC that covers part of a lap), the detector can miss the lap, and the next forecast is far off. The site replay shows
  one such lap. Spec 14 measured it against official race control: 28% of neutral laps are missed, mostly VSC laps.
  From 2023 the official laps are available (OpenF1); before 2023 only the detector.
- **Future information in specs 07 and 08.** Their models used `wait_laps` (how long the rival waited to respond), which is
  not known when the car pits. Spec 08 added a decision-time model to fix this, and spec 10 removed the feature entirely.
  The deployed model uses only gap, tyre-age difference and laps remaining.
- **p-values printed as 0.** A block-bootstrap p-value of 0.0 means no bootstrap sample reached the observed value:
  read it as p < 0.0001 (10,000 samples).
- **One unexplained outlier.** In spec 03, `gbm_2026` (trained on 2026 races only) had a 9.6 s mean error on round 10 (Belgium).
  `gbm_pretrain` did not. We did not find the cause. It is one reason the pre-trained model is the one we use.
- **Calibration at the extremes.** On 2024 and 2025, the 0.8 to 1.0 probability bin has only 6 events.
- **Dump date.** The pinned dump ends at the United States GP (round 18). Rounds 19 onward are not tested yet ([spec 13](specs/13-out-of-sample-rounds.md)).
