"""Battery energy store with hard limits.

The limits are parameters. They have no default values, because spec 01 must record
their source in the FIA regulations first (see specs/00-charter.md, section 8).

Sign convention: positive power deploys energy (the battery discharges),
negative power harvests energy (the battery charges).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Limits:
    capacity_mj: float  # usable energy between empty and full
    max_deploy_kw: float  # maximum discharge power
    max_harvest_kw: float  # maximum charge power (positive number)
    max_harvest_per_lap_mj: float  # maximum energy that the car can recover in one lap

    def __post_init__(self) -> None:
        for name, value in vars(self).items():
            if not value > 0:
                raise ValueError(f"{name} must be > 0")


@dataclass(frozen=True)
class LapResult:
    charge_mj: np.ndarray  # charge after each step
    power_kw: np.ndarray  # power that the store accepted at each step, after the limits
    harvested_mj: float
    deployed_mj: float


def simulate_lap(
    power_kw: np.ndarray,
    dt_s: np.ndarray | float,
    charge0_mj: float,
    limits: Limits,
    deploy_cap_kw: np.ndarray | None = None,
) -> LapResult:
    """Apply the requested power profile for one lap and enforce all limits.

    deploy_cap_kw: optional limit on deploy power at each step (for example, the speed curve of the regulations).

    Each step clips the power to the power limits, to the charge in the store,
    to the free space in the store, and to the harvest budget that is left for the lap.
    """
    power = np.asarray(power_kw, dtype=float)
    dt = np.broadcast_to(np.asarray(dt_s, dtype=float), power.shape)
    cap = np.full(power.shape, limits.max_deploy_kw) if deploy_cap_kw is None else np.asarray(deploy_cap_kw, float)
    if cap.shape != power.shape:
        raise ValueError("deploy_cap_kw must have the same shape as power_kw")
    if np.any(dt <= 0):
        raise ValueError("time steps must be > 0")
    if not 0 <= charge0_mj <= limits.capacity_mj:
        raise ValueError("initial charge must be between 0 and capacity")

    charge = charge0_mj
    harvest_left = limits.max_harvest_per_lap_mj
    charges = np.empty_like(power)
    accepted = np.empty_like(power)
    harvested = deployed = 0.0
    for i, (p, step, c) in enumerate(zip(power, dt, cap)):
        p = float(np.clip(p, -limits.max_harvest_kw, min(limits.max_deploy_kw, c)))
        energy = p * step / 1000.0  # kW * s = kJ -> MJ
        if energy > 0:
            energy = min(energy, charge)
            deployed += energy
        else:
            energy = -min(-energy, limits.capacity_mj - charge, harvest_left)
            harvest_left += energy
            harvested -= energy
        charge -= energy
        charges[i] = charge
        accepted[i] = energy * 1000.0 / step
    return LapResult(charge_mj=charges, power_kw=accepted, harvested_mj=harvested, deployed_mj=deployed)
