import { buildSidebar, apiFetch, showToast, fmtNumber, parseTs, fmtClock as clock, visibleInterval,
         nodeName, zoneName, dustLevel, signalLevel, fanStatusLabel, needLabel as needWord, ageWords } from "/src/shared.js?v=20261111-1";
import { icon } from "/src/icons.js";
import { ZONE_COLOR as ZONE_LINE } from "/src/theme.js?v=20261111-1";
import { createFan } from "/src/fan-canvas.js?v=20261111-1";
import { drawChart, legendHtml, thin, PALETTE } from "/src/chart.js?v=20261111-1";

buildSidebar("ringkasan");

// ── Util ───────────────────────────────────────────────────────────────────
const $ = (s) => document.querySelector(s);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[c]));

const classKey = (c) => (c === "Baik" ? "good" : c === "Perlu Perhatian" ? "attention" : c === "Buruk" ? "bad" : "");

// ── State ──────────────────────────────────────────────────────────────────
let cfg = null;
const state = { nodes: [], control: null, history: null, sensorHistory: null, tab: "control", range: "24h", failed: false };
const fan = createFan($("#fan-canvas"));

// ── Status atas ────────────────────────────────────────────────────────────
function renderStatus() {
  const total = state.nodes.length;
  const valid = state.nodes.filter((n) => n.data_status === "Valid").length;
  const badge = $("#connection-badge");
  badge.classList.remove("offline", "warn");
  if (!total || valid === 0) badge.classList.add("offline");
  else if (valid < total) badge.classList.add("warn");
  badge.querySelector("span").textContent = total ? `${valid} dari ${total} sensor mengirim data terbaru` : "Data belum tersedia";

  const c = state.control;
  $("#zone-label").textContent = c?.zone_id ? `Kondisi ruangan, ${zoneName(c.zone_id)}` : "Kondisi ruangan saat ini";
  $("#updated-at").textContent = !c ? "—"
    : !c.worker_alive ? "Pengolahan data sedang berhenti"
    : `Diperbarui ${clock(parseTs(c.last_evaluated_at))}`;
}

// ── Kartu keputusan ────────────────────────────────────────────────────────
const needLabel = (u) => needWord(u, cfg);

// Kondisi zona = kondisi terburuk di antara node yang datanya valid.
function zoneCondition() {
  const valid = state.nodes.filter((n) => n.data_status === "Valid" && n.condition_class);
  if (!valid.length) return null;
  const order = ["Baik", "Perlu Perhatian", "Buruk"];
  const worst = valid.reduce((a, n) => (order.indexOf(n.condition_class) > order.indexOf(a) ? n.condition_class : a), "Baik");
  const count = (c) => valid.filter((n) => n.condition_class === c).length;
  const parts = [];
  if (count("Buruk")) parts.push(`${count("Buruk")} buruk`);
  if (count("Perlu Perhatian")) parts.push(`${count("Perlu Perhatian")} perlu perhatian`);
  if (count("Baik")) parts.push(`${count("Baik")} baik`);
  return { worst, summary: parts.join(", ") };
}

function renderZoneBanner(unavailable) {
  const box = $("#zone-banner"), z = unavailable ? null : zoneCondition();
  box.className = `zone-banner ${z ? classKey(z.worst) : ""}`;
  $("#zone-class").textContent = z ? z.worst : "Belum dapat dinilai";
  $("#zone-summary").textContent = z
    ? `Mengikuti sensor dengan kondisi terburuk. Dari ${state.nodes.length} sensor: ${z.summary}.`
    : "Menunggu data terbaru dari sensor.";
}

