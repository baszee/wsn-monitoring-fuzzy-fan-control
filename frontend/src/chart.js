import { NODE_PALETTE } from "/src/theme.js?v=20261111-3";
import { fmtNumber, fmtClock } from "/src/shared.js?v=20261111-3";

export const PALETTE = NODE_PALETTE;
const L = 46, R = 16, T = 12, B = 30;
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[c]));

export function thin(pts, max = 300) {
  if (pts.length <= max) return pts;
  const s = Math.ceil(pts.length / max);
  return pts.filter((_, i) => i % s === 0 || i === pts.length - 1);
}

function segments(pts) {
  const out = [];
  let cur = [];
  for (const p of pts) {
    if (p.v == null || !Number.isFinite(Number(p.v))) { if (cur.length) out.push(cur); cur = []; }
    else cur.push({ t: p.t, v: Number(p.v) });
  }
  if (cur.length) out.push(cur);
  return out;
}

export function legendHtml(items) {
  return items.map((s) => `<span><i class="dot" style="color:${s.color}"></i>${esc(s.name)}</span>`).join("");
}

/** series: [{name,color,width,step,pts:[{t(ms),v}]}]. Mengembalikan item legenda, atau null bila kosong. */
export function drawChart(wrap, { series, t0, t1, fixed, floor, dec = 1, label = "" }) {
  const segs = series.map((s) => ({ ...s, segs: segments(s.pts) }));
  const values = segs.flatMap((s) => s.segs.flat().map((p) => p.v));
  if (!values.length) return null;

  const cs = getComputedStyle(wrap);
  const W = Math.max(320, Math.round(wrap.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight)) || 760);
  const H = Math.max(170, Math.round(wrap.clientHeight - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom)) || 230);
  const PW = W - L - R, PH = H - T - B;

  let y0, y1;
  if (fixed) [y0, y1] = fixed;
  else {
    const mn = Math.min(...values), mx = Math.max(...values);
    const span = mx - mn || Math.max(1, Math.abs(mx) * 0.1);
    y0 = mn - span * 0.15; y1 = mx + span * 0.15;
    if (floor != null) y0 = Math.max(floor, y0);
  }
  const X = (t) => L + ((Math.max(t0, t) - t0) / (t1 - t0)) * PW;
  const Y = (v) => T + PH - ((v - y0) / (y1 - y0)) * PH;

  const grid = [0, 1, 2, 3, 4].map((i) => {
    const r = i / 4, y = T + PH * r;
    return `<line class="chart-grid" x1="${L}" y1="${y}" x2="${W - RT_()}" y2="${y}"/><text class="chart-axis-text" x="${L - 8}" y="${y + 3}" text-anchor="end">${fmtNumber(y1 - (y1 - y0) * r, dec)}</text>`;
  }).join("");
  const longRange = t1 - t0 >= 20 * 3600e3;
  const tickLabel = (t) => longRange ? `${new Date(t).toLocaleDateString("id-ID", { weekday: "short" })} ${fmtClock(t, false)}` : fmtClock(t, false);
  const xl = [0, 1, 2, 3].map((i) => {
    const t = t0 + ((t1 - t0) * i) / 3;
    return `<text class="chart-axis-text" x="${X(t)}" y="${H - 8}" text-anchor="${i === 0 ? "start" : i === 3 ? "end" : "middle"}">${tickLabel(t)}</text>`;
  }).join("");
  const lines = segs.map((s) => s.segs.map((seg) => {
    if (seg.length === 1) return `<circle cx="${X(seg[0].t).toFixed(1)}" cy="${Y(seg[0].v).toFixed(1)}" r="3" fill="${s.color}"/>`;
    const d = seg.map((p, i) => {
      const x = X(p.t).toFixed(1), y = Y(p.v).toFixed(1);
      return i === 0 ? `M${x} ${y}` : s.step ? ` H${x} V${y}` : ` L${x} ${y}`;
    }).join("");
    return `<path d="${d}" fill="none" stroke="${s.color}" stroke-width="${s.width ?? 1.8}" stroke-linejoin="round" stroke-linecap="round"/>`;
  }).join("")).join("");

  wrap.style.position = "relative";
  wrap.innerHTML = `<svg viewBox="0 0 ${W} ${H}" style="width:100%;height:100%;display:block" role="img" aria-label="Grafik ${esc(label)}">${grid}${xl}${lines}<line id="guide" x1="0" y1="${T}" x2="0" y2="${T + PH}" stroke="#94a3b8" stroke-dasharray="3 3" style="display:none"/></svg><div class="chart-tip"></div>`;

  const svg = wrap.querySelector("svg"), guide = svg.querySelector("#guide"), tip = wrap.querySelector(".chart-tip");
  const hide = () => { tip.style.display = "none"; guide.style.display = "none"; };
  svg.addEventListener("mouseleave", hide);
  svg.addEventListener("mousemove", (e) => {
    const r = svg.getBoundingClientRect();
    const x = ((e.clientX - r.left) / r.width) * W;
    if (x < L || x > W - R) return hide();
    const t = t0 + ((x - L) / PW) * (t1 - t0);
    const rows = segs.map((s) => {
      let best = null;
      for (const p of s.segs.flat()) {
        if (s.step) { if (p.t <= t) best = p; }
        else if (!best || Math.abs(p.t - t) < Math.abs(best.t - t)) best = p;
      }
      return best ? `<div><i class="dot" style="color:${s.color}"></i> ${esc(s.name)}: <b>${fmtNumber(best.v, dec)}</b></div>` : "";
    }).join("");
    guide.setAttribute("x1", x); guide.setAttribute("x2", x); guide.style.display = "";
    tip.innerHTML = `<div class="tip-time">${fmtClock(t)}</div>${rows}`;
    tip.style.display = "block";
    const wr = wrap.getBoundingClientRect();
    tip.style.left = `${Math.min(e.clientX - wr.left + 14, wr.width - 150)}px`;
  });

  return segs.map((s) => ({ name: s.name, color: s.color }));
}
function RT_() { return R; }
