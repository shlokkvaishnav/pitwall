// The live replay on the site is a development race, and each frame uses only laps up to its own.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const d = JSON.parse(readFileSync(new URL("../../site/data/live-replay.json", import.meta.url)));

test("the replay is a development race with one frame per lap", () => {
  assert.ok(d.race.startsWith("2026") && !/Mexico|Brazil|Vegas|Qatar|Abu Dhabi/.test(d.race));
  d.frames.forEach((f, i) => assert.equal(f.lap, i + 1));
  assert.equal(d.frames.length, d.laps - 1);
});

test("windows lie after the lap they were computed on, chances are probabilities", () => {
  for (const f of d.frames) {
    if (f.window) assert.ok(f.window[0] > f.lap && f.window[0] <= f.window[1] && f.window[1] < d.laps);
    if (f.undercut !== undefined) assert.ok(f.undercut >= 0 && f.undercut <= 1);
    for (const r of f.forecast) assert.ok(r.podium >= 0 && r.podium <= 1);
  }
  assert.ok(d.latency_ms.median > 0);
});
