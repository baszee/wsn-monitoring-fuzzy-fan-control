import { buildSidebar, apiFetch, showToast, fmtNumber } from "/src/shared.js?v=20261029-3";
import { icon } from "/src/icons.js";
import { createFan } from "/src/fan-canvas.js";

buildSidebar("ringkasan");

// ── Util ───────────────────────────────────────────────────────────────────
const $ = (s) => document.querySelector(s);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[c]));
const p2 = (n) => String(n).padStart(2, "0");

// SQLite mengirim waktu tanpa zona; anggap UTC supaya tidak bergeser.
function parseTs(v) {
  if (!v) return NaN;
  const s = String(v);
  return Date.parse(/(Z|[+-]\d{2}:?\d{2})$/.test(s) ? s : `${s}Z`);
}
function clock(ms, withSeconds = true) {
  if (!Number.isFinite(ms)) return "—";
  const d = new Date(ms);
  return `${p2(d.getHours())}:${p2(d.getMinutes())}${withSeconds ? `:${p2(d.getSeconds())}` : ""}`;
}
function ageText(sec) {
  if (sec == null) return "";
  if (sec < 60) return `${Math.round(sec)} dtk`;
  if (sec < 3600) return `${Math.floor(sec / 60)} mnt`;
  return `${Math.floor(sec / 3600)} jam`;
}
const classKey = (c) => (c === "Baik" ? "good" : c === "Perlu Perhatian" ? "attention" : c === "Buruk" ? "bad" : "");

// ── State ──────────────────────────────────────────────────────────────────
const state = { nodes: [], control: null, history: null, tab: "control", range: "1h", failed: false };
const fan = createFan($("#fan-canvas"));

// ── Status atas ────────────────────────────────────────────────────────────
function renderStatus() {
  const total = state.nodes.length;
  const valid = state.nodes.filter((n) => n.data_status === "Valid").length;
  const badge = $("#connection-badge");
  badge.classList.remove("offline", "warn");
  if (!total || valid === 0) badge.classList.add("offline");
  else if (valid < total) badge.classList.add("warn");
  badge.querySelector("span").textContent = total ? `${valid} dari ${total} node valid` : "Data tidak tersedia";

  const c = state.control;
  $("#zone-label").textContent = c?.zone_id ? `Kondisi ${c.zone_id}` : "Kondisi zona";
  $("#updated-at").textContent = !c ? "—"
    : !c.worker_alive ? "Pemroses data tidak berjalan"
    : `Diperbarui ${clock(parseTs(c.last_evaluated_at))}`;
}

// ── Kartu keputusan ────────────────────────────────────────────────────────
function renderDecision() {
  const c = state.control;
  const unavailable = !c || c.fan_command_status === "Kendali tidak tersedia" || !c.worker_alive;
  $("#decision-card").classList.toggle("unavailable", unavailable);

  const pill = $("#fan-status");
  pill.className = "status-pill";
  const note = $("#decision-note");

  if (unavailable) {
    pill.textContent = "Kendali tidak tersedia";
    pill.classList.add("unavailable");
    note.textContent = !c ? "Data kendali belum dapat dimuat."
      : !c.worker_alive ? "Pemroses data tidak berjalan."
      : `Tidak ada node dengan data valid dalam ${c.freshness_seconds} detik terakhir.`;
    fan.setTarget(0, true);
    $("#pwm-value").textContent = "—";
    $("#fact-uzona").textContent = "—";
    $("#fact-node").textContent = "—";
  } else {
    pill.textContent = c.fan_command_status;
    if (c.fan_command_status === "Mati") pill.classList.add("off");
    fan.setTarget(c.pwm_command_percent, false);
    $("#pwm-value").textContent = `${fmtNumber(c.pwm_command_percent, 0)}%`;
    note.textContent = c.hysteresis_held
      ? `PWM hasil hitung ${fmtNumber(c.candidate_pwm_percent, 1)}%, ditahan karena perubahan kecil.`
      : "";
    $("#fact-uzona").textContent = fmtNumber(c.zone_control_level, 1);
    $("#fact-node").textContent = c.determining_node_id ?? "Tidak ada";
  }
  $("#fact-mode").textContent = c?.control_mode === "manual" ? "Manual" : c ? "Otomatis" : "—";
  $("#fact-time").textContent = c?.created_at ? clock(parseTs(c.created_at)) : "—";
}

