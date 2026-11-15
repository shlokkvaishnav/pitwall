"""2026 energy limits from the FIA text (see specs/01-energy-limits-and-data.md, section 3).

Source: FIA 2026 F1 Regulations, Section C (Technical), Issue 21, 19 October 2026, Article C5.2.
"""

from __future__ import annotations

import numpy as np

from .battery import Limits

SOURCE = "FIA 2026 F1 Regulations Section C Iss 21 (2026-10-19), Art. C5.2"

ERS_K_MAX_KW = 350.0  # C5.2.7, absolute DC power, deploy and harvest
SOC_WINDOW_MJ = 4.0  # C5.2.9
RECHARGE_PER_LAP_MJ = 8.5  # C5.2.10
RECHARGE_PER_LAP_REDUCED_MJ = 7.0  # C5.2.10 i, at Competitions that the FIA selects
RECHARGE_QUALIFYING_MIN_MJ = 4.0  # C5.2.10 ii, lowest value that the FIA can set
EXTRA_HARVEST_MJ = 0.5  # C5.2.10 iii, with conditions in B7.2
MGU_K_MAX_TORQUE_NM = 500.0  # C5.2.11


def deploy_limit_kw(speed_kph, overtake: bool = False, power_limited: bool = False) -> np.ndarray:
    """Maximum ERS-K DC power that can propel the car at a given speed (C5.2.8 and C5.2.7)."""
    v = np.asarray(speed_kph, dtype=float)
    if overtake and power_limited:
        raise ValueError("choose one mode: overtake or power_limited")
    if overtake:  # C5.2.8 ii
        p = np.where(v < 355.0, 7100.0 - 20.0 * v, 0.0)
    else:  # C5.2.8 i
        p = np.where(v < 340.0, 1800.0 - 5.0 * v, np.where(v < 345.0, 6900.0 - 20.0 * v, 0.0))
        if power_limited:  # C5.2.8 iii
            p = np.where(v < 310.0, 250.0, p)
    return np.clip(p, 0.0, ERS_K_MAX_KW)


def race_limits(reduced_recharge: bool = False, extra_harvest: bool = False) -> Limits:
    """Battery limits for a race lap. reduced_recharge: the FIA selected 7 MJ for this event."""
    per_lap = RECHARGE_PER_LAP_REDUCED_MJ if reduced_recharge else RECHARGE_PER_LAP_MJ
    if extra_harvest:
        per_lap += EXTRA_HARVEST_MJ
    return Limits(
        capacity_mj=SOC_WINDOW_MJ,
        max_deploy_kw=ERS_K_MAX_KW,
        max_harvest_kw=ERS_K_MAX_KW,
        max_harvest_per_lap_mj=per_lap,
    )
