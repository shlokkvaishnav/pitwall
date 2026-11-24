# Spec 22 — Does the engine's pit window contain the real teams' stops?

Status: registered on 2026-11-24, before the engine was run on any of these races. Development data only
(2023 to 2025); no 2026 race is used.

## 1. Question
The strategy engine simulates the rest of a race from the real race so far and picks the lap where a car's next stop
gives the best mean finishing position. Real teams have far more data. On past races, how often does the engine's
window contain the lap the team really chose, and is that more often than simple rules?

## 2. Engine (`pitwall.engine`, fast simulator)
- World for race k of season s: simulator C inputs (spec 20, section 2; spec 06 pace, form and retirements from
  earlier races of season s), built only from races before k. Neutral-period hazard: spec 15 `M2` fitted on races
  before k (a flat rate from `inputs_from_history` if fewer than 5 such races have flag data). Passing: spec 16 `gbm`
  fitted on pair-laps of seasons before s.
- Cars: the top 5 classified finishers. Each of their real stops is one decision (stops on lap 1 are skipped).
- Decision lap t0: the first lap of the stint that the stop ends (lap 1 for the first stop; the out-lap after the
  previous stop otherwise). The state is the real race at the end of t0 (`engine.state_at`: race times, tyre ages,
  stops, retirements), with nothing from later laps. The real stop lap does not choose t0.
- Candidates for the next stop: t0 + 1 to min(t0 + 45, laps − 1). After it, `extra` more stops spread evenly, where
  `extra` = (the most common stop count at this circuit in earlier races, or in all earlier races if none) − stops
  made − 1, at least 0. 40 runs per candidate, one batch, seed = race index; smoothed over 5 candidate laps.
- Window: best lap ± 3 (7 laps).

## 3. Baselines (same width, ± 3 laps)
- B1 tyre age: stop when the stint reaches the median length of the same stint number in earlier races at this
  circuit (all earlier races if none): t0 − 1 + median length.
- B2 fixed lap: lap round(j × laps / (n + 1)) for stop j of n = the most common stop count (as above); if j > n,
  half way from the previous stop to the end.
Windows are clipped to the candidate range. A real stop outside the candidates (more than 45 laps after t0) counts
as a miss for every method; a stop on the lap after the previous one (no candidate) is skipped.

## 4. Measures
- Containment rate: the share of decisions where the window contains the real stop lap, for the engine, B1 and B2.
- 95% interval: race-block bootstrap (10,000 samples, seed 0). The same for the paired difference engine − B1 and
  engine − B2.
- Also: the median absolute error of the best lap; the rates for stops not made on a neutral lap (lap table flag).
- Report-only comparison (no pass rule; development data): E1 = the 95% interval of engine − best baseline is above 0.

## 5. Output
`scripts/decision_check.py`, `results/22-decision-check.json`.
