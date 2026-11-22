# State (2026-11-22)

The project question: how far can public lap data take you towards a team's race-strategy model, and where does it
break? README is organised by layer (pace, race events, racing, signals, strategy) with a scorecard.

## Branches
- main: specs 14, 15, 16 merged and pushed.
- research/simulator-c (NOT merged, not pushed; owner must ask; contains research/deep-lap-model): specs 17 (deep lap
  model, dev recorded: 0.93 s vs 1.03 s), 18 (RL strategy, recorded: S1 fails, S2 passes), 19 (team radio, recorded: R1 and R2 fail), 20
  (simulator C, dev recorded), TreeEnsemble, README layer rewrite, site section "One race, layer by layer"
  (`scripts/export_strategy.py` -> `site/data/race-strategy.json`; checked at 1280 and 390, light and dark).

## Next
- After 2026-12-06: spec 13 and the `--test` runs of specs 15, 16, 17, 20 on rounds 19 to 23, once.
- Merge research/simulator-c to main and push when the owner says so; refresh `docs/site.png`.

## Open items
- OpenF1 has no team radio for 2026 rounds 1 to 4 (404).
- Simulator C's pace input limits it (spec 20 dev): the pit-window chart favours very early stops.
- macOS: LightGBM and torch in one process deadlock unless all LightGBM fits run first and torch uses one thread.
- Rounds 13 to 18 are spent: never fit, calibrate or choose on them.
