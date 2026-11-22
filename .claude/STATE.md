# State (2026-11-22)

## Branches
- main (spec 15 merged): spec 14 (official flag laps from OpenF1) merged. The detector finds 96% of SC laps, 40% of VSC laps
  (recall 0.72, precision 0.81, 80 races 2023 to 2026 r12). Decision: new specs use official laps from 2023
  (`lap_table(race, official_neutral=...)`, `pitwall.flags`). Spec 13 keeps the detector, as registered.

## Next
- Spec 15 registered and developed (hazard M2 log loss 0.097 vs 0.114 simulator rule, LOSO). After 6 Dec:
  `scripts/sc_hazard.py --test` once (2026 rounds 13-23). Then a spec to put M2 into the race simulator.
- After 6 Dec: `scripts/overtaking.py --test` once (spec 16, gbm 0.154 vs sim rule 0.249 on dev).
- December: new Jolpica dump with rounds 19-23, then run spec 13 as registered (section 6).
- Undercut confirmatory test needs 80 pooled events (2027).

## Open items
- FastF1 live-timing archive now needs an F1 account: no official flags before 2023 without a login.
- OpenF1 has no Las Vegas 2024/2025 race session; no CORS header, so no live browser polling.
- OpenF1 raw JSON cached in data/raw/openf1/ (not committed).
