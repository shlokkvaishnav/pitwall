# Spec 05 — Race simulator, version A

Status: We committed this file before the first run.

## 1. Objective
Make a lap-by-lap Monte Carlo race simulator (stage 2 of spec 00). It gives a probability for each finishing position.
We test it before the race: all inputs come from data before the race, and from the grid of the race.
This is a development preview of rule R4. Stage 3 (strategy agent) is allowed only if R4 passes on the holdout.

## 2. Inputs (for test race k)
| Input | Source |
|---|---|
| Grid | Results of race k. A pit-lane start (grid 0) is last. |
| Driver pace | Mean of the driver's median clean lap minus the field median clean lap, over the 2026 races before k. 0 if no race. |
| Lap noise | Standard deviation of clean-lap residuals (1.0 s, from spec 03). |
| Pit loss | Median pit loss at the same circuit in all earlier races. Pit loss = in-lap + out-lap − 2 × the driver's median clean lap in the race. Fallback: median over all circuits. |
| Tyre wear | Median slope of clean lap time against tyre age within stints, at the same circuit in earlier races. Fallback: all circuits. |
| Number of stops | The distribution of stops per classified driver at the same circuit in earlier races. Fallback: all circuits. |
| Safety cars | Mean number of neutralised periods per race at the same circuit in earlier races (Poisson). Each period lasts 4 laps. |
| Retirements | A per-lap hazard: the fraction of non-classified starters in the 2026 races before k, divided by the race length. |

## 3. Simulation
- 2,000 runs for each race, seed 0. The race length is the number of laps of the winner.
- Lap 1: the order of the grid, with gaps of 0.25 s for each position, and noise × 2.
- Each lap: lap time = driver pace + wear × tyre age + noise. A pit lap adds the pit loss and resets the tyre age.
  Pit laps are spread evenly over the race, with ±3 laps of uniform noise.
- Overtaking: a car can pass the car ahead on a lap only if it is at least 0.4 s faster on that lap. Else it stays 0.2 s behind.
- Safety car: during a neutralised period, no car passes, and the gaps become 0.3 s for each position at the end of the period.
- A retired car stays at the back.

## 4. Rules (development rounds 4 to 12)
| Rule | Pass condition |
|---|---|
| S1 Order | The mean Spearman correlation between the simulated order (mean simulated position) and the official classification is higher than for the grid order. Classified drivers only. |
| S2 Podium | The mean Brier score of the simulated podium probabilities is lower than for a grid baseline. Grid baseline: the frequency of a podium for each grid position in all races before race k. |
| S3 Calibration (report only) | Reliability of the podium probabilities in 5 bins. |

## 5. Output
`results/05-race-simulator.json`: the inputs and the scores for each race, the rule results, and the git commit SHA.
