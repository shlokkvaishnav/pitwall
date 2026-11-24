// "Lap by lap, as if live": the engine's odds after each lap of a past race.
// Data: data/live-replay.json (scripts/replay.py). Odds from the simulator, not advice.
const $ = (id) => document.getElementById(id);
const NS = "http://www.w3.org/2000/svg";
const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
let D = null, timer = null;

function el(tag, attrs = {}, parent) {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (parent) parent.appendChild(e);
  return e;
}
const text = (p, x, y, s, a = {}) => { const t = el("text", { x, y, ...a }, p); t.textContent = s; return t; };
const width = (svg) => Math.max(300, Math.round(svg.parentElement.getBoundingClientRect().width - 2 * parseFloat(getComputedStyle(svg.parentElement).paddingLeft)));
const pct = (p) => (p < 0.01 ? "<1%" : `${Math.round(p * 100)}%`);
const name = (d) => d.split("_").pop().replace(/^./, (c) => c.toUpperCase());

function frame() { return D.frames[Number($("liveLap").value) - 1]; }

function drawWindow(f) {
  const svg = $("liveWin"); svg.replaceChildren();
  const W = width(svg), H = 120, L = 14, R = 14, T = 26, B = 34, n = D.laps;
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  const x = (lap) => L + ((lap - 0.5) / n) * (W - L - R), mid = (T + H - B) / 2;
  el("line", { x1: x(1), x2: x(n), y1: mid, y2: mid, class: "axis" }, svg);
  el("rect", { x: x(1) - 2, y: T, width: x(f.lap) - x(1) + 4, height: H - T - B, fill: css("--rule"), opacity: 0.5, rx: 3 }, svg);
  if (f.window) {
    const [lo, hi] = f.window;
    el("rect", { x: x(lo) - 3, y: T + 6, width: x(hi) - x(lo) + 6, height: H - T - B - 12, rx: 4, fill: css("--accent-soft") }, svg);
    el("rect", { x: x(lo) - 3, y: T + 6, width: x(hi) - x(lo) + 6, height: H - T - B - 12, rx: 4, fill: "none", stroke: css("--accent"), "stroke-width": 1.5 }, svg);
  }
  for (const lap of D.real_stops) el("circle", { cx: x(lap), cy: mid, r: 4.5, fill: css("--ink") }, svg);
  el("line", { x1: x(f.lap), x2: x(f.lap), y1: T - 8, y2: H - B, stroke: css("--ink"), "stroke-width": 1.5 }, svg);
  const right = x(f.lap) > W - R - 60;
  text(svg, right ? x(f.lap) - 5 : x(f.lap) + 5, T - 10, `LAP ${f.lap}`, { class: "lbl", "text-anchor": right ? "end" : "start", fill: css("--ink") });
  const step = W < 520 ? 20 : 10;
  for (let v = step; v <= n; v += step) text(svg, x(v), H - B + 18, `${v}`, { class: "tick", "text-anchor": "middle" });
  text(svg, x(n / 2), H - 3, "lap", { class: "tick", "text-anchor": "middle" });
}

function drawPodium(f) {
  const svg = $("livePod"); svg.replaceChildren();
  const rows = f.forecast, W = width(svg), row = 24, T = 4, B = 4, L = Math.min(130, W * 0.34), R = 48, H = T + rows.length * row + B;
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  const x = (p) => L + p * (W - L - R);
  rows.forEach((r, i) => {
    const cy = T + i * row + row / 2, me = r.driver === D.car, c = css(me ? "--accent" : "--muted");
    text(svg, L - 10, cy + 4, name(r.driver), { class: "bar-lbl", "text-anchor": "end", "font-weight": me ? 700 : 400 });
    el("line", { x1: x(0), x2: x(1), y1: cy, y2: cy, class: "axis" }, svg);
    el("line", { x1: x(0), x2: x(r.podium), y1: cy, y2: cy, stroke: c, "stroke-width": 6, "stroke-linecap": "round" }, svg);
    text(svg, x(1) + 8, cy + 4, pct(r.podium), { class: "bar-val", fill: c });
  });
}

function draw() {
  if (!D) return;
  const f = frame();
  $("liveLapV").textContent = `${f.lap} of ${D.laps}`;
  $("livePos").textContent = f.position ? `P${f.position}` : "out";
  $("liveUc").textContent = f.undercut !== undefined ? `undercut on ${name(f.ahead)}: ${pct(f.undercut)}` : f.ahead ? `more than 3 s behind ${name(f.ahead)}` : "leading";
  drawWindow(f); drawPodium(f);
}

function play() {
  if (timer) { clearInterval(timer); timer = null; $("livePlay").textContent = "Replay"; return; }
  const s = $("liveLap"); if (Number(s.value) >= D.frames.length) s.value = 1;
  $("livePlay").textContent = "Pause";
  timer = setInterval(() => {
    if (Number(s.value) >= D.frames.length) { play(); return; }
    s.value = Number(s.value) + 1; draw();
  }, 220);
}

fetch("data/live-replay.json").then((r) => r.json()).then((d) => {
  D = d;
  const s = $("liveLap"); s.max = d.frames.length; s.value = 1;
  $("liveCar").textContent = `${name(d.car)}, started 5th`;
  $("liveMs").textContent = `${Math.round(d.latency_ms.median)} ms (median, one race, one car)`;
  s.addEventListener("input", draw);
  $("livePlay").addEventListener("click", play);
  draw();
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", draw);
  let t; addEventListener("resize", () => { clearTimeout(t); t = setTimeout(draw, 120); });
});
