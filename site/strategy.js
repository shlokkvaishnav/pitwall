// "One race, layer by layer": safety-car risk per lap, how hard passing is here, and the simulated pit window.
// Data: data/race-strategy.json (scripts/export_strategy.py). Odds from the models, not advice.
const $ = (id) => document.getElementById(id);
const NS = "http://www.w3.org/2000/svg";
const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
let D = null, hoverLap = null;

function el(tag, attrs = {}, parent) {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (parent) parent.appendChild(e);
  return e;
}
const text = (p, x, y, s, a = {}) => { const t = el("text", { x, y, ...a }, p); t.textContent = s; return t; };
const width = (svg) => Math.max(300, Math.round(svg.parentElement.getBoundingClientRect().width - 2 * parseFloat(getComputedStyle(svg.parentElement).paddingLeft)));
const pct = (p) => (p < 0.01 ? "<1%" : `${Math.round(p * 100)}%`);
const tickPct = (p) => `${Math.round(p * 100)}%`;
const KIND = { sc: "Safety car", vsc: "VSC", red: "Red flag" };

function lapAxis(svg, x, laps, W, H, B) {
  const step = W < 520 ? 20 : 10;
  for (let v = step; v <= laps; v += step) text(svg, x(v), H - B + 18, `${v}`, { class: "tick", "text-anchor": "middle" });
  text(svg, x(laps / 2), H - 3, "lap", { class: "tick", "text-anchor": "middle" });
}

function drawHazard() {
  const svg = $("hazard"); svg.replaceChildren();
  const W = width(svg), H = Math.round(Math.min(220, Math.max(170, W * 0.3))), L = 44, R = 12, T = 22, B = 34;
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  const n = D.laps, top = Math.max(0.05, Math.ceil(Math.max(...D.hazard) * 20) / 20);
  const x = (lap) => L + ((lap - 0.5) / n) * (W - L - R), y = (p) => T + (1 - p / top) * (H - T - B), bw = Math.max(1, (W - L - R) / n - 1);
  for (let v = 0; v <= top + 1e-9; v += top / 2) {
    el("line", { x1: L, x2: W - R, y1: y(v), y2: y(v), class: "axis" }, svg);
    text(svg, L - 8, y(v) + 4, tickPct(v), { class: "tick", "text-anchor": "end" });
  }
  D.hazard.forEach((p, i) => el("rect", { x: x(i + 1) - bw / 2, y: y(p), width: bw, height: y(0) - y(p), rx: Math.min(2, bw / 2), fill: css("--accent"), opacity: hoverLap === i + 1 ? 1 : 0.5 }, svg));
  for (const ev of D.real_neutral) {
    const px = x(ev.lap);
    el("line", { x1: px, x2: px, y1: T - 6, y2: H - B, stroke: css("--ink"), "stroke-width": 1.5, "stroke-dasharray": "3 3" }, svg);
    const right = px > W - R - 90;
    text(svg, right ? px - 5 : px + 5, T - 8, (KIND[ev.kind] || ev.kind).toUpperCase(), { class: "lbl", "text-anchor": right ? "end" : "start", fill: css("--ink") });
  }
  lapAxis(svg, x, n, W, H, B);
  svg.onpointermove = (ev) => {
    const b = svg.getBoundingClientRect(), vx = ((ev.clientX - b.left) / b.width) * W;
    const lap = Math.min(n, Math.max(1, Math.round(((vx - L) / (W - L - R)) * n + 0.5)));
    if (lap !== hoverLap) {
      hoverLap = lap; drawHazard();
      const real = D.real_neutral.find((e) => e.lap === lap);
      $("hzTip").textContent = `Lap ${lap}: ${pct(D.hazard[lap - 1])} chance a neutral period starts.${real ? ` One did: ${KIND[real.kind] || real.kind}.` : ""}`;
    }
  };
}

