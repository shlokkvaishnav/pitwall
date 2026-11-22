# Spec 18 — A reinforcement-learning pit-strategy agent, inside the simulator

Status: registered on 2026-11-22, before the environment was run or any agent trained.

## 1. Objective
Train an agent that decides, lap by lap, whether to pit, and compare it with fixed plans inside the same simulated
races. Everything here is **inside the simulator**: a better agent here is not shown to be better in real races.

## 2. Environment (`pitwall.strategy_env`, "simulator C")
- Inputs per race: `pitwall.sim.inputs_from_history` (pace by driver, tyre wear slope, pit loss, stop counts, laps),
  built from races before it, exactly as specs 05 and 06.
- Lap time: pace + wear × tyre age + noise (`noise_s` = 1.0 s, as spec 05).
- Neutral periods: a period starts on a lap with the spec 15 `M2` hazard for that circuit (fitted on the 80 races of
  spec 14) and lasts 3, 4 or 5 laps (equal chance). In it: no passing, the field closes to 0.3 s gaps, and a pit stop
  costs half the normal pit loss (an assumption, not measured).
- Passing: for the car behind within 3.0 s, the spec 16 `gbm` gives the chance of a pass on this lap (features from the
  simulated race). If it does not pass but would cross the line first, it stays 0.2 s behind.
- Other cars: number of stops from history, laps spread evenly with ±3 laps of noise (as spec 05); if a neutral period
  starts and a car's next planned stop is within 8 laps, it stops now.
- The agent's car: the driver who starts 5th. At least one stop is required; finishing with none counts as last.
- Observation: lap fraction, tyre age, position, gap ahead and behind, neutral period active, stops made.
  Action: pit or stay out. Reward at the end: −(finishing position − 1) / (cars − 1).

## 3. Policies
| Name | Rule |
|---|---|
| `history` | The same rule as the other cars. |
| `fixed1` | One stop on lap s; s chosen by grid search over all laps on 200 training seeds. |
| `fixed2` | Two stops (s1, s2), grid search in steps of 3 laps on 200 training seeds. |
| `ppo` | PPO (stable-baselines3 2.4.1, default settings, 300,000 steps, seed 0) on training seeds. |

## 4. Races and evaluation
2026 rounds 4, 8 and 12 (fixed now). For each, the simulator is built from earlier races only. Evaluation on 1,000 seeds
(10,000 to 10,999) that no policy saw in training or grid search; the same seeds for every policy.

| Rule | Pass condition |
|---|---|
| S1 | In each of the 3 races, `ppo`'s mean finishing position ≤ `fixed1`'s. |
| S2 | Pooled over the 3 races: `ppo`'s mean position is better than `history`'s, with the 95% interval of the paired difference (bootstrap over seeds, 10,000 samples) below 0. |

## 5. Output
`src/pitwall/strategy_env.py`, `scripts/rl_strategy.py`, `results/18-rl-strategy.json` (with the PPO's pit-lap
distribution per race, for the site). Optional extra `rl`: stable-baselines3, gymnasium.
