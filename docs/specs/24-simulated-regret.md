# Spec 24 — Simulated strategy regret of the engine's pit lap

Status: registered on 2026-11-24, before any run of the script. Development data only (2023 to 2025); no 2026 race
is used and no locked test is run.

## 1. Question and label
**SIMULATED.** Every number here comes from the engine's own fast simulator. The same model picks the engine's lap
and scores it, so this is not independent evidence of real-world gains. It asks only: inside the model, how much race
time do the engine's pit laps and the real teams' pit laps cost compared with the best lap?

## 2. Decisions and options
The same decisions as spec 22 (top 5 finishers of each 2023 to 2025 race, each real stop; the state at decision lap
t0 from `engine.state_at`; the same world, candidate grid t0 + 1 to min(t0 + 45, laps - 1), and `extra` stops).
Four options for the next stop lap:
- (a) Engine: `engine.pit_window` as in spec 22 (40 runs per candidate, seed = race index, 5-lap smoothing). It uses
  only the state at t0.
- (b) Actual: the team's real stop lap.
- (c) Fixed-lap rule: B2 of spec 22, section 3.
- (d) Tyre-age rule: B1 of spec 22, section 3.
Decisions whose real stop is outside the grid, or with no candidate, are dropped for all options; the count is reported.

## 3. Scoring
A separate batch (seed = race index + 1000) simulates 100 races per grid lap with no retirements; the metric is the
mean simulated finish time of the car (s). Means are smoothed over 5 grid laps as in spec 22. For an option at lap L:
time(L) = smoothed mean at L (L clipped to the grid); regret(L) = time(L) minus the lowest smoothed time in the grid.

## 4. Measures (no pass rule; report only)
- Mean regret in seconds for each option.
- Paired mean time difference (option minus engine, s; positive = slower than the engine) for (b), (c), (d).
- 95% intervals: race-block bootstrap (10,000 samples, seed 0). Also split by stops on neutral laps and green laps.
Favourable and unfavourable results are reported alike.

## 5. Output
`scripts/decision_regret.py`, `results/24-decision-regret.json`.
