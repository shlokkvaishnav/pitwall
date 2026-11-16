# pitwall

pitwall tries to find the hidden battery state and tyre wear of 2026 F1 cars from public timing data.
Then it tests a race simulator and a pit-strategy agent against real races.

## Why
The 2026 F1 cars get approximately half of their power from the battery.
Energy use changes lap times and overtakes. But public data does not show the battery state.
Also, the tyre models from earlier years may not work on the 2026 cars.

## How it works
1. **Lap model.** A gradient-boosting model predicts the next lap time of each car. It learns on 2022 to 2025 and on earlier 2026 races.
2. **Energy regime.** A hidden Markov model looks for "push" and "harvest" laps in the lap-time residuals.
3. **Race simulator.** A lap-by-lap Monte Carlo simulator gives a probability for each finishing position.
4. **Strategy agent.** A reinforcement-learning agent learns pit decisions in the simulator.
   We train it only if the simulator passes its test on the holdout.

## Method
- We write a spec before each experiment. Each spec has pass/fail rules with numbers.
- The 2026 races on or after 1 September 2026 are a locked holdout. The code enforces the lock.
- We keep failed results, and we report them.

Read the charter: [specs/00-charter.md](specs/00-charter.md).

## Results (development races, 2026 rounds 4 to 12)
| Spec | Test | Result |
|---|---|---|
| [01](specs/01-energy-limits-and-data.md) | Energy limits from the FIA regulations. Data checks of the Jolpica dump. | Pass (one check is not correct, see the spec) |
| [02](specs/02-lap-baselines.md) | Lap-time baselines. The best is the previous lap: 1.05 s mean error. | Done |
| [03](specs/03-lap-model.md) | Lap model against the previous lap | **Pass:** 11.5% lower error, p < 0.0001 |
| [04](specs/04-energy-regime.md) | Hidden energy regime in lap times | **Fail:** no regime. The second state is an outlier state. |
| [05](specs/05-race-simulator.md) | Simulator version A against the grid | **Fail:** Spearman 0.72 against 0.79 |
| [06](specs/06-race-simulator-b.md) | Simulator version B (qualifying pace) against the grid | **Fail:** Spearman 0.74 against 0.79 |
| [07](specs/07-undercut.md) | Undercut model: does the car that pits first come out ahead? | **Pass:** log loss 0.62 against 0.70 (2022 to 2025), 0.56 against 0.69 (2026) |
| [08](specs/08-undercut-b.md) | Undercut with tyre compounds, and a model that uses only data known when the driver pits | **Mixed:** compounds add nothing (fail). Decision-time model: p = 0.054 on 2022 to 2025 (fail, the bar is 0.05), pass on 2026. |
| [09](specs/09-undercut-replication.md) | The decision-time undercut model on 136 new duels (2018 to 2021) | **Pass:** log loss 0.63 against 0.69, p = 0.016 |

The strategy agent is blocked, because no simulator is better than the grid.
The undercut model (spec 07) tests one strategy decision without the simulator.

## Quick start
```bash
make install
make check   # lint and tests
```

## Data
- The Jolpica-F1 database dump (lap times, pit stops, results, qualifying). We check its SHA-256.
- TracingInsights open data (tyre compound, tyre life and stint for each lap; MIT and Apache-2.0). We do not download holdout races.
Do not commit raw data. The site shows statistics only.
