"""Spec 18: PPO pit-strategy agent inside simulator C, against fixed plans, on 2026 rounds 4, 8 and 12.

Usage: PYTHONPATH=src:scripts .venv/bin/python scripts/rl_strategy.py   (needs the `rl` extra)
Writes results/18-rl-strategy.json. Inside the simulator only.
"""

from __future__ import annotations

import itertools
import json
import subprocess
import time
from dataclasses import replace
from pathlib import Path

import gymnasium as gym
import lightgbm  # noqa: F401  (load LightGBM's OpenMP before torch's; the other order crashes on macOS)
import numpy as np
import pandas as pd
from race_sim_b import history
from sc_hazard import dev_rows
from stable_baselines3 import PPO

from pitwall.dump import Dump
from pitwall.hazard import Models as HazardModels
from pitwall.hazard import race_rows
from pitwall.overtake import Models as OvertakeModels
from pitwall.pace import fit, qualifying_gap
from pitwall.sim import inputs_from_history
from pitwall.strategy_env import Race, World, fixed_policy, history_policy, run

ROOT = Path(__file__).resolve().parents[1]
ROUNDS = [4, 8, 12]
TRAIN_SEEDS = range(200)
EVAL_SEEDS = range(10_000, 11_000)
PPO_STEPS = 300_000


def build_worlds(dump: Dump) -> dict[int, World]:
    races, stats, rows = history(dump, list(range(1, 13)))
    hz = dev_rows(dump)
    hazard = HazardModels(hz[hz["season"] < 2026])  # no 2026 race informs the simulator
    pairs = pd.read_csv(ROOT / "data" / "derived" / "pair_laps.csv.gz")
    overtake = OvertakeModels(pairs[pairs["season"] < 2026])
    worlds = {}
    for k in ROUNDS:
        hist_keys = [key for key in stats if key[0] < 2026 or key[1] < k]
        in_hist = rows["season"].lt(2026) | rows["round"].lt(k)
        pf = fit(rows[in_hist])
        res = races[(2026, k)].results
        laps = int(res["laps"].max())
        cid = stats[(2026, k)].circuit_id
        base = inputs_from_history([stats[x] for x in hist_keys], cid, res[["driver", "grid"]], laps)
        q = qualifying_gap(dump.qualifying(2026, k), base.drivers)
        inp = replace(base, pace=pf.predict(q, base.pace), pace_shock_s=pf.sigma_r)  # simulator B inputs (spec 06)
        lap_rows = race_rows({}, laps, season=2026, round=k, circuit_id=cid)
        h = np.concatenate([[0.0], hazard.predict(lap_rows)["M2"]])
        worlds[k] = World(inp, h, overtake, cid, ego=4)
    return worlds


class Env(gym.Env):
    def __init__(self, world: World, seeds):
        self.world, self.seeds, self.i = world, list(seeds), 0
        self.observation_space = gym.spaces.Box(0.0, 1.0, (7,), np.float32)
        self.action_space = gym.spaces.Discrete(2)

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        self.race = Race(self.world, self.seeds[self.i % len(self.seeds)])
        self.i += 1
        return self.race.obs(), {}

    def step(self, action):
        self.race.step(bool(action))
        done = self.race.done()
        reward = -(self.race.ego_result() - 1) / (self.race.d - 1) if done else 0.0
        return self.race.obs(), reward, done, False, {}


def mean_pos(world: World, seeds, policy) -> tuple[np.ndarray, list[list[int]]]:
    out = [run(world, s, policy) for s in seeds]
    return np.array([p for p, _ in out]), [laps for _, laps in out]


def main() -> None:
    dump = Dump(ROOT / "data" / "raw" / "jolpica-dump" / "csv")
    worlds = build_worlds(dump)
    report, paired = [], []
    for k, w in worlds.items():
        t0 = time.time()
        n = w.inp.laps
        g1 = {s: mean_pos(w, TRAIN_SEEDS, fixed_policy([s]))[0].mean() for s in range(5, n - 4)}
        s1 = min(g1, key=g1.__getitem__)
        cand2 = [(a, b) for a, b in itertools.combinations(range(5, n - 4, 3), 2) if b - a >= 8]
        g2 = {c: mean_pos(w, TRAIN_SEEDS, fixed_policy(list(c)))[0].mean() for c in cand2}
        s2 = min(g2, key=g2.__getitem__)
        model = PPO("MlpPolicy", Env(w, TRAIN_SEEDS), seed=0, verbose=0, device="cpu")
        model.learn(PPO_STEPS)
        ppo = lambda r, m=model: int(m.predict(r.obs(), deterministic=True)[0]) == 1
        res = {}
        laps_ppo: list[list[int]] = []
        for name, pol in (
            ("history", history_policy),
            ("fixed1", fixed_policy([s1])),
            ("fixed2", fixed_policy(list(s2))),
            ("ppo", ppo),
        ):
            pos, laps = mean_pos(w, EVAL_SEEDS, pol)
            res[name] = pos
            if name == "ppo":
                laps_ppo = laps
        rec = {
            "round": k,
            "laps": n,
            "fixed1_lap": s1,
            "fixed2_laps": list(s2),
            **{f"{name}_mean_pos": float(v.mean()) for name, v in res.items()},
            "ppo_stops": np.bincount([len(x) for x in laps_ppo], minlength=4).tolist(),
            "ppo_first_stop_laps": np.bincount([x[0] for x in laps_ppo if x], minlength=n + 1).tolist(),
        }
        report.append(rec)
        paired.append(res["ppo"] - res["history"])
        print(rec | {"ppo_first_stop_laps": "..."}, f"{time.time() - t0:.0f} s", flush=True)

    d = np.concatenate(paired)
    rng = np.random.default_rng(0)
    boots = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(10_000)]
    ci = [float(np.quantile(boots, 0.025)), float(np.quantile(boots, 0.975))]
    rules = {
        "S1_pass": all(r["ppo_mean_pos"] <= r["fixed1_mean_pos"] for r in report),
        "S2_diff_ppo_minus_history": float(d.mean()),
        "S2_ci": ci,
        "S2_pass": ci[1] < 0,
    }
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    out = {"spec": "18-rl-strategy", "commit": sha, "inside_simulator_only": True, "rules": rules, "races": report}
    (ROOT / "results" / "18-rl-strategy.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(rules, indent=2))


if __name__ == "__main__":
    main()