// ── Kartu node ─────────────────────────────────────────────────────────────
function tileHtml(n) {
  const ok = n.data_status === "Valid";
  const det = ok && n.is_determining_node;
  const href = `/dashboard/nodes/detail.html?node=${encodeURIComponent(n.node_id)}`;
  const reason = n.data_status === "Data lama" ? `Data lama, ${ageText(n.data_age_seconds)} yang lalu` : (n.data_status || "Tidak ada data");
  const u = Math.max(0, Math.min(100, Number(n.control_level) || 0));
  return `
    <a class="panel node-tile${ok ? "" : " inactive"}${det ? " determining" : ""}" href="${href}">
      <div class="tile-top">
        <span class="tile-id">${esc(n.node_id)}</span>
        ${det ? `<span class="tag-determining">${icon("target")} Penentu</span>` : ""}
      </div>
      <div class="tile-class ${ok ? classKey(n.condition_class) : ""}">${ok ? `<i class="dot"></i>${esc(n.condition_class ?? "Belum dinilai")}` : "Tidak dipakai"}</div>
      ${ok
        ? `<div class="tile-scores">
             <div><span>Skor kondisi (s)</span><strong>${fmtNumber(n.condition_score, 1)}</strong></div>
             <div><span>Tingkat kendali (u)</span><strong>${fmtNumber(n.control_level, 1)}</strong></div>
           </div>
           <div class="tile-bar" aria-hidden="true"><i style="width:${u}%"></i></div>`
        : `<p class="tile-reason">${esc(reason)}</p>`}
      <div class="tile-readings"><span>${fmtNumber(n.temperature, 1)} °C</span><span>${fmtNumber(n.humidity, 0)}% RH</span><span>Debu ${fmtNumber(n.dust_index, 2)}</span></div>
    </a>`;
}

function renderNodes() {
  const el = $("#node-board");
  if (state.failed) el.innerHTML = `<div class="board-empty">Data node tidak dapat dimuat.</div>`;
  else if (!state.nodes.length) el.innerHTML = `<div class="board-empty">Belum ada node terdaftar.</div>`;
  else el.innerHTML = state.nodes.map(tileHtml).join("");
}

// ── Grafik ─────────────────────────────────────────────────────────────────
const W = 760, H = 230, L = 46, RT = 16, T = 12, B = 30, PW = W - L - RT, PH = H - T - B;
const RANGE_MS = { "1h": 3600e3, "6h": 21600e3, "24h": 86400e3 };
const RANGE_TEXT = { "1h": "1 jam", "6h": "6 jam", "24h": "24 jam" };
const PALETTE = ["#2f7df0", "#13a8aa", "#e7a21a", "#8b5cf6"];
const ZONE_COLOR = "#10213c";
const TABS = {
  control:     { label: "Tingkat kendali", key: "control_level", fixed: [0, 100], dec: 0, note: "u zona = nilai u tertinggi dari semua node" },
  temperature: { label: "Suhu (°C)",       key: "temperature",  dec: 1, note: "Data sensor aktual, tanpa nilai perkiraan" },
  humidity:    { label: "Kelembapan (% RH)", key: "humidity",   dec: 1, floor: 0, note: "Data sensor aktual, tanpa nilai perkiraan" },
  dust_index:  { label: "Indeks debu",     key: "dust_index",   dec: 2, floor: 0, note: "Data sensor aktual, tanpa nilai perkiraan" },
};

const thin = (pts, max = 300) => {
  if (pts.length <= max) return pts;
  const s = Math.ceil(pts.length / max);
  return pts.filter((_, i) => i % s === 0 || i === pts.length - 1);
};

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

function buildSeries() {
  const h = state.history;
  if (!h) return [];
  const tab = TABS[state.tab];
  const out = Object.keys(h.nodes).sort().map((id, i) => ({
    name: id, color: PALETTE[i % PALETTE.length], width: 1.8, step: false,
    pts: thin(h.nodes[id].map((r) => ({ t: parseTs(r.timestamp), v: r[tab.key] })).filter((p) => Number.isFinite(p.t))),
  }));
  if (state.tab === "control") {
    const pts = h.zone.map((r) => ({ t: parseTs(r.timestamp), v: r.zone_control_level })).filter((p) => Number.isFinite(p.t));
    if (pts.length && state.control?.worker_alive) pts.push({ t: Date.now(), v: pts[pts.length - 1].v });
    out.push({ name: "Zona", color: ZONE_COLOR, width: 2.6, step: true, pts });
  }
  return out;
}

