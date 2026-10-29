/**
 * history.js — Halaman Riwayat Data
 * Visualisasi tren historis sensor dan ringkasan perbandingan multi-node
 */
import {
  buildSidebar,
  showToast,
  apiFetch,
  setConnectionBadge,
  setUpdatedAt,
  fmtTime,
  fmtRelative,
  fmtNumber,
  conditionClass,
  conditionLabel,
  startPolling,
  normalizeNode,
  dataQualityPill,
} from "/src/shared.js?v=20261029-3";

buildSidebar("riwayat");

// ── State ──────────────────────────────────────────────────────────────────
let nodesList = [];
let selectedNode = "";
let selectedMetric = "temperature";
let selectedRange = "24h";
let historyData = [];

const METRIC_CONFIG = {
  temperature: { label: "Suhu", unit: "°C", color: "#2563EB", digits: 1 },
  humidity:    { label: "Kelembapan Relatif", unit: "% RH", color: "#06B6D4", digits: 1 },
  dust_index:  { label: "Indeks Debu", unit: "", color: "#D97706", digits: 3 },
};

// ── Elements ───────────────────────────────────────────────────────────────
const nodeSelectEl   = document.getElementById("node-select");
const metricSelectEl = document.getElementById("metric-select");
const rangeSelectEl  = document.getElementById("range-select");
const loadBtnEl      = document.getElementById("load-btn");
const refreshBtnEl   = document.getElementById("refresh-btn");
const chartTitleEl   = document.getElementById("chart-title");
const chartStatsEl   = document.getElementById("chart-stats");
const mainChartWrap  = document.getElementById("main-chart-wrap");
const chartLegendEl  = document.getElementById("chart-legend");
const compTableEl    = document.getElementById("comparison-table");

// ── Load Initial Node List & Current Values ────────────────────────────────
async function initNodes() {
  try {
    const data = await apiFetch("/api/nodes/latest");
    nodesList = (Array.isArray(data) ? data : (data.nodes ?? [])).map(normalizeNode);
    setConnectionBadge(true, document.getElementById("connection-badge"));

    if (nodesList.length > 0) {
      nodeSelectEl.innerHTML = nodesList
        .map((n) => `<option value="${n.node_id}">${n.node_id}</option>`)
        .join("");
      selectedNode = nodesList[0].node_id;
      nodeSelectEl.value = selectedNode;
    } else {
      nodeSelectEl.innerHTML = `<option value="">Tidak ada node</option>`;
    }

    renderComparisonTable();
    if (selectedNode) {
      await loadHistory();
    }
  } catch (err) {
    setConnectionBadge(false, document.getElementById("connection-badge"));
    showToast("Gagal memuat node", err.message, "error");
  }
}

// ── Comparison Table ───────────────────────────────────────────────────────
function renderComparisonTable() {
  if (!nodesList.length) {
    compTableEl.innerHTML = `<tr><td colspan="8" class="table-loading">Tidak ada data node.</td></tr>`;
    return;
  }

  compTableEl.innerHTML = nodesList
    .map((node) => {
      const cls = conditionClass(node.condition_score);
      const isSelected = node.node_id === selectedNode;
      return `
        <tr style="${isSelected ? "background: rgba(37, 99, 235, 0.05); font-weight: 600;" : ""}">
          <td><strong>${node.node_id}</strong></td>
          <td>${fmtNumber(node.temperature, 1)}</td>
          <td>${fmtNumber(node.humidity, 1)}</td>
          <td>${node.dust_index != null ? fmtNumber(node.dust_index, 3) : "—"}</td>
          <td>${node.condition_score != null ? fmtNumber(node.condition_score, 1) : "—"}</td>
          <td>${node.control_level != null ? fmtNumber(node.control_level, 1) : "—"}</td>
          <td><span class="pill-${cls}">${conditionLabel(cls)}</span><div style="margin-top:.3rem;">${dataQualityPill(node)}</div></td>
          <td style="font-size: 0.72rem; color: var(--text-soft);">${fmtRelative(node.timestamp)}</td>
        </tr>
      `;
    })
    .join("");

  const latestTs = nodesList.reduce((acc, n) => (!acc || n.timestamp > acc ? n.timestamp : acc), null);
  setUpdatedAt(latestTs);
}

// ── Load History from API ──────────────────────────────────────────────────
async function loadHistory() {
  if (!selectedNode) return;

  mainChartWrap.innerHTML = `<div class="chart-loading">Memuat data riwayat ${selectedNode}...</div>`;
  chartStatsEl.textContent = "";

  try {
    const res = await apiFetch(`/api/nodes/${encodeURIComponent(selectedNode)}/history?range=${selectedRange}`);
    historyData = Array.isArray(res) ? res : (res.history ?? []);
    setConnectionBadge(true, document.getElementById("connection-badge"));
    renderChart();
  } catch (err) {
    setConnectionBadge(false, document.getElementById("connection-badge"));
    mainChartWrap.innerHTML = `<div class="empty-state"><p>Gagal memuat riwayat: ${err.message}</p></div>`;
    showToast("Gagal memuat riwayat", err.message, "error");
  }
}

