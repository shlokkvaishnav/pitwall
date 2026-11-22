"""Simulator C and a lap-by-lap pit-strategy environment (spec 18). Inside the simulator only."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .sim import SC_GAP_S, START_GAP_S, STUCK_GAP_S, SimInputs

MAX_GAP_S = 3.0
SC_PACE = 1.4  # neutral lap = 1.4 x a normal lap
SC_PIT_FACTOR = 0.5  # a stop under a neutral period costs half (assumption, spec 18)
REACT_LAPS = 8


@dataclass
class World:
    """Everything fixed for one race: simulator inputs, per-lap neutral hazard, overtaking model, ego car."""

    inp: SimInputs
    hazard: np.ndarray  # (laps + 1,) chance a neutral period starts on each lap
    overtake: object  # pitwall.overtake.Models (gbm used)
    circuit_id: int
    ego: int = 4  # index in grid order: the car that starts 5th


class Race:
    """One simulated race. Call `step(pit)` once per lap for the ego car; others follow their plans."""

    def __init__(self, world: World, seed: int):
        self.w, self.rng = world, np.random.default_rng(seed)
        inp, d = world.inp, len(world.inp.drivers)
        self.n, self.d = inp.laps, d
        self.cum = np.arange(d) * START_GAP_S + self.rng.normal(0, 2 * inp.noise_s, d)
        self.age = np.ones(d)
        self.stops = np.zeros(d, int)
        self.lap = 1
        self.sc_left = 0
        n_stops = self.rng.choice(inp.stop_counts, d) if len(inp.stop_counts) else np.ones(d, int)
        self.plans = [
            sorted(
                {
                    int(np.clip(round(k * self.n / (s + 1)) + self.rng.integers(-3, 4), 2, self.n - 1))
                    for k in range(1, s + 1)
                }
            )
            for s in n_stops
        ]
        self.pace = inp.pace + (self.rng.normal(0, inp.pace_shock_s, d) if inp.pace_shock_s > 0 else 0.0)

    # ---------- state for the agent ----------
    def position(self, car: int) -> int:
        return int((self.cum < self.cum[car]).sum()) + 1

    def obs(self) -> np.ndarray:
        e = self.w.ego
        order = np.argsort(self.cum)
        p = int(np.flatnonzero(order == e)[0])
        ahead = self.cum[e] - self.cum[order[p - 1]] if p > 0 else 10.0
        behind = self.cum[order[p + 1]] - self.cum[e] if p < self.d - 1 else 10.0
        return np.array(
            [self.lap / self.n, self.age[e] / 30, p / (self.d - 1), min(ahead, 10) / 10, min(behind, 10) / 10,
             float(self.sc_left > 0), min(self.stops[e], 3) / 3],
            dtype=np.float32,
        )  # fmt: skip

    def done(self) -> bool:
        return self.lap >= self.n

    def ego_result(self) -> int:
        """Finishing position of the ego car; no stop at all counts as last (spec 18)."""
        return self.position(self.w.ego) if self.stops[self.w.ego] > 0 else self.d

    # ---------- one lap ----------
    def step(self, ego_pit: bool) -> None:
        inp, rng, lap = self.w.inp, self.rng, self.lap + 1
        if self.sc_left == 0 and rng.random() < self.w.hazard[min(lap, len(self.w.hazard) - 1)]:
            self.sc_left = int(rng.integers(3, 6))
        sc = self.sc_left > 0
        pit = np.zeros(self.d, bool)
        for i in range(self.d):
            if i == self.w.ego:
                pit[i] = ego_pit
                continue
            nxt = [p for p in self.plans[i] if p >= lap]
            if nxt and (nxt[0] == lap or (sc and self.sc_left >= 3 and nxt[0] - lap <= REACT_LAPS)):
                pit[i] = True
                self.plans[i] = nxt[1:]
        base = 90.0
        t = base + self.pace + inp.wear_s_per_lap * self.age + rng.normal(0, inp.noise_s, self.d)
        loss = inp.pit_loss_s * (SC_PIT_FACTOR if sc else 1.0)
        t = t + np.where(pit, loss, 0.0)
        order = np.argsort(self.cum)
        new = self.cum + t
        if sc:
            leader = self.cum[order[0]] + base * SC_PACE
            # the field closes up behind the leader, in the order of the last lap, plus any pit loss
            new_sorted = leader + np.arange(self.d) * SC_GAP_S + np.where(pit[order], loss, 0.0)
            new[order] = new_sorted
        else:
            self._passes(order, new, t)
        self.cum = new
        self.age = np.where(pit, 1.0, self.age + 1.0)
        self.stops += pit
        self.lap = lap
        self.sc_left = max(0, self.sc_left - 1)

    def _passes(self, order: np.ndarray, new: np.ndarray, t: np.ndarray) -> None:
        """For each car within 3 s of the car ahead (last lap's order), draw a pass with the spec 16 gbm."""
        pairs = []
        for k in range(1, self.d):
            a, b = order[k - 1], order[k]
            if self.cum[b] - self.cum[a] <= MAX_GAP_S and new[b] < new[a] + STUCK_GAP_S:
                pairs.append((a, b))
        if not pairs:
            return
        ia, ib = np.array(pairs).T
        p = self.w.overtake.gbm_fast(  # type: ignore[attr-defined]
            self.w.circuit_id,
            self.cum[ib] - self.cum[ia],
            t[ia] - t[ib],
            self.age[ia] - self.age[ib],
            (self.lap + 1) / self.n,
        )
        passed = self.rng.random(len(p)) < p
        for (a, b), ok in zip(pairs, passed):
            if ok:
                new[b] = min(new[b], new[a] - STUCK_GAP_S)
            else:
                new[b] = max(new[b], new[a] + STUCK_GAP_S)


def run(world: World, seed: int, policy) -> tuple[int, list[int]]:
    """Play one race with policy(race) -> bool. Returns (ego finishing position, ego pit laps)."""
    r = Race(world, seed)
    laps = []
    while not r.done():
        pit = bool(policy(r))
        if pit:
            laps.append(r.lap + 1)
        r.step(pit)
    return r.ego_result(), laps


def fixed_policy(stops: list[int]):
    s = set(stops)
    return lambda r: (r.lap + 1) in s


def history_policy(r: Race) -> bool:
    """The ego car follows the other cars' rule (its own sampled plan, with the neutral-period reaction)."""
    e, lap = r.w.ego, r.lap + 1
    nxt = [p for p in r.plans[e] if p >= lap]
    go = bool(nxt) and (nxt[0] == lap or (r.sc_left >= 3 and nxt[0] - lap <= REACT_LAPS))
    if go:
        r.plans[e] = nxt[1:]
    return go