function renderChart() {
  const wrap = $("#history-chart");
  const tab = TABS[state.tab];
  $("#history-caption").textContent = `${tab.label}, ${RANGE_TEXT[state.range]} terakhir`;
  $("#chart-note").textContent = tab.note;

  const series = buildSeries();
  const segs = series.map((s) => ({ ...s, segs: segments(s.pts) }));
  const values = segs.flatMap((s) => s.segs.flat().map((p) => p.v));
  const tip = $("#chart-tip");

  if (!values.length) {
    wrap.innerHTML = `<div class="chart-empty">Belum ada data pada rentang waktu ini.</div>`;
    wrap.appendChild(tip);
    $("#chart-legend").innerHTML = "";
    return;
  }

  const t1 = Date.now(), t0 = t1 - RANGE_MS[state.range];
  let y0, y1;
  if (tab.fixed) [y0, y1] = tab.fixed;
  else {
    const mn = Math.min(...values), mx = Math.max(...values);
    const span = mx - mn || Math.max(1, Math.abs(mx) * 0.1);
    y0 = mn - span * 0.15; y1 = mx + span * 0.15;
    if (tab.floor != null) y0 = Math.max(tab.floor, y0);
  }
  const X = (t) => L + ((Math.max(t0, t) - t0) / (t1 - t0)) * PW;
  const Y = (v) => T + PH - ((v - y0) / (y1 - y0)) * PH;

  const grid = [0, 1, 2, 3, 4].map((i) => {
    const r = i / 4, y = T + PH * r;
    return `<line class="chart-grid" x1="${L}" y1="${y}" x2="${W - RT}" y2="${y}"/><text class="chart-axis-text" x="${L - 8}" y="${y + 3}" text-anchor="end">${fmtNumber(y1 - (y1 - y0) * r, tab.dec)}</text>`;
  }).join("");
  const xl = [0, 1, 2, 3].map((i) => {
    const t = t0 + ((t1 - t0) * i) / 3;
    return `<text class="chart-axis-text" x="${X(t)}" y="${H - 8}" text-anchor="${i === 0 ? "start" : i === 3 ? "end" : "middle"}">${clock(t, false)}</text>`;
  }).join("");

  const lines = segs.map((s) => s.segs.map((seg) => {
    if (seg.length === 1) return `<circle cx="${X(seg[0].t).toFixed(1)}" cy="${Y(seg[0].v).toFixed(1)}" r="3" fill="${s.color}"/>`;
    const d = seg.map((p, i) => {
      const x = X(p.t).toFixed(1), y = Y(p.v).toFixed(1);
      return i === 0 ? `M${x} ${y}` : s.step ? ` H${x} V${y}` : ` L${x} ${y}`;
    }).join("");
    return `<path d="${d}" fill="none" stroke="${s.color}" stroke-width="${s.width}" stroke-linejoin="round" stroke-linecap="round"/>`;
  }).join("")).join("");

  wrap.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Grafik ${esc(tab.label)}">${grid}${xl}${lines}<line id="guide" x1="0" y1="${T}" x2="0" y2="${T + PH}" stroke="#94a3b8" stroke-dasharray="3 3" style="display:none"/></svg>`;
  wrap.appendChild(tip);

  $("#chart-legend").innerHTML = segs.map((s) => `<span><i class="dot" style="color:${s.color}"></i>${esc(s.name)}</span>`).join("");

  // Tooltip
  const svg = wrap.querySelector("svg"), guide = svg.querySelector("#guide");
  const hide = () => { tip.style.display = "none"; guide.style.display = "none"; };
  svg.addEventListener("mouseleave", hide);
  svg.addEventListener("mousemove", (e) => {
    const r = svg.getBoundingClientRect();
    const x = ((e.clientX - r.left) / r.width) * W;
    if (x < L || x > W - RT) return hide();
    const t = t0 + ((x - L) / PW) * (t1 - t0);
    const rows = segs.map((s) => {
      let best = null;
      for (const p of s.segs.flat()) {
        if (s.step) { if (p.t <= t) best = p; }
        else if (!best || Math.abs(p.t - t) < Math.abs(best.t - t)) best = p;
      }
      return best ? `<div><i class="dot" style="color:${s.color}"></i> ${esc(s.name)}: <b>${fmtNumber(best.v, tab.dec)}</b></div>` : "";
    }).join("");
    guide.setAttribute("x1", x); guide.setAttribute("x2", x); guide.style.display = "";
    tip.innerHTML = `<div class="tip-time">${clock(t)}</div>${rows}`;
    tip.style.display = "block";
    const wr = wrap.getBoundingClientRect();
    tip.style.left = `${Math.min(e.clientX - wr.left + 14, wr.width - 150)}px`;
  });
}

// ── Pemuatan data ──────────────────────────────────────────────────────────
async function refreshLive() {
  try {
    const [nodes, control] = await Promise.all([apiFetch("/api/nodes/latest"), apiFetch("/api/control/latest")]);
    state.nodes = nodes; state.control = control; state.failed = false;
  } catch (e) {
    if (!state.failed) showToast("Dashboard belum terhubung", "Pastikan layanan backend aktif.", "error");
    state.nodes = []; state.control = null; state.failed = true;
  }
  renderStatus(); renderDecision(); renderNodes();
}

async function refreshHistory() {
  try { state.history = await apiFetch(`/api/control/history?range=${state.range}`); }
  catch { state.history = null; }
  renderChart();
}

async function refreshAll() {
  const btn = $("#refresh-button");
  btn.classList.add("loading");
  await Promise.all([refreshLive(), refreshHistory()]);
  btn.classList.remove("loading");
}

// ── Kontrol ────────────────────────────────────────────────────────────────
function bindTabs(containerSel, attr, onPick) {
  document.querySelectorAll(`${containerSel} button`).forEach((b) => b.addEventListener("click", () => {
    document.querySelectorAll(`${containerSel} button`).forEach((x) => x.classList.toggle("active", x === b));
    onPick(b.dataset[attr]);
  }));
}
bindTabs("#metric-tabs", "tab", (v) => { state.tab = v; renderChart(); });
bindTabs("#range-tabs", "range", (v) => { state.range = v; $("#history-chart").classList.add("is-loading"); refreshHistory().finally(() => $("#history-chart").classList.remove("is-loading")); });
$("#refresh-button").addEventListener("click", refreshAll);

refreshAll();
setInterval(refreshLive, 5000);
setInterval(refreshHistory, 30000);