// ── Render SVG Chart ───────────────────────────────────────────────────────
function renderChart() {
  const cfg = METRIC_CONFIG[selectedMetric] || METRIC_CONFIG.temperature;
  chartTitleEl.textContent = `Riwayat ${cfg.label} — ${selectedNode} (${selectedRange})`;

  if (!historyData.length) {
    mainChartWrap.innerHTML = `<div class="empty-state"><p>Tidak ada catatan riwayat untuk node ${selectedNode} pada rentang ${selectedRange}.</p></div>`;
    chartStatsEl.textContent = "0 titik data";
    chartLegendEl.innerHTML = "";
    return;
  }

  // Extract values
  const values = historyData
    .map((item) => item[selectedMetric])
    .filter((v) => v !== null && v !== undefined && !isNaN(Number(v)))
    .map(Number);

  if (!values.length) {
    mainChartWrap.innerHTML = `<div class="empty-state"><p>Parameter tidak memiliki nilai valid dalam rentang ini.</p></div>`;
    return;
  }

  const minVal = Math.min(...values);
  const maxVal = Math.max(...values);
  const avgVal = values.reduce((a, b) => a + b, 0) / values.length;

  chartStatsEl.textContent = `Min: ${minVal.toFixed(cfg.digits)}${cfg.unit} | Max: ${maxVal.toFixed(cfg.digits)}${cfg.unit} | Rata-rata: ${avgVal.toFixed(cfg.digits)}${cfg.unit} (${values.length} data)`;

  chartLegendEl.innerHTML = `
    <span><i style="display:inline-block;width:10px;height:10px;background:${cfg.color};border-radius:2px;margin-right:4px;"></i> ${cfg.label}</span>
    <span>Rentang: ${selectedRange}</span>
    <span>Sumbu Y: ${minVal.toFixed(cfg.digits)} – ${maxVal.toFixed(cfg.digits)} ${cfg.unit}</span>
  `;

  // Draw SVG
  const W = 800;
  const H = 240;
  const PAD_L = 55;
  const PAD_R = 25;
  const PAD_T = 20;
  const PAD_B = 40;

  const chartW = W - PAD_L - PAD_R;
  const chartH = H - PAD_T - PAD_B;

  const yRange = (maxVal - minVal) || 1;
  const getY = (val) => PAD_T + (1 - (val - minVal) / yRange) * chartH;
  const getX = (index) => PAD_L + (values.length === 1 ? chartW / 2 : (index / (values.length - 1)) * chartW);

  // Horizontal Grid Lines & Y Labels (4 steps)
  let gridLines = "";
  for (let i = 0; i <= 4; i++) {
    const ratio = i / 4;
    const y = PAD_T + ratio * chartH;
    const labelVal = (maxVal - ratio * yRange).toFixed(cfg.digits);
    gridLines += `
      <line x1="${PAD_L}" y1="${y}" x2="${W - PAD_R}" y2="${y}" class="h-grid-line" stroke="#E2E8F0" stroke-dasharray="3 4"/>
      <text x="${PAD_L - 8}" y="${y + 4}" text-anchor="end" class="h-axis-label" fill="#64748B">${labelVal}${cfg.unit ? " " + cfg.unit : ""}</text>
    `;
  }

  // Points & Line path
  const pts = values.map((val, idx) => ({ x: getX(idx), y: getY(val) }));
  const polylinePoints = pts.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");

  // X Axis Time Labels (up to 6 labels)
  let timeLabels = "";
  const step = Math.max(1, Math.floor(historyData.length / 5));
  for (let i = 0; i < historyData.length; i += step) {
    const item = historyData[i];
    const x = getX(i);
    const date = new Date(item.timestamp);
    const timeStr = !isNaN(date.getTime())
      ? date.toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" })
      : `${i}`;
    timeLabels += `
      <text x="${x.toFixed(1)}" y="${H - 12}" text-anchor="middle" class="h-axis-label" fill="#64748B">${timeStr}</text>
    `;
  }

  // Dots
  const dots = pts
    .map(
      (p) => `<circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="3.5" fill="${cfg.color}" stroke="#FFFFFF" stroke-width="1.5"/>`
    )
    .join("");

  // Area under line
  const areaD = `M ${pts[0].x.toFixed(1)} ${H - PAD_B} L ${pts.map((p) => `${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" L ")} L ${pts[pts.length - 1].x.toFixed(1)} ${H - PAD_B} Z`;

  mainChartWrap.innerHTML = `
    <svg viewBox="0 0 ${W} ${H}" style="width: 100%; height: ${H}px; display: block;">
      ${gridLines}
      <path d="${areaD}" fill="${cfg.color}" fill-opacity="0.12"/>
      <polyline points="${polylinePoints}" fill="none" stroke="${cfg.color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
      ${dots}
      ${timeLabels}
    </svg>
  `;
}

// ── Event Handlers ─────────────────────────────────────────────────────────
loadBtnEl.addEventListener("click", () => {
  selectedNode = nodeSelectEl.value;
  selectedMetric = metricSelectEl.value;
  selectedRange = rangeSelectEl.value;
  loadHistory();
  renderComparisonTable();
});

refreshBtnEl.addEventListener("click", async () => {
  await initNodes();
  showToast("Data diperbarui", "Data riwayat dan perbandingan telah dimuat ulang.", "success");
});

nodeSelectEl.addEventListener("change", (e) => {
  selectedNode = e.target.value;
  loadHistory();
  renderComparisonTable();
});

metricSelectEl.addEventListener("change", (e) => {
  selectedMetric = e.target.value;
  renderChart();
});

rangeSelectEl.addEventListener("change", (e) => {
  selectedRange = e.target.value;
  loadHistory();
});

// ── Auto-polling for latest comparison table ───────────────────────────────
startPolling(async () => {
  try {
    const data = await apiFetch("/api/nodes/latest");
    nodesList = (Array.isArray(data) ? data : (data.nodes ?? [])).map(normalizeNode);
    renderComparisonTable();
  } catch (err) {
    // silent fail in background polling
  }
}, 12000);

// Initialize
initNodes();
