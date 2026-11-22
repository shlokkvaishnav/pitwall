# State (2026-11-22)

## Branches
- main: spec 14 (official flag laps from OpenF1) merged. The detector finds 96% of SC laps, 40% of VSC laps
  (recall 0.72, precision 0.81, 80 races 2023 to 2026 r12). Decision: new specs use official laps from 2023
  (`lap_table(race, official_neutral=...)`, `pitwall.flags`). Spec 13 keeps the detector, as registered.

## Next
- Spec 15: safety-car hazard model (chance of SC/VSC in the next N laps by circuit and lap) from the official
  laps, fed into the race simulator. Register it before fitting; gate on locked 2027 races.
- December: new Jolpica dump with rounds 19-23, then run spec 13 as registered (section 6).
- Undercut confirmatory test needs 80 pooled events (2027).

## Open items
- FastF1 live-timing archive now needs an F1 account: no official flags before 2023 without a login.
- OpenF1 has no Las Vegas 2024/2025 race session; no CORS header, so no live browser polling.
- OpenF1 raw JSON cached in data/raw/openf1/ (not committed).