function drawPassing() {
  const svg = $("passing"); svg.replaceChildren();
  const rows = [...D.overtaking].sort((a, b) => b.p - a.p);
  const W = width(svg), row = 20, T = 6, B = 26, L = Math.min(150, W * 0.38), R = 44, H = T + rows.length * row + B;
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  const top = Math.ceil(Math.max(...rows.map((r) => r.p)) * 50) / 50; // a multiple of 2%
  const x = (p) => L + (p / top) * (W - L - R);
  for (let v = 0; v <= top + 1e-9; v += top / 2) {
    el("line", { x1: x(v), x2: x(v), y1: T, y2: H - B, class: "axis" }, svg);
    text(svg, x(v), H - B + 16, tickPct(v), { class: "tick", "text-anchor": "middle" });
  }
  rows.forEach((r, i) => {
    const cy = T + i * row + row / 2, c = css(r.this ? "--accent" : "--muted");
    text(svg, L - 10, cy + 4, r.circuit, { class: "bar-lbl", "text-anchor": "end", "font-weight": r.this ? 700 : 400 });
    el("line", { x1: x(0), x2: x(r.p), y1: cy, y2: cy, stroke: c, "stroke-width": r.this ? 3 : 1.5, opacity: r.this ? 1 : 0.6 }, svg);
    el("circle", { cx: x(r.p), cy, r: r.this ? 5.5 : 3.5, fill: c }, svg);
    if (r.this) text(svg, x(r.p) + 10, cy + 4, pct(r.p), { class: "bar-val", fill: css("--accent") });
  });
}

function drawWindow() {
  const svg = $("window"); svg.replaceChildren();
  const w = D.window, W = width(svg), H = Math.round(Math.min(300, Math.max(220, W * 0.42))), L = 44, R = 14, T = 40, B = 34;
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  const lo = Math.floor(Math.min(...w.map((r) => r.mean))), hi = Math.ceil(Math.max(...w.map((r) => r.mean)));
  const x = (lap) => L + ((lap - 0.5) / D.laps) * (W - L - R), y = (p) => T + ((p - lo) / (hi - lo || 1)) * (H - T - B); // better finish is higher
  const step = hi - lo > 6 ? 2 : 1;
  for (let v = lo; v <= hi; v += step) {
    el("line", { x1: L, x2: W - R, y1: y(v), y2: y(v), class: "axis" }, svg);
    text(svg, L - 8, y(v) + 4, `P${v}`, { class: "tick", "text-anchor": "end" });
  }
  let lastX = -Infinity, row = 0;
  for (const lap of D.ego.real_stops) {
    const px = x(lap);
    row = px - lastX < 110 ? 1 - row : 0; lastX = px;
    el("line", { x1: px, x2: px, y1: T - 8, y2: H - B, stroke: css("--ink"), "stroke-width": 1.5, "stroke-dasharray": "3 3" }, svg);
    const right = px > W - R - 120;
    const flag = D.real_neutral.find((e) => Math.abs(e.lap - lap) <= 1);
    text(svg, right ? px - 5 : px + 5, T - 26 + row * 13, flag ? `STOP, ${(KIND[flag.kind] || flag.kind).toUpperCase()}` : "REAL STOP", { class: "lbl", "text-anchor": right ? "end" : "start", fill: css("--ink") });
  }
  el("path", { d: "M" + w.map((r) => `${x(r.lap).toFixed(1)},${y(r.mean).toFixed(1)}`).join("L"), fill: "none", stroke: css("--accent"), "stroke-width": 2.4, "stroke-linejoin": "round" }, svg);
  const best = w.reduce((a, r) => (r.mean < a.mean ? r : a));
  el("circle", { cx: x(best.lap), cy: y(best.mean), r: 5, fill: css("--accent") }, svg);
  lapAxis(svg, x, D.laps, W, H, B);
  const show = (r) => { $("winTip").textContent = `Stop on lap ${r.lap}: average finish P${r.mean.toFixed(1)}, top 5 in ${pct(r.top5)} of ${D.runs} simulated races.`; };
  show(best);
  svg.onpointermove = (ev) => {
    const b = svg.getBoundingClientRect(), vx = ((ev.clientX - b.left) / b.width) * W;
    const lap = Math.round(((vx - L) / (W - L - R)) * D.laps + 0.5);
    show(w.reduce((a, r) => (Math.abs(r.lap - lap) < Math.abs(a.lap - lap) ? r : a)));
  };
}

function drawAll() { if (D) { drawHazard(); drawPassing(); drawWindow(); } }

function loadFailed(id) {
  const s = document.getElementById(id); if (!s) return;
  const p = document.createElement("p"); p.className = "tip"; p.setAttribute("role", "alert");
  p.textContent = "This chart could not load its data. Reload the page to try again.";
  s.closest("section").querySelector(".panel").prepend(p);
}

fetch("data/race-strategy.json").then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); }).then((d) => {
  D = d;
  $("anyNeutral").textContent = pct(d.any_neutral);
  $("egoName").textContent = d.ego.driver.charAt(0).toUpperCase() + d.ego.driver.slice(1);
  drawAll();
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", drawAll);
  let t; addEventListener("resize", () => { clearTimeout(t); t = setTimeout(drawAll, 120); });
}).catch(() => loadFailed("hazard"));