function renderDecision() {
  const c = state.control;
  const manual = c?.control_mode === "manual";
  const unavailable = !c || (!manual && (c.fan_command_status === "Kendali tidak tersedia" || !c.worker_alive));
  $("#decision-card").classList.toggle("unavailable", unavailable);

  const pill = $("#fan-status");
  pill.className = "status-pill";
  const note = $("#decision-note");

  if (unavailable) {
    pill.textContent = fanStatusLabel("Kendali tidak tersedia");
    pill.classList.add("unavailable");
    note.textContent = !c ? "Data kipas belum dapat dimuat."
      : !c.worker_alive ? "Pengolahan data sedang berhenti."
      : `Belum ada sensor yang mengirim data dalam ${c.freshness_seconds} detik terakhir. Kipas diatur ke putaran terendah.`;
    fan.setTarget(0, true);
    $("#pwm-value").textContent = "—";
    $("#fact-need").textContent = "—";
    $("#fact-node").textContent = "—";
  } else {
    pill.textContent = fanStatusLabel(c.fan_command_status);
    if (c.fan_command_status === "Mati") pill.classList.add("off");
    fan.setTarget(c.pwm_command_percent, false);
    $("#pwm-value").textContent = `${fmtNumber(c.pwm_command_percent, 0)}%`;
    const minimum = Number(c.pwm_command_percent) <= 0;
    note.textContent = manual ? "Kecepatan sedang diatur langsung oleh admin."
      : c.hysteresis_held ? "Kecepatan dipertahankan karena perubahan kebutuhan masih kecil."
      : minimum ? "Kondisi ruangan tidak memerlukan kipas. Kipas berputar pelan pada pengaturan terendah."
      : "";
    $("#fact-need").textContent = needLabel(c.zone_control_level);
    $("#fact-need").removeAttribute("title");
    $("#fact-node").textContent = c.determining_node_id ? nodeName(c.determining_node_id) : "Tidak ada";
    $("#fact-node").title = "Kipas mengikuti sensor dengan kebutuhan kipas tertinggi";
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
  const reason = n.data_status === "Data lama" ? `Data terakhir ${ageWords(n.data_age_seconds)}`
    : n.data_status === "Masukan tidak lengkap" ? "Data sensor belum lengkap"
    : n.data_status === "Tidak valid" ? "Data tidak terbaca"
    : "Belum ada data";
  const u = Math.max(0, Math.min(100, Number(n.control_level) || 0));
  const dust = dustLevel(n.dust_index);
  const sig = signalLevel(n.rssi, n.snr);

  let body;
  if (!ok) body = `<p class="tile-reason">${esc(reason)}</p>`;
  else if (!scored) body = `<p class="tile-wait">Data baru masuk, kondisi sedang dinilai.</p>`;
  else body = `<div class="tile-need"><span>Kebutuhan kipas</span><strong>${needLabel(n.control_level)}</strong></div>
    <div class="tile-bar" aria-hidden="true"><i style="width:${u}%"></i></div>`;

  return `
    <a class="panel node-tile${ok ? "" : " inactive"}${det ? " determining" : ""}" href="${href}">
      <div class="tile-top">
        <span class="tile-id">${esc(nodeName(n.node_id))} <span class="node-code">${esc(n.node_id)}</span></span>
        ${det ? `<span class="tag-determining" title="Kipas mengikuti sensor dengan kebutuhan tertinggi">${icon("target")} Diikuti kipas</span>` : ""}
      </div>
      <div class="tile-class ${ok && scored ? classKey(n.condition_class) : ""}">${ok ? (scored ? `<i class="dot"></i>${esc(n.condition_class)}` : "Menilai...") : "Tidak dipakai"}</div>
      ${body}
      <div class="tile-readings">
        <div><span>Suhu</span><strong>${fmtNumber(n.temperature, 1)} °C</strong></div>
        <div><span>Kelembapan</span><strong>${fmtNumber(n.humidity, 0)}%</strong></div>
        <div><span>Debu</span><strong class="level-word ${dust.key}">${dust.label}</strong></div>
        <div><span>Tekanan udara</span><strong>${n.pressure_hpa != null ? `${fmtNumber(n.pressure_hpa, 0)} hPa` : "—"}</strong></div>
      </div>
      <div class="tile-foot">
        <span>Sinyal <b class="level-word ${sig.key}">${sig.label}</b></span>
        <span>${n.data_age_seconds != null ? esc(ageWords(n.data_age_seconds)) : ""}</span>
      </div>
    </a>`;
}

function renderNodes() {
  const el = $("#node-board");
  if (state.failed) el.innerHTML = `<div class="board-empty">Data sensor tidak dapat dimuat.</div>`;
  else if (!state.nodes.length) el.innerHTML = `<div class="board-empty">Belum ada sensor terdaftar.</div>`;
  else el.innerHTML = state.nodes.map(tileHtml).join("");
}

// ── Grafik ─────────────────────────────────────────────────────────────────
const RANGE_MS = { "1h": 3600e3, "6h": 21600e3, "24h": 86400e3 };
const RANGE_TEXT = { "1h": "1 jam", "6h": "6 jam", "24h": "24 jam" };
const ZONE_COLOR = ZONE_LINE;
const TABS = {
  control:      { label: "Kebutuhan kipas (0–100)", key: "control_level", fixed: [0, 100], dec: 0, note: "0 = kipas tidak diperlukan, 100 = kebutuhan tertinggi. Garis tebal adalah yang diikuti kipas." },
  temperature:  { label: "Suhu (°C)", key: "temperature", dec: 1, note: "Hasil ukur sensor" },
  humidity:     { label: "Kelembapan (%)", key: "humidity", dec: 1, floor: 0, note: "Hasil ukur sensor" },
  dust_index:   { label: "Tingkat debu (0–100)", key: "dust_index", scale: 100, fixed: [0, 100], dec: 0, note: "Dibandingkan rentang sensor, bukan ukuran resmi PM2.5" },
  pressure_hpa: { label: "Tekanan udara (hPa)", key: "pressure_hpa", dec: 1, source: "sensor", note: "Hasil ukur sensor, tidak dipakai untuk mengatur kipas" },
};

function buildSeries() {
  const tab = TABS[state.tab];
  const h = tab.source === "sensor" ? state.sensorHistory : state.history;
  if (!h) return [];
  const scale = tab.scale ?? 1;
  const out = Object.keys(h.nodes).sort().map((id, i) => ({
    name: nodeName(id), color: PALETTE[i % PALETTE.length], width: 1.8, step: false,
    pts: thin(h.nodes[id].map((r) => ({ t: parseTs(r.timestamp), v: r[tab.key] == null ? null : r[tab.key] * scale })).filter((p) => Number.isFinite(p.t))),
  }));
  if (state.tab === "control") {
    const pts = h.zone.map((r) => ({ t: parseTs(r.timestamp), v: r.zone_control_level })).filter((p) => Number.isFinite(p.t));
    if (pts.length && state.control?.worker_alive) pts.push({ t: Date.now(), v: pts[pts.length - 1].v });
    out.push({ name: "Diikuti kipas", color: ZONE_COLOR, width: 2.6, step: true, pts });
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

// Tekanan udara tidak ikut perhitungan fuzzy, sehingga diambil dari riwayat sensor.
async function loadSensorHistory() {
  const ids = state.nodes.map((n) => n.node_id);
  const rows = await Promise.all(ids.map((id) =>
    apiFetch(`/api/nodes/${encodeURIComponent(id)}/history?range=${state.range}`).catch(() => [])));
  state.sensorHistory = { nodes: Object.fromEntries(ids.map((id, i) => [id, Array.isArray(rows[i]) ? rows[i] : []])) };
}

async function refreshHistory() {
  try { state.history = await apiFetch(`/api/control/history?range=${state.range}`); }
  catch { state.history = null; }
  if (TABS[state.tab].source === "sensor") { try { await loadSensorHistory(); } catch { state.sensorHistory = null; } }
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
bindTabs("#metric-tabs", "tab", (v) => { state.tab = v; if (TABS[v].source === "sensor") refreshHistory(); else renderChart(); });
bindTabs("#range-tabs", "range", (v) => { state.range = v; $("#history-chart").classList.add("is-loading"); refreshHistory().finally(() => $("#history-chart").classList.remove("is-loading")); });
$("#refresh-button").addEventListener("click", refreshAll);
let resizeTimer;
window.addEventListener("resize", () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(renderChart, 150); });

refreshAll();
visibleInterval(refreshLive, 5000);
visibleInterval(refreshHistory, 30000);
