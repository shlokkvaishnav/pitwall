# Spec 01 — Energy limits and data layer

Status: We committed this file before the data check run.

## 1. Objective
1. Record the 2026 energy limits from the FIA text, with the article and the issue.
2. Put the limits in the code, with tests.
3. Load the FastF1 data for the 2026 development races, and check the data quality.

## 2. Source
FIA 2026 Formula 1 Regulations, Section C (Technical), **Issue 21, 19 October 2026**, Article C5.2.
Index of all issues: https://www.fia.com/regulation/category/110

## 3. Limits (Issue 21)
| Limit | Value | Article |
|---|---|---|
| ERS-K electrical DC power, absolute (deploy and harvest) | not more than 350 kW | C5.2.7 |
| ERS-K deploy power, Overtake not active | 1800 − 5·v kW for v < 340 km/h. 6900 − 20·v kW for 340 ≤ v < 345 km/h. 0 kW for v ≥ 345 km/h. | C5.2.8 i |
| ERS-K deploy power, Overtake active | 7100 − 20·v kW for v < 355 km/h. 0 kW for v ≥ 355 km/h. | C5.2.8 ii |
| ERS-K deploy power, power-limited period (race, specified sectors) | 250 kW for v < 310 km/h, then the same curve as C5.2.8 i | C5.2.8 iii |
| Energy store state-of-charge window | not more than 4 MJ between maximum and minimum | C5.2.9 |
| Recharge per lap | not more than 8.5 MJ | C5.2.10 |
| Recharge per lap, reduced | 7 MJ at Competitions that the FIA selects | C5.2.10 i |
| Recharge per lap, qualifying | not less than 4 MJ at Competitions that the FIA selects (Issue 21 changed this from 5 MJ) | C5.2.10 ii |
| Additional harvest | up to 0.5 MJ per lap, with conditions in Article B7.2 | C5.2.10 iii |
| MGU-K torque | not more than 500 Nm | C5.2.11 |

All deploy limits are also capped by the 350 kW absolute limit.
A lap starts and stops at the timing line. In the pits, the lap stops at the start of the pit lane.

## 4. Open points
1. **Per-event recharge limit.** The FIA selects the events with 7 MJ. We look for the FIA event documents.
   If we cannot find the value for an event, the state model estimates it from the set {7.0, 8.5} MJ.
2. **History of changes.** Issues 15 to 20 can have different values. Spec 02 compares them and records the date of each change.
   Until then, the code uses Issue 21 for all 2026 races.
3. **Overtake and power-limited periods.** Public data does not show when they are active. The state model treats them as hidden.

## 5. Data layer
- `pitwall.data.load_race(year, round)` loads one race with FastF1.
  It checks the race date with `pitwall.splits` first. A holdout race raises `HoldoutError`.
- The FastF1 cache is in `data/fastf1-cache/`. Git ignores it.
- Outputs per race: the laps table and the car data for each driver (speed, RPM, gear, throttle, brake, time).

## 6. Data check rules
We run the check on all 2026 races before 2026-09-01 (rounds 1 to 12).

| Rule | Pass condition |
|---|---|
| D1 Laps | For each race, at least 90% of the laps of the classified drivers have a lap time. |
| D2 Car data rate | For at least 95% of driver-races, the median time between car data samples is not more than 300 ms. |
| D3 Speed limit | In the car data, the fraction of samples above 360 km/h is less than 0.1%. This checks the units and the regulation curves. |

If a race fails D1 or D2, we record it, and later specs do not use it.

## 7. Output
`results/01-data-check.json`: the results for each race, the rule results, and the git commit SHA.

## Amendment A1 (2026-11-15)
**Reason.** See spec 00, amendment A1. FastF1 does not give data without an F1 TV account.

**Changes to section 5 (data layer).**
- `pitwall.data` loads from the Jolpica-F1 API (`https://api.jolpi.ca/ergast/f1/`): schedule, laps, pit stops, results.
- The client keeps a cache in `data/jolpica-cache/`. It sends not more than one request each 8 s,
  because the API allows approximately 500 requests each hour.
- The loader checks the race date with `pitwall.splits` before it gets the laps. A holdout race raises `HoldoutError`.

**Changes to section 6 (rules).** D2 and D3 needed car data. We replace them:

| Rule | Pass condition |
|---|---|
| D1 Laps | For each race, the laps table has at least 90% of the laps of the classified drivers (laps from the results). |
| D2 Pit stops | At least 99% of pit stops are on a lap that is in the laps table for that driver. |
| D3 Order | For at least 95% of classified drivers, the position on the last lap is the same as the result position. |

Section 4 (limits) does not change. The limits are constraints on the hidden energy mode.

## Amendment A2 (2026-11-15)
**Reason.** The API is slow: approximately 12 minutes for each race. 2022 to 2026 has approximately 110 races.
Jolpica gives a free CSV dump of its full database for non-commercial use. The free dump is 14 days old.

**Change to section 5 (data layer).**
- The source is the free "delayed" CSV dump: uploaded 2026-11-01T02:34:25Z,
  SHA-256 `34ae3788503c17931e500c347211efaa534a93fced707ed7788bfe17dd2c4334`.
  It has all races before that date. The 2026 holdout races after that date are not in it. This is correct for the lock.
- `pitwall.dump` reads the dump into the same `Race` object as the API loader. Race sessions only (type `R`).
- The API loader stays for checks.
- We keep the dump in `data/raw/jolpica-dump/`. Git ignores this folder. Do not commit the dump. Do not publish it.

**Change to section 6 (rules).** D1 to D3 run on the dump. We add one rule:

| Rule | Pass condition |
|---|---|
| D4 Dump = API | For the races in the API cache, at least 99.5% of the (driver, lap) rows have the same position and lap time (±0.001 s) in the dump and in the API. |

The data check also reports the same numbers for 2022 to 2025 (pre-training data). D1 to D3 apply to these seasons too.

## Result note (2026-11-15)
D1, D2 and D4 pass on the dump. D3 fails: 83.8% (2022 to 2025) and 82.0% (2026 development), not 95%.
The cause is not a data defect. Post-race time penalties change the final result after the last lap
(for example, 2026 round 6: three drivers lost four places each after the finish).
Thus, D3 was a wrong check. Later specs use the laps table for the order during the race and the results table only for the final classification.
No race is excluded because of D3.
