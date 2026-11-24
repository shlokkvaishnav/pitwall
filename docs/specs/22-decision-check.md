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
- Tyre wear: `engine.tyre_deg`, the slope of clean lap times on tyre age net of fuel burn (driver effects; the stops
  separate age from lap number), median over earlier races at the circuit (all earlier races if none), at least 0.
  This replaces the wear input of simulators A to C (see the amendment below).
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

## Amendment (2026-11-24, before the full run)
A smoke run of the script on one race (2024 Miami, 6 decisions, not kept) put every first stop on laps 2 to 7. The
cause: the wear input of simulators A to C is the slope of lap time on tyre age within stints, which includes fuel
burn; there it was −0.042 s per lap, so older tyres looked faster and the earliest stop looked best (the same cause
as the "very early stops" of spec 20). The engine now uses the fuel-corrected wear of section 2. Nothing else
changed; the full run has not been made.

## Result (2026-11-24, commit f463659; 69 races of 2023 to 2025, 591 decisions)
Raw numbers: `results/22-decision-check.json`. Window ± 3 laps for every method; 95% race-block bootstrap intervals.

| Method | Window contains the real stop | Median error of the centre lap |
|---|---|---|
| Engine | 29.3% (24.0 to 34.6) | 7 laps |
| B1 tyre-age rule | 31.1% (23.6 to 38.9) | 7 laps |
| B2 fixed-lap rule | **36.7%** (29.5 to 43.9) | 5 laps |

Engine − B1: −1.9 points (−9.9 to 6.1); engine − B2: −7.4 points (−13.8 to −1.2). E1 is false: the engine does
not beat the simple rules, and the fixed-lap rule beats it. Stops not made on a neutral lap (437): engine 28.4%,
B1 35.0%, B2 38.0%. The simulator has one wear rate for every compound and no tyre-choice rule, so the lap it
prefers follows wear and traffic in the simulator, not the compound plans that set real stops.
