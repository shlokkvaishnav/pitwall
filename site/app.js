import { predict } from "./undercut.js";

const $ = (id) => document.getElementById(id);
const NS = "http://www.w3.org/2000/svg";
const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
let P; // model parameters

function el(tag, attrs = {}, parent) {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (parent) parent.appendChild(e);
  return e;
}
const text = (parent, x, y, s, attrs = {}) => { const t = el("text", { x, y, ...attrs }, parent); t.textContent = s; return t; };

// Charts are drawn at their real width, so that the text keeps its size on a phone.
const width = (svg) => Math.max(300, Math.round(svg.parentElement.getBoundingClientRect().width - 2 * parseFloat(getComputedStyle(svg.parentElement).paddingLeft)));

function hexToRgb(h) {
  const m = h.replace("#", "");
  const n = parseInt(m.length === 3 ? m.split("").map((c) => c + c).join("") : m, 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}
function mix(a, b, t) { return `rgb(${a.map((v, i) => Math.round(v + (b[i] - v) * t)).join(",")})`; }
function ramp(p) {
  // blue (the undercut usually failed) -> paper -> red (it usually worked), centred on 50%
  const cool = hexToRgb(css("--cool")), mid = hexToRgb(css("--chip")), hot = hexToRgb(css("--accent"));
  return p < 0.5 ? mix(cool, mid, p / 0.5) : mix(mid, hot, (p - 0.5) / 0.5);
}

const state = () => ({
  gap: Number($("gap").value), ageA: Number($("ageA").value),
  ageB: Number($("ageB").value), left: Number($("left").value),
});
const chance = (s) => predict(P, s.gap, s.ageA, s.ageB, s.left);

function verdict(p) {
  if (p >= 0.65) return ["Likely works", css("--accent")];
  if (p >= 0.5) return ["Leans your way", css("--accent")];
  if (p >= 0.35) return ["Coin flip", css("--muted")];
  return ["Unlikely", css("--cool")];
}

function drawGauge(p) {
  $("pct").textContent = `${Math.round(p * 100)}%`;
  $("arcFill").setAttribute("stroke-dasharray", `${(p * 100).toFixed(1)} 100`);
  const a = Math.PI * (1 - p); // the arc: centre (160, 150), radius 130, from the left end (p = 0) to the right end
  $("knob").setAttribute("cx", (160 + 130 * Math.cos(a)).toFixed(1));
  $("knob").setAttribute("cy", (150 - 130 * Math.sin(a)).toFixed(1));
  const [w, c] = verdict(p);
  $("word").textContent = w;
  $("word").setAttribute("fill", c);
}

function drawStrip(s) {
  const xB = 230, xA = xB - 18 - s.gap * 50;
  $("carB").style.transform = `translateX(${xB}px)`;
  $("carA").style.transform = `translateX(${xA}px)`;
  $("gapLine").setAttribute("x1", xA + 15); $("gapLine").setAttribute("x2", xB - 15);
  $("gapTxt").setAttribute("x", (xA + xB) / 2); $("gapTxt").textContent = `${s.gap.toFixed(1)} s`;
}

function drawCurve(s) {
  const svg = $("curve"); svg.replaceChildren();
  const W = 320, H = 130, L = 30, R = 6, T = 8, B = 22;
  const x = (g) => L + ((g - 0.1) / 2.9) * (W - L - R), y = (p) => T + (1 - p) * (H - T - B);
  for (const p of [0, 0.5, 1]) {
    el("line", { x1: L, x2: W - R, y1: y(p), y2: y(p), class: "axis" }, svg);
    text(svg, L - 6, y(p) + 4, `${p * 100}%`, { class: "tick", "text-anchor": "end" });
  }
  for (const g of [0.5, 1, 1.5, 2, 2.5, 3]) text(svg, x(g), H - 5, `${g} s`, { class: "tick", "text-anchor": "middle" });
  let d = "", area = `M${x(0.1)},${y(0)}`;
  for (let i = 0; i <= 58; i++) {
    const g = 0.1 + (i / 58) * 2.9, py = y(chance({ ...s, gap: g }));
    d += `${i ? "L" : "M"}${x(g).toFixed(1)},${py.toFixed(1)}`; area += `L${x(g).toFixed(1)},${py.toFixed(1)}`;
  }
  area += `L${x(3)},${y(0)}Z`;
  el("path", { d: area, fill: css("--accent-soft"), opacity: 0.6 }, svg);
  el("path", { d, fill: "none", stroke: css("--accent"), "stroke-width": 2.4, "stroke-linejoin": "round" }, svg);
  el("circle", { cx: x(s.gap), cy: y(chance(s)), r: 5.5, fill: css("--accent"), stroke: css("--card"), "stroke-width": 2 }, svg);
}

function drawMap(s) {
  const svg = $("map"); svg.replaceChildren();
  const W = width(svg), H = Math.round(Math.min(330, Math.max(240, W * 0.55))), L = 50, R = 62, T = 10, B = 40;
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  const gaps = 30, advs = 41, aMin = -15, aMax = 25; // advantage = rival tyre age - your tyre age
  const cw = (W - L - R) / gaps, ch = (H - T - B) / advs;
  const ageA = 20;
  for (let i = 0; i < gaps; i++) for (let j = 0; j < advs; j++) {
    const g = 0.1 + (i + 0.5) * (2.9 / gaps), adv = aMax - j;
    const p = predict(P, g, ageA, ageA + adv, s.left);
    el("rect", { class: "cell", x: L + i * cw, y: T + j * ch, width: cw + 0.6, height: ch + 0.6, fill: ramp(p) }, svg);
  }
  // 50% line
  let d = "";
  for (let i = 0; i <= gaps; i++) {
    const g = 0.1 + (i / gaps) * 2.9;
    let lo = aMin, hi = aMax; // find advantage where p = 0.5 (p rises with advantage)
    for (let k = 0; k < 30; k++) { const m = (lo + hi) / 2; (predict(P, g, ageA, ageA + m, s.left) < 0.5 ? (lo = m) : (hi = m)); }
    const yy = T + (aMax - (lo + hi) / 2) * ch;
    if (yy >= T && yy <= H - B) d += `${d ? "L" : "M"}${(L + i * cw).toFixed(1)},${yy.toFixed(1)}`;
  }
  if (d) el("path", { d, fill: "none", stroke: css("--ink"), "stroke-width": 1.4, "stroke-dasharray": "5 4" }, svg);
  for (const g of [0.5, 1, 1.5, 2, 2.5, 3]) text(svg, L + ((g - 0.1) / 2.9) * (W - L - R), H - B + 18, `${g} s`, { class: "tick", "text-anchor": "middle" });
  text(svg, L + (W - L - R) / 2, H - 4, "gap to the car ahead", { class: "tick", "text-anchor": "middle" });
  for (const a of [-10, 0, 10, 20]) text(svg, L - 8, T + (aMax - a + 0.5) * ch + 4, `${a > 0 ? "+" : ""}${a}`, { class: "tick", "text-anchor": "end" });
  const yl = text(svg, 14, T + (H - T - B) / 2, "rival's tyres older by (laps)", { class: "tick", "text-anchor": "middle" });
  yl.setAttribute("transform", `rotate(-90 14 ${T + (H - T - B) / 2})`);
  // your point
  const adv = Math.max(aMin, Math.min(aMax, s.ageB - s.ageA));
  const px = L + ((s.gap - 0.1) / 2.9) * (W - L - R), py = T + (aMax - adv + 0.5) * ch;
  el("circle", { cx: px, cy: py, r: 8, fill: "none", stroke: css("--ink"), "stroke-width": 2.5 }, svg);
  el("circle", { cx: px, cy: py, r: 2.5, fill: css("--ink") }, svg);
  // legend
  const lx = W - R + 22, lh = H - T - B;
  for (let k = 0; k < 40; k++) el("rect", { x: lx, y: T + (k / 40) * lh, width: 12, height: lh / 40 + 0.6, fill: ramp(1 - k / 40) }, svg);
  for (const p of [1, 0.5, 0]) text(svg, lx + 18, T + (1 - p) * lh + 4, `${p * 100}%`, { class: "tick" });
  $("mapLaps").textContent = s.left;
}

function drawBars(s) {
  const svg = $("bars"); svg.replaceChildren();
  const base = chance(s);
  const rows = [
    ["Gap 1 s smaller", { ...s, gap: Math.max(0.1, s.gap - 1) }],
    ["Gap 1 s larger", { ...s, gap: Math.min(3, s.gap + 1) }],
    ["Rival's tyres 10 laps older", { ...s, ageB: s.ageB + 10 }],
    ["Your tyres 10 laps older", { ...s, ageA: s.ageA + 10 }],
    ["10 laps fewer to go", { ...s, left: Math.max(3, s.left - 10) }],
  ];
  const W = width(svg), narrow = W < 540; // on a phone, the label goes above its bar
  const L = narrow ? 8 : Math.round(Math.min(230, W * 0.42)), R = narrow ? 8 : 58, row = narrow ? 56 : 42;
  const mid = L + (W - L - R) / 2, half = (W - L - R) / 2 - (narrow ? 62 : 0), maxPts = 40;
  svg.setAttribute("viewBox", `0 0 ${W} ${rows.length * row + 34}`);
  el("line", { x1: mid, x2: mid, y1: 4, y2: rows.length * row + 6, stroke: css("--rule"), "stroke-width": 1.5 }, svg);
  rows.forEach(([label, alt], k) => {
    const d = (chance(alt) - base) * 100, y = 10 + k * row, by = narrow ? y + 18 : y + 4;
    if (narrow) text(svg, L, y + 8, label, { class: "bar-lbl" });
    else text(svg, L - 14, y + 17, label, { class: "bar-lbl", "text-anchor": "end" });
    const w = (Math.min(Math.abs(d), maxPts) / maxPts) * half;
    const color = d >= 0 ? css("--accent") : css("--cool");
    el("rect", { x: d >= 0 ? mid : mid - w, y: by, width: Math.max(w, 1.5), height: 20, rx: 5, fill: color }, svg);
    text(svg, d >= 0 ? mid + w + 8 : mid - w - 8, by + 14, `${d >= 0 ? "+" : "−"}${Math.abs(d).toFixed(0)} pts`,
      { class: "bar-val", fill: color, "text-anchor": d >= 0 ? "start" : "end" });
  });
  text(svg, mid, rows.length * row + 24, `your chance now: ${Math.round(base * 100)}%`, { class: "tick", "text-anchor": "middle" });
}

function update() {
  const s = state();
  $("gapV").textContent = `${s.gap.toFixed(1)} s`;
  $("ageAV").textContent = `${s.ageA} laps`;
  $("ageBV").textContent = `${s.ageB} laps`;
  $("leftV").textContent = `${s.left}`;
  drawGauge(chance(s)); drawStrip(s); drawCurve(s); drawMap(s); drawBars(s);
}

// Next-lap forecast replay (docs/specs/12-lap-intervals.md, section 5): real lap, forecast and its 80% range.
const LAP = { data: null, driver: 0, shown: Infinity, timer: null, hover: null };
const fmt = (v) => `${v.toFixed(3)} s`;

function lapRows() {
  const [lap, actual, fc, lo, hi, stint] = [0, 1, 2, 3, 4, 5];
  return LAP.data.drivers[LAP.driver].laps.map((r) => ({ lap: r[lap], y: r[actual], f: r[fc], lo: r[lo], hi: r[hi], stint: r[stint] }));
}

function lapDomain(rows) {
  // The axis fits the normal racing laps. Laps far outside it (traffic, a slow restart) are drawn at the edge.
  const ys = rows.map((r) => r.y).sort((a, b) => a - b), med = ys[Math.floor(ys.length / 2)];
  const core = rows.flatMap((r) => [r.y, r.lo, r.hi]).filter((v) => v > med - 5 && v < med + 6);
  return [Math.floor((Math.min(...core) - 0.3) * 2) / 2, Math.ceil((Math.max(...core) + 0.3) * 2) / 2];
}

function drawLaps() {
  const svg = $("laps"); svg.replaceChildren();
  if (!LAP.data) return;
  const all = lapRows(), rows = all.filter((r, i) => i < LAP.shown);
  const W = width(svg), H = Math.round(Math.min(340, Math.max(250, W * 0.5))), L = 52, R = 12, T = 14, B = 34;
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  const [y0, y1] = lapDomain(all), x0 = all[0].lap - 1, x1 = all[all.length - 1].lap + 1;
  const x = (v) => L + ((v - x0) / (x1 - x0)) * (W - L - R), y = (v) => T + (1 - (v - y0) / (y1 - y0)) * (H - T - B);
  const step = y1 - y0 > 6 ? 2 : y1 - y0 > 3 ? 1 : 0.5;
  for (let v = Math.ceil(y0 / step) * step; v <= y1 + 1e-9; v += step) {
    el("line", { x1: L, x2: W - R, y1: y(v), y2: y(v), class: "axis" }, svg);
    text(svg, L - 8, y(v) + 4, `${v.toFixed(step < 1 ? 1 : 0)} s`, { class: "tick", "text-anchor": "end" });
  }
  const xstep = W < 520 ? 20 : 10;
  for (let v = Math.ceil(x0 / xstep) * xstep; v <= x1; v += xstep) text(svg, x(v), H - B + 18, `${v}`, { class: "tick", "text-anchor": "middle" });
  text(svg, L + (W - L - R) / 2, H - 3, "lap", { class: "tick", "text-anchor": "middle" });
  // pit stops: a faint line where the stint changes
  all.forEach((r, i) => { if (i && r.stint !== all[i - 1].stint) {
    const px = x((r.lap + all[i - 1].lap) / 2);
    el("line", { x1: px, x2: px, y1: T, y2: H - B, stroke: css("--rule"), "stroke-width": 1.5 }, svg);
    text(svg, px + 4, T + 9, "PIT", { class: "lbl" });
  } });
  const clip = el("clipPath", { id: "lapClip" }, el("defs", {}, svg));
  el("rect", { x: L, y: T, width: W - L - R, height: H - T - B }, clip);
  const g = el("g", { "clip-path": "url(#lapClip)" }, svg);
  // the band and the forecast line, broken where laps are missing
  const runs = [];
  rows.forEach((r, i) => (i && r.lap === rows[i - 1].lap + 1 ? runs[runs.length - 1].push(r) : runs.push([r])));
  for (const run of runs) {
    const top = run.map((r) => `${x(r.lap - (run.length === 1 ? 0.35 : 0)).toFixed(1)},${y(r.hi).toFixed(1)}`);
    const bot = run.map((r) => `${x(r.lap + (run.length === 1 ? 0.35 : 0)).toFixed(1)},${y(r.lo).toFixed(1)}`).reverse();
    if (run.length === 1) { top.push(`${x(run[0].lap + 0.35).toFixed(1)},${y(run[0].hi).toFixed(1)}`); bot.push(`${x(run[0].lap - 0.35).toFixed(1)},${y(run[0].lo).toFixed(1)}`); }
    el("path", { d: `M${top.join("L")}L${bot.join("L")}Z`, fill: css("--accent-soft") }, g);
    el("path", { d: "M" + run.map((r) => `${x(r.lap).toFixed(1)},${y(r.f).toFixed(1)}`).join("L"), fill: "none", stroke: css("--accent"), "stroke-width": 2, "stroke-linejoin": "round" }, g);
  }
  // the real laps; misses are hollow, laps off the axis are triangles at the edge
  let hits = 0;
  for (const r of rows) {
    const inside = r.y >= r.lo && r.y <= r.hi; hits += inside;
    const px = x(r.lap);
    if (r.y > y1 || r.y < y0) {
      const e = r.y > y1 ? T + 2 : H - B - 2, s = r.y > y1 ? 1 : -1;
      el("path", { d: `M${px - 5},${e + 8 * s}L${px + 5},${e + 8 * s}L${px},${e}Z`, fill: css("--cool") }, svg);
    } else if (inside) el("circle", { cx: px, cy: y(r.y), r: 3.2, fill: css("--ink") }, svg);
    else el("circle", { cx: px, cy: y(r.y), r: 3.4, fill: css("--card"), stroke: css("--cool"), "stroke-width": 2 }, svg);
  }
  $("lapHits").innerHTML = `${hits} <span>of ${rows.length} laps in the range</span>`;
  if (LAP.hover != null) {
    const r = all.find((q) => q.lap === LAP.hover);
    if (r && rows.includes(r)) {
      el("line", { x1: x(r.lap), x2: x(r.lap), y1: T, y2: H - B, class: "guide" }, svg);
      $("lapTip").textContent = `Lap ${r.lap}: real ${fmt(r.y)}, forecast ${fmt(r.f)}, range ${r.lo.toFixed(1)} to ${r.hi.toFixed(1)} s.`;
    }
  }
  svg.onpointermove = (ev) => {
    const b = svg.getBoundingClientRect(), vx = ((ev.clientX - b.left) / b.width) * W;
    const lap = Math.round(x0 + ((vx - L) / (W - L - R)) * (x1 - x0));
    const near = all.reduce((a, q) => (Math.abs(q.lap - lap) < Math.abs(a.lap - lap) ? q : a));
    if (near.lap !== LAP.hover) { LAP.hover = near.lap; drawLaps(); }
  };
}

function lapDrivers() {
  const box = $("lapDrivers"); box.replaceChildren();
  LAP.data.drivers.forEach((d, i) => {
    const b = document.createElement("button");
    b.type = "button"; b.textContent = `P${d.position} ${d.code}`; b.setAttribute("aria-pressed", String(i === LAP.driver));
    b.onclick = () => { LAP.driver = i; LAP.hover = null; stopReplay(); lapDrivers(); drawLaps(); };
    box.appendChild(b);
  });
}

function stopReplay() { clearInterval(LAP.timer); LAP.timer = null; LAP.shown = Infinity; $("lapPlay").textContent = "Replay"; }
function replay() {
  if (LAP.timer) { stopReplay(); drawLaps(); return; }
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) { drawLaps(); return; }
  LAP.shown = 0; LAP.hover = null; $("lapPlay").textContent = "Stop";
  const n = lapRows().length;
  LAP.timer = setInterval(() => { LAP.shown += 1; drawLaps(); if (LAP.shown >= n) stopReplay(); }, 70);
}

fetch("data/lap-replay.json").then((r) => r.json()).then((d) => {
  LAP.data = d;
  $("lapRace").textContent = d.race;
  $("lapPlay").addEventListener("click", replay);
  lapDrivers(); drawLaps();
});

fetch("data/undercut-model.json").then((r) => r.json()).then((m) => {
  P = m.params;
  $("nEvents").textContent = m.trained_on.events.toLocaleString("en");
  for (const id of ["gap", "ageA", "ageB", "left"]) $(id).addEventListener("input", update);
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { update(); drawLaps(); });
  let t; addEventListener("resize", () => { clearTimeout(t); t = setTimeout(() => { update(); drawLaps(); }, 120); });
  update();
});
