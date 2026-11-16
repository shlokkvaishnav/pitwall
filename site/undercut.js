// Undercut success model (spec 10) in the browser. The same maths as scikit-learn:
// p = sigmoid(intercept + sum(coef_i * (x_i - mean_i) / scale_i)), x = [gap, ageB - ageA, ln(lapsLeft)].

export function features(gapS, ageA, ageB, lapsLeft) {
  return [gapS, ageB - ageA, Math.log(Math.max(lapsLeft, 1))];
}

export function predict(params, gapS, ageA, ageB, lapsLeft) {
  const x = features(gapS, ageA, ageB, lapsLeft);
  let z = params.intercept;
  for (let i = 0; i < x.length; i++) z += (params.coef[i] * (x[i] - params.mean[i])) / params.scale[i];
  return 1 / (1 + Math.exp(-z));
}

// ---- page code (runs only in a browser) ----
if (typeof document !== "undefined") {
  const $ = (id) => document.getElementById(id);
  const svgNS = "http://www.w3.org/2000/svg";
  let model;

  function el(tag, attrs, parent) {
    const e = document.createElementNS(svgNS, tag);
    for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
    parent.appendChild(e);
    return e;
  }

  function drawCurve(ageA, ageB, left, gap) {
    const svg = $("curve");
    svg.replaceChildren();
    const W = 320, H = 160, L = 34, B = 24, T = 8, R = 8;
    const x = (g) => L + (g / 3) * (W - L - R);
    const y = (p) => T + (1 - p) * (H - T - B);
    for (const p of [0, 0.5, 1]) {
      el("line", { x1: L, x2: W - R, y1: y(p), y2: y(p), class: "grid" }, svg);
      el("text", { x: L - 6, y: y(p) + 4, class: "tick", "text-anchor": "end" }, svg).textContent = `${p * 100}%`;
    }
    for (const g of [0, 1, 2, 3]) {
      el("text", { x: x(g), y: H - 6, class: "tick", "text-anchor": "middle" }, svg).textContent = `${g} s`;
    }
    let d = "";
    for (let i = 0; i <= 60; i++) {
      const g = (i / 60) * 3;
      d += `${i ? "L" : "M"}${x(g).toFixed(1)},${y(predict(model.params, g, ageA, ageB, left)).toFixed(1)}`;
    }
    el("path", { d, class: "line" }, svg);
    const p = predict(model.params, gap, ageA, ageB, left);
    el("circle", { cx: x(gap), cy: y(p), r: 4.5, class: "dot" }, svg);
  }

  function drawCalibration() {
    const svg = $("calib");
    const W = 320, H = 160, L = 34, B = 24, T = 8, R = 8;
    const x = (p) => L + p * (W - L - R);
    const y = (p) => T + (1 - p) * (H - T - B);
    el("line", { x1: x(0), y1: y(0), x2: x(1), y2: y(1), class: "diag" }, svg);
    for (const p of [0, 0.5, 1]) {
      el("text", { x: L - 6, y: y(p) + 4, class: "tick", "text-anchor": "end" }, svg).textContent = `${p * 100}%`;
      el("text", { x: x(p), y: H - 6, class: "tick", "text-anchor": "middle" }, svg).textContent = `${p * 100}%`;
    }
    for (const b of model.test.calibration) {
      if (b.mean_p === null) continue;
      const c = el("circle", { cx: x(b.mean_p), cy: y(b.freq), r: Math.max(3, Math.sqrt(b.n)), class: "dot soft" }, svg);
      el("title", {}, c).textContent = `${b.n} events: predicted ${(b.mean_p * 100).toFixed(0)}%, real ${(b.freq * 100).toFixed(0)}%`;
    }
  }

  function update() {
    const gap = Number($("gap").value), ageA = Number($("ageA").value);
    const ageB = Number($("ageB").value), left = Number($("left").value);
    $("gapV").textContent = `${gap.toFixed(1)} s`;
    $("ageAV").textContent = `${ageA} laps`;
    $("ageBV").textContent = `${ageB} laps`;
    $("leftV").textContent = `${left} laps`;
    const p = predict(model.params, gap, ageA, ageB, left);
    $("prob").textContent = `${(p * 100).toFixed(0)}%`;
    drawCurve(ageA, ageB, left, gap);
  }

  fetch("data/undercut-model.json")
    .then((r) => r.json())
    .then((m) => {
      model = m;
      $("bss").textContent = m.test.bss.toFixed(2);
      $("nTest").textContent = m.test.events;
      $("nTrain").textContent = m.trained_on.events;
      for (const id of ["gap", "ageA", "ageB", "left"]) $(id).addEventListener("input", update);
      drawCalibration();
      update();
    })
    .catch(() => {
      $("prob").textContent = "–";
      $("err").hidden = false;
    });
}
