# Spec 20 — Do the new layers make a better race simulator?

Status: registered on 2026-11-22, before simulator C was run on any race outcome.

## 1. Question
Simulator B (spec 06) orders the field better than the grid but gives worse podium chances (spec 11). Simulator C adds
the layers built since: the safety-car hazard (spec 15), the overtaking model (spec 16), and teams pitting early under a
safety car. Does the whole beat B and the grid?

## 2. Simulator C (`pitwall.strategy_env.Race`, every car following its plan)
- Inputs: simulator B's (spec 06: qualifying-based pace with a pace shock, wear, pit loss, stop counts), built from races
  before the one simulated.
- Neutral periods: spec 15 `M2` hazard; passing: spec 16 `gbm`; pit reaction: as spec 18.
- Retirements: the per-lap hazard of `inputs_from_history` (as simulators A and B).
- For race k, the hazard and overtaking models are fitted only on races before k.
- 2,000 runs per race, seed 0; finishing order = classified cars by laps done, then race time.

## 3. Measures (as spec 06)
Spearman rank correlation between the simulated mean position and the result (classified cars), and the podium Brier
score (chance of a top 3 against what happened), for simulator C, simulator B (re-run, spec 06 code) and the grid
baseline (podium frequency by grid slot in earlier races).

## 4. Development and test
- Development (no rule): 2026 rounds 4 to 12.
- **Test, once, with spec 13:** 2026 rounds 19 to 23.

| Rule | Pass condition (test races) |
|---|---|
| C1 | Mean podium Brier of C < B. |
| C2 | Mean podium Brier of C < the grid baseline. |
| C3 | Mean Spearman of C ≥ the grid's. |

The spec 11 rule R4 (B against the grid) failed on C2's measure; C2 is the main question.

## 5. Output
`scripts/race_sim_c.py`, `results/20-simulator-c-dev.json`, later `results/20-simulator-c-test.json`.
