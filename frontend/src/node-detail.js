/**
 * node-detail.js — Halaman detail satu sensor.
 * Bagian atas memakai bahasa umum; angka metode fuzzy ada di "Detail teknis".
 */
import { buildSidebar, showToast, apiFetch, setConnectionBadge, setUpdatedAt,
         fmtTime, fmtNumber, startPolling, parseTs, normalizeNode, dataQualityPill,
         nodeName, zoneName, dustLevel, signalLevel, needLabel } from "/src/shared.js?v=20261111-4";
import { drawChart, legendHtml, thin, PALETTE } from "/src/chart.js?v=20261111-4";

buildSidebar("nodes");

const params = new URLSearchParams(location.search);
const NODE_ID = params.get("node") ?? "";
const $ = (id) => document.getElementById(id);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[c]));
const CLASS_KEY = { "Baik": "good", "Perlu Perhatian": "warn", "Buruk": "bad" };

if (!NODE_ID) {
  $("page-title").textContent = "Sensor tidak ditemukan";
  $("page-sub").textContent = "Alamat halaman tidak menyebut sensor.";
} else {
  $("page-title").textContent = nodeName(NODE_ID);
  $("page-sub").textContent = NODE_ID;
  document.title = `${nodeName(NODE_ID)} — WSNova`;
  $("tech-link").href = `/dashboard/technical/?node=${encodeURIComponent(NODE_ID)}#fuzzy`;
}

let cfg = null;
let currentMetric = "temperature";
let currentRange = "24h";
let histData = [];

const METRICS = {
  temperature:  { label: "Suhu (°C)", title: "suhu (°C)", dec: 1 },
  humidity:     { label: "Kelembapan (%)", title: "kelembapan (%)", dec: 1, floor: 0 },
  dust_index:   { label: "Tingkat debu (0–100)", title: "tingkat debu (0–100)", dec: 0, scale: 100, fixed: [0, 100] },
  pressure_hpa: { label: "Tekanan udara (hPa)", title: "tekanan udara (hPa)", dec: 1 },
};
const RANGE_MS = { "1h": 3600e3, "6h": 21600e3, "24h": 86400e3 };
const RANGE_TEXT = { "1h": "1 jam", "6h": "6 jam", "24h": "24 jam" };

// ── Data terkini ───────────────────────────────────────────────────────────
async function fetchLatest() {
  try {
    const [nodesAll, control] = await Promise.all([
      apiFetch("/api/nodes/latest"),
      apiFetch("/api/control/latest").catch(() => null),
    ]);
    if (!cfg) cfg = await apiFetch("/api/config/active").catch(() => null);

    const nodes = Array.isArray(nodesAll) ? nodesAll : (nodesAll.nodes ?? []);
    const node = nodes.map(normalizeNode).find((n) => n.node_id === NODE_ID);
    if (node) renderNode(node, control);
    setConnectionBadge(true, $("connection-badge"));
  } catch (e) {
    setConnectionBadge(false, $("connection-badge"));
    showToast("Gagal memuat detail", e.message, "error");
  }
}

function renderNode(node, control) {
  const dust = dustLevel(node.dust_index);
  const sig = signalLevel(node.rssi, node.snr);
  const scored = node.usable && node.condition_class;

  $("rd-temp").textContent = fmtNumber(node.temperature);
  $("rd-rh").textContent = fmtNumber(node.humidity);
  $("rd-pressure").textContent = fmtNumber(node.pressure_hpa, 1);
  $("rd-dust").innerHTML = `<span class="level-word ${dust.key}">${dust.label}</span>`;
  $("rd-dust-sub").textContent = node.dust_index != null ? `${dust.pct} dari 100, dibandingkan rentang sensor` : "dibandingkan rentang sensor";
  $("rd-class").innerHTML = scored
    ? `<span class="level-word ${CLASS_KEY[node.condition_class] ?? ""}">${esc(node.condition_class)}</span>` : "—";
  $("rd-signal").innerHTML = `<span class="level-word ${sig.key}">${sig.label}</span>`;

  const determining = node.usable && control?.determining_node_id === NODE_ID && control?.fan_command_status !== "Kendali tidak tersedia";
  $("info-need").textContent = node.usable ? needLabel(node.control_level, cfg) : "—";
  $("info-determining").textContent = determining ? "Ya, kebutuhannya paling tinggi" : "Tidak";
  $("info-valid").innerHTML = dataQualityPill(node);
  $("info-time").textContent = fmtTime(node.timestamp);
  $("info-zone").textContent = zoneName(node.zone_id);
  $("page-sub").textContent = `${NODE_ID} · ${zoneName(node.zone_id)}`;
  setUpdatedAt(node.timestamp);
}

// ── Riwayat ────────────────────────────────────────────────────────────────
async function fetchHistory() {
  try {
    const data = await apiFetch(`/api/nodes/${encodeURIComponent(NODE_ID)}/history?range=${currentRange}`);
    histData = Array.isArray(data) ? data : (data.history ?? []);
    drawHistoryChart();
  } catch (e) {
    $("detail-chart-wrap").innerHTML = `<div class="chart-empty">Gagal memuat riwayat: ${esc(e.message)}</div>`;
  }
}

function drawHistoryChart() {
  const m = METRICS[currentMetric], wrap = $("detail-chart-wrap"), t1 = Date.now();
  $("hist-title").textContent = `Riwayat ${m.title}, ${RANGE_TEXT[currentRange]} terakhir`;
  const scale = m.scale ?? 1;
  const pts = thin(histData
    .map((d) => ({ t: parseTs(d.timestamp), v: d[currentMetric] == null ? null : d[currentMetric] * scale }))
    .filter((p) => Number.isFinite(p.t)));
  const items = drawChart(wrap, {
    series: [{ name: nodeName(NODE_ID), color: PALETTE[0], width: 2, pts }],
    t0: t1 - RANGE_MS[currentRange], t1, fixed: m.fixed, floor: m.floor, dec: m.dec, label: m.label,
  });
  if (!items) wrap.innerHTML = `<div class="chart-empty">Belum ada data pada rentang waktu ini.</div>`;
}

function bindTabs(sel, attr, onPick) {
  $(sel).addEventListener("click", (e) => {
    const btn = e.target.closest("button");
    if (!btn) return;
    $(sel).querySelectorAll("button").forEach((b) => b.classList.toggle("active", b === btn));
    onPick(btn.dataset[attr]);
  });
}
bindTabs("hist-metric-tabs", "m", (v) => { currentMetric = v; drawHistoryChart(); });
bindTabs("hist-range-tabs", "r", (v) => { currentRange = v; fetchHistory(); });
let resizeTimer;
window.addEventListener("resize", () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(drawHistoryChart, 150); });

if (NODE_ID) {
  startPolling(fetchLatest, 10000);
  fetchHistory();
  setInterval(() => { if (!document.hidden) fetchHistory(); }, 30000);
}
