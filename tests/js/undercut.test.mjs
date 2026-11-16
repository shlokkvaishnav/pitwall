// The browser model must give the same probabilities as scikit-learn (the test vectors in the JSON).
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { predict } from "../../site/undercut.js";

const model = JSON.parse(readFileSync(new URL("../../site/data/undercut-model.json", import.meta.url)));

test("browser model equals the Python model on the test vectors", () => {
  assert.ok(model.test_vectors.length >= 20);
  for (const v of model.test_vectors) {
    const p = predict(model.params, v.gap_s, v.age_a, v.age_b, v.laps_left);
    assert.ok(Math.abs(p - v.p) < 1e-5, `p=${p} python=${v.p}`);
  }
});

test("a larger gap makes the undercut less probable", () => {
  assert.ok(predict(model.params, 0.5, 15, 25, 30) > predict(model.params, 2.5, 15, 25, 30));
});
