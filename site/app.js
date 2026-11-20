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

fetch("data/undercut-model.json").then((r) => r.json()).then((m) => {
  P = m.params;
  $("nEvents").textContent = m.trained_on.events.toLocaleString("en");
  for (const id of ["gap", "ageA", "ageB", "left"]) $(id).addEventListener("input", update);
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", update);
  let t; addEventListener("resize", () => { clearTimeout(t); t = setTimeout(update, 120); });
  update();
});
