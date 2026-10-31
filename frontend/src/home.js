import { buildSidebar, apiFetch, showToast, fmtNumber, parseTs, fmtClock as clock } from "/src/shared.js?v=20261029-3";
import { icon } from "/src/icons.js";
import { createFan } from "/src/fan-canvas.js";
import { drawChart, legendHtml, thin, PALETTE } from "/src/chart.js";

buildSidebar("ringkasan");

// ── Util ───────────────────────────────────────────────────────────────────
const $ = (s) => document.querySelector(s);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[c]));

function ageText(sec) {
  if (sec == null) return "";
  if (sec < 60) return `${Math.round(sec)} dtk`;
  if (sec < 3600) return `${Math.floor(sec / 60)} mnt`;
  return `${Math.floor(sec / 3600)} jam`;
}
const classKey = (c) => (c === "Baik" ? "good" : c === "Perlu Perhatian" ? "attention" : c === "Buruk" ? "bad" : "");

// ── State ──────────────────────────────────────────────────────────────────
let cfg = null;
const state = { nodes: [], control: null, history: null, tab: "control", range: "24h", failed: false };
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
// Kebutuhan kipas dalam kata, dihitung dari batas u_off dan u_max pada konfigurasi aktif.
function needLabel(u) {
  const off = cfg?.u_off, max = cfg?.u_max;
  if (u == null || off == null || max == null) return "—";
  if (u <= off) return "Tidak perlu";
  const r = (u - off) / (max - off);
  return r < 1 / 3 ? "Rendah" : r < 2 / 3 ? "Sedang" : "Tinggi";
}

// Kondisi zona = kondisi terburuk di antara node yang datanya valid.
function zoneCondition() {
  const valid = state.nodes.filter((n) => n.data_status === "Valid" && n.condition_class);
  if (!valid.length) return null;
  const order = ["Baik", "Perlu Perhatian", "Buruk"];
  const worst = valid.reduce((a, n) => (order.indexOf(n.condition_class) > order.indexOf(a) ? n.condition_class : a), "Baik");
  const count = (c) => valid.filter((n) => n.condition_class === c).length;
  const parts = [];
  if (count("Buruk")) parts.push(`${count("Buruk")} node buruk`);
  if (count("Perlu Perhatian")) parts.push(`${count("Perlu Perhatian")} perlu perhatian`);
  if (count("Baik")) parts.push(`${count("Baik")} baik`);
  return { worst, summary: parts.join(", ") };
}

function renderZoneBanner(unavailable) {
  const box = $("#zone-banner"), z = unavailable ? null : zoneCondition();
  box.className = `zone-banner ${z ? classKey(z.worst) : ""}`;
  $("#zone-class").textContent = z ? z.worst : "Belum dapat dinilai";
  $("#zone-summary").textContent = z ? `Dari ${state.nodes.length} node: ${z.summary}.` : "Menunggu data node yang valid.";
}

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
    $("#fact-need").textContent = "—";
    $("#fact-node").textContent = "—";
  } else {
    pill.textContent = c.fan_command_status;
    if (c.fan_command_status === "Mati") pill.classList.add("off");
    fan.setTarget(c.pwm_command_percent, false);
    $("#pwm-value").textContent = `${fmtNumber(c.pwm_command_percent, 1)}%`;
    note.textContent = c.hysteresis_held
      ? `PWM hasil hitung ${fmtNumber(c.candidate_pwm_percent, 1)}%, ditahan karena perubahan kecil.`
      : "";
    $("#fact-need").textContent = needLabel(c.zone_control_level);
    $("#fact-need").title = `Tingkat kendali zona ${fmtNumber(c.zone_control_level, 1)}`;
    $("#fact-node").textContent = c.determining_node_id ?? "Tidak ada";
  }
  renderZoneBanner(unavailable);
  $("#fact-mode").textContent = c?.control_mode === "manual" ? "Manual" : c ? "Otomatis" : "—";
  $("#fact-time").textContent = c?.created_at ? clock(parseTs(c.created_at)) : "—";
}

