# pitwall

pitwall finds the hidden battery state and tyre wear of 2026 F1 cars from public timing data.
Then it uses these states in a race simulator and a pit-strategy agent.

## Why
The 2026 F1 cars get approximately half of their power from the battery.
Energy use changes lap times and overtakes. But public data does not show the battery state.
Also, the tyre models from earlier years may not work on the 2026 cars.

## How it works
1. **State model.** For each car, a state-space model estimates the battery charge and the tyre wear.
   The energy limits of the regulations are hard constraints.
2. **Race simulator.** A lap-by-lap Monte Carlo simulator uses the state model.
   We compare the simulator with real races before we use it.
3. **Strategy agent.** A reinforcement-learning agent learns pit decisions in the simulator.
   We train it only if the simulator passes its test.

## Method
- We write a spec before each experiment. Each spec has pass/fail rules with numbers.
- The 2026 races on or after 1 September 2026 are a locked holdout. The code enforces the lock.
- The battery state is not in the data. Thus, we test it through lap times and speed on straights.
- We keep failed results, and we report them.

Read the charter: [specs/00-charter.md](specs/00-charter.md).

## Milestones
| Milestone | Content | Status |
|---|---|---|
| M0 | Charter, holdout lock, energy store with hard limits, CI, site | Done |
| M1 | FastF1 data layer. Energy limits from the FIA regulations, with dates. | Next |
| M2 | Baselines and the tyre model (pre-train 2022 to 2025, adapt on 2026) | |
| M3 | Battery and tyre state-space model | |
| M4 | Race simulator and its check against real races | |
| M5 | Strategy agent, final holdout run and report | |

## Quick start
```bash
make install
make check   # lint and tests
```

## Data
FastF1 and Jolpica-F1. FastF1 data is not official F1 data. We use it for research only.
Do not commit raw data. The site shows statistics only.
