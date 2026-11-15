# Spec 00 — Project charter

Status: We committed this file before we downloaded data.
We change this file only with a dated amendment at the end.

## 1. Problem
The 2026 F1 cars get approximately half of their power from the battery.
The energy use of each car changes its lap times and its overtakes.
But public timing data does not show the battery state.

The FIA changed the energy limits during the 2026 season.
Also, the tyre models from earlier years may not work on the 2026 cars.

## 2. Objective
We make the project in three stages. Each stage uses the stage before it.

1. **State model.** For each car, we estimate two hidden states: the battery charge and the tyre wear.
   The inputs are public timing and car data (speed, throttle, brake, gear, position).
   The physical energy limits are hard constraints.
2. **Race simulator.** We make a lap-by-lap race simulator on the state model.
   We compare the simulator with real races before we use it.
3. **Strategy agent.** We train a reinforcement-learning agent in the simulator.
   We compare its pit decisions with the real decisions of the teams.

## 3. Data
| Source | Content | Use |
|---|---|---|
| FastF1 | Lap times, stints, tyre compounds, pit stops, track status, weather, car data, position data | All stages |
| Jolpica-F1 | Results and grid positions | Simulator checks |

We use seasons 2022 to 2026. The 2022 season started the current car design.
We keep raw data in `data/`. Git ignores this folder. Do not commit raw data. Do not publish raw data.
The tests use only synthetic data.

## 4. Splits
| Split | Races | Use |
|---|---|---|
| Pre-training | 2022 to 2025 | Tyre model only. These cars have a different power unit. |
| Development | 2026 races before 2026-09-01 | Train and tune all models. |
| **Holdout** | **2026 races on or after 2026-09-01** | **Locked.** Only the final spec can use it. |

The code enforces the lock: `pitwall.splits.assert_not_holdout()` raises an error.

## 5. How we test a hidden state
The battery state is not in the data. Thus, we cannot measure its error directly.
We test the state model through quantities that we can see:

- the next lap time;
- the speed loss in the last part of long straights (this loss shows harvesting at full throttle);
- the overtakes on straights.

## 6. Final rules (holdout)
We set these rules now, before the experiments.
We can change them only with an amendment, and only before we use the holdout.

| Rule | Pass condition |
|---|---|
| R1 Lap time | The mean absolute error of the next lap time is at least 5% lower than the best baseline. A one-sided Diebold-Mariano test gives p < 0.05. Baselines: previous lap, linear tyre wear per stint, a state-space tyre model without energy. |
| R2 Straights | The error of the predicted speed loss in the last 200 m of long straights is at least 10% lower than the best baseline. |
| R3 Tyre transfer | A tyre model that we pre-train on 2022 to 2025 and then adapt on 2026 has a lower lap-time error than a model that we train on 2026 data only. |
| R4 Simulator | The rank correlation (Spearman) of simulated and real finishing order is higher than for the grid order. The Brier score of the podium probabilities is lower than for a grid-order baseline. |
| R5 Strategy | We do this step only if R4 passes. In the simulator, the agent gets a better mean finishing position than the real team strategy. We report this result as a simulator result only. |

If R4 fails, we do not do R5. We report the failure.
If a rule fails, we keep the result and we report it.

## 7. Rules for each experiment
1. Write a spec in `specs/NN-name.md`. Commit it before the code that runs it.
2. Give each spec its pass/fail rules, with numbers, before the run.
3. Write the results to `results/NN-name.json`, with the git commit SHA.
4. Keep the results of failed rules. Do not remove them.
5. Record each change after a run as an amendment (A1, A2, …), with a date and a reason.

## 8. Limits
FastF1 data is not official F1 data. We use it for research only.
The site shows statistics and charts. It does not show raw data.
Spec 01 finds the energy limits from the FIA regulations, with the dates of each change.
The code does not use a limit until spec 01 records its source.

## 9. Output
A static site on GitHub Pages. It has no server.
