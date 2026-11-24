# State (2026-11-24)

The project question: how far can public lap data take you towards a team's race-strategy model, and where does it
break? README is organised by layer (pace, race events, racing, signals, strategy) with a scorecard.

## Branches
- main: specs 14, 15, 16 merged and pushed.
- research/simulator-c (NOT merged, not pushed; owner must ask): spec 18 and 19 results, radio fixes. Left untouched.
- v2/strategy-engine (from origin/main, pushed, not merged): fast simulator (`pitwall.fastsim`, now also returns race
  time), spec 21 simulator D, spec 22 decision check (engine 29% vs fixed-lap rule 37%), spec 23 wear per compound
  (27%, no better), spec 24 SIMULATED regret (engine 2.3 s better than teams' real laps, same as fixed-lap rule,
  inside its own model), engine, live replay and site section "Lap by lap, as if live" (not deployed, not checked in a
  browser yet).

## Next
- After 2026-12-06: spec 13, then the `--test` runs of specs 15, 16, 17, 20 and 21 (`scripts/race_sim_d.py --test`,
  w = 0.5, c = 0.75) on rounds 19 to 23, once each.
- Owner: look at the new site section at 1280 and 390 px, light and dark; then merge and redeploy; refresh
  `docs/site.png`.
- Merge research/simulator-c when the owner says so (it touches STATE.md, README and the strategy site data).

## Open items
- Simulator wear: the per-compound fit (spec 23) is confounded; simulators A to D use the within-stint slope.
- Spec 23 section 6 (test on rounds 19 to 23) needs a `--test` mode in `scripts/decision_check.py` (2026 history).
- bench_sim, race_sim_d, decision_check, replay are not in `make reproduce`; decision_regret is (about 35 min).
- Spec 24 regret has a floor of several seconds (min of noisy means); compare options, not against zero.
- macOS: LightGBM and torch in one process deadlock unless all LightGBM fits run first and torch uses one thread.
- Rounds 13 to 18 are spent: never fit, calibrate or choose on them.
