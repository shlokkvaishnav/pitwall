// The lap replay on the site is a development race (spec 12) and its rows are consistent.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const d = JSON.parse(readFileSync(new URL("../../site/data/lap-replay.json", import.meta.url)));

test("the replay is a development race, not a locked one", () => {
  assert.equal(d.round, 12); // 2026 rounds 13 to 18 are the locked holdout (spec 11)
  assert.ok(d.round <= 12);
});

test("each lap has the forecast inside its range, in lap order", () => {
  assert.equal(d.drivers.length, 3);
  for (const drv of d.drivers) {
    assert.ok(drv.laps.length > 20);
    drv.laps.forEach(([lap, actual, fc, lo, hi], i) => {
      assert.ok(lo <= fc && fc <= hi, `${drv.code} lap ${lap}`);
      assert.ok(actual > 0);
      if (i) assert.ok(lap > drv.laps[i - 1][0]);
    });
  }
});