// ── Kartu node ─────────────────────────────────────────────────────────────
function tileHtml(n) {
  const ok = n.data_status === "Valid";
  const scored = n.condition_score != null;
  const det = ok && n.is_determining_node;
  const href = `/dashboard/nodes/detail.html?node=${encodeURIComponent(n.node_id)}`;
  const reason = n.data_status === "Data lama" ? `Data lama, ${ageText(n.data_age_seconds)} yang lalu` : (n.data_status || "Tidak ada data");
  const u = Math.max(0, Math.min(100, Number(n.control_level) || 0));
  const tip = scored ? `Skor kondisi ${fmtNumber(n.condition_score, 1)}, tingkat kendali ${fmtNumber(n.control_level, 1)}` : "";

  let body;
  if (!ok) body = `<p class="tile-reason">${esc(reason)}</p>`;
  else if (!scored) body = `<p class="tile-wait">Data baru masuk, hasil sedang dihitung.</p>`;
  else body = `<div class="tile-need"><span>Kebutuhan kipas</span><strong>${needLabel(n.control_level)}</strong></div>
    <div class="tile-bar" aria-hidden="true"><i style="width:${u}%"></i></div>`;

  return `
    <a class="panel node-tile${ok ? "" : " inactive"}${det ? " determining" : ""}" href="${href}" title="${esc(tip)}">
      <div class="tile-top">
        <span class="tile-id">${esc(n.node_id)}</span>
        ${det ? `<span class="tag-determining">${icon("target")} Penentu</span>` : ""}
      </div>
      <div class="tile-class ${ok && scored ? classKey(n.condition_class) : ""}">${ok ? (scored ? `<i class="dot"></i>${esc(n.condition_class)}` : "Menghitung...") : "Tidak dipakai"}</div>
      ${body}
      <div class="tile-readings">
        <div><span>Suhu</span><strong>${fmtNumber(n.temperature, 1)} °C</strong></div>
        <div><span>Kelembapan</span><strong>${fmtNumber(n.humidity, 0)}%</strong></div>
        <div><span>Debu</span><strong>${fmtNumber(n.dust_index, 2)}</strong></div>
      </div>
    </a>`;
}

function renderNodes() {
  const el = $("#node-board");
  if (state.failed) el.innerHTML = `<div class="board-empty">Data node tidak dapat dimuat.</div>`;
  else if (!state.nodes.length) el.innerHTML = `<div class="board-empty">Belum ada node terdaftar.</div>`;
  else el.innerHTML = state.nodes.map(tileHtml).join("");
}

// ── Grafik ─────────────────────────────────────────────────────────────────
const RANGE_MS = { "1h": 3600e3, "6h": 21600e3, "24h": 86400e3 };
const RANGE_TEXT = { "1h": "1 jam", "6h": "6 jam", "24h": "24 jam" };
const ZONE_COLOR = "#10213c";
const TABS = {
  control:     { label: "Tingkat kendali", key: "control_level", fixed: [0, 100], dec: 0, note: "u zona = nilai u tertinggi dari semua node" },
  temperature: { label: "Suhu (°C)", key: "temperature", dec: 1, note: "Data sensor aktual, tanpa nilai perkiraan" },
  humidity:    { label: "Kelembapan (% RH)", key: "humidity", dec: 1, floor: 0, note: "Data sensor aktual, tanpa nilai perkiraan" },
  dust_index:  { label: "Indeks debu", key: "dust_index", dec: 2, floor: 0, note: "Data sensor aktual, tanpa nilai perkiraan" },
};

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
  const tab = TABS[state.tab], wrap = $("#history-chart"), t1 = Date.now();
  $("#history-caption").textContent = `${tab.label}, ${RANGE_TEXT[state.range]} terakhir`;
  $("#chart-note").textContent = tab.note;
  const items = drawChart(wrap, { series: buildSeries(), t0: t1 - RANGE_MS[state.range], t1, fixed: tab.fixed, floor: tab.floor, dec: tab.dec, label: tab.label });
  if (!items) {
    wrap.innerHTML = `<div class="chart-empty">Belum ada data pada rentang waktu ini.</div>`;
    $("#chart-legend").innerHTML = "";
    return;
  }
  $("#chart-legend").innerHTML = legendHtml(items);
}

// ── Pemuatan data ──────────────────────────────────────────────────────────
async function refreshLive() {
  try {
    const [nodes, control] = await Promise.all([apiFetch("/api/nodes/latest"), apiFetch("/api/control/latest")]);
    if (!cfg) cfg = await apiFetch("/api/config/active").catch(() => null);
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
let resizeTimer;
window.addEventListener("resize", () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(renderChart, 150); });

refreshAll();
setInterval(refreshLive, 5000);
setInterval(refreshHistory, 30000);
