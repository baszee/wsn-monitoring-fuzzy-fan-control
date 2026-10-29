const API_BASE = "/api";

const state = {
  nodes: [],
  control: null,
  history: [],
  selectedNodeId: null,
  metric: "temperature",
  range: "24h",
};

const metricConfig = {
  temperature: { label: "Suhu", unit: "°C", min: 0, max: 50, color: "#2f7df0" },
  humidity: { label: "Kelembapan", unit: "% RH", min: 0, max: 100, color: "#13a8aa" },
  dust_index: { label: "Indeks Debu", unit: "", min: 0, max: 1, color: "#3597e6" },
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function fetchJson(url) {
  const response = await fetch(url, { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error(`Permintaan gagal (${response.status})`);
  return response.json();
}

function formatNumber(value, digits = 1) {
  return Number.isFinite(Number(value)) ? Number(value).toFixed(digits).replace(".", ",") : "—";
}

function formatTime(value, includeSeconds = false) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleTimeString("id-ID", {
    hour: "2-digit",
    minute: "2-digit",
    second: includeSeconds ? "2-digit" : undefined,
    hour12: false,
  });
}

function classNameForCondition(value) {
  if (value === "Baik") return "good";
  if (value === "Perlu Perhatian") return "attention";
  if (value === "Buruk") return "bad";
  return "";
}

function dataQuality(node) {
  if (!node?.status_valid) return { label: "Tidak valid", className: "invalid" };
  const complete = [node.temperature, node.humidity, node.dust_index].every((value) => value != null && Number.isFinite(Number(value)));
  if (!complete) return { label: "Belum lengkap", className: "stale" };
  const timestamp = new Date(node.source_timestamp).getTime();
  if (!Number.isFinite(timestamp) || Date.now() - timestamp > 10 * 60 * 1000) return { label: "Data lama", className: "stale" };
  return { label: "Valid", className: "" };
}

function selectedNode() {
  return state.nodes.find((node) => node.node_id === state.selectedNodeId) || state.nodes[0] || null;
}

function linePoints(values, width, height, min, max, padding = 2) {
  if (!values.length) return [];
  const usableWidth = width - padding * 2;
  const usableHeight = height - padding * 2;
  const range = max - min || 1;
  return values.map((value, index) => ({
    x: padding + (values.length === 1 ? usableWidth / 2 : (index / (values.length - 1)) * usableWidth),
    y: padding + usableHeight - ((Math.min(max, Math.max(min, value)) - min) / range) * usableHeight,
  }));
}

function pathFromPoints(points) {
  return points.map((point, index) => `${index === 0 ? "M" : "L"}${point.x.toFixed(1)} ${point.y.toFixed(1)}`).join(" ");
}

function renderSparkline(selector, values, config, color) {
  const svg = $(selector);
  if (!svg) return;
  const points = linePoints(values, 100, 28, config.min, config.max, 2);
  if (!points.length) {
    svg.innerHTML = "";
    return;
  }
  const line = pathFromPoints(points);
  const area = `${line} L${points.at(-1).x.toFixed(1)} 28 L${points[0].x.toFixed(1)} 28 Z`;
  svg.innerHTML = `
    ${points.length > 1 ? `<path class="spark-area" d="${area}" fill="${color}"></path>` : ""}
    <path class="spark-line" d="${line}" stroke="${color}"></path>
    ${points.length === 1 ? `<circle cx="${points[0].x}" cy="${points[0].y}" r="2.5" fill="${color}"></circle>` : ""}
  `;
}

function renderMetrics() {
  const node = selectedNode();
  const validNodes = state.nodes.filter((item) => dataQuality(item).label === "Valid").length;

  $("#metric-temp").textContent = formatNumber(node?.temperature);
  $("#metric-rh").textContent = formatNumber(node?.humidity);
  $("#metric-dust").textContent = formatNumber(node?.dust_index, 2);
  $("#metric-nodes").textContent = String(state.nodes.length || 0);
  $("#metric-temp-node").textContent = node?.node_id || "Belum ada node";
  $("#metric-rh-node").textContent = node?.node_id || "Belum ada node";
  $("#metric-dust-node").textContent = node?.node_id || "Belum ada node";
  $("#metric-valid").textContent = `${validNodes} data segar`;
  $("#node-dots").innerHTML = state.nodes.map((item) => `<i class="${item.status_valid ? "valid" : ""}" title="${escapeHtml(item.node_id)}"></i>`).join("");

  renderSparkline("#spark-temp", state.history.map((item) => Number(item.temperature)), metricConfig.temperature, "#2f7df0");
  renderSparkline("#spark-rh", state.history.map((item) => Number(item.humidity)), metricConfig.humidity, "#13a8aa");
  renderSparkline("#spark-dust", state.history.map((item) => Number(item.dust_index)), metricConfig.dust_index, "#3597e6");
}

function renderNodeSelect() {
  const select = $("#node-select");
  select.innerHTML = state.nodes.map((node) => `<option value="${escapeHtml(node.node_id)}" ${node.node_id === state.selectedNodeId ? "selected" : ""}>${escapeHtml(node.node_id)}</option>`).join("");
}

function renderConnection() {
  const badge = $("#connection-badge");
  const valid = state.nodes.filter((node) => dataQuality(node).label === "Valid").length;
  badge.classList.toggle("offline", !state.nodes.length);
  badge.innerHTML = state.nodes.length
    ? `<i></i><span>${valid}/${state.nodes.length} data segar</span>`
    : `<i></i><span>Data tidak tersedia</span>`;
  $("#updated-at").textContent = `Diperbarui ${new Date().toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false })}`;
}

function renderControl() {
  const control = state.control;
  const level = Number(control?.zone_control_level ?? 0);
  const pwm = Number(control?.pwm_command_percent ?? 0);
  const status = control?.fan_command_status || "Tidak tersedia";
  const statusEl = $("#fan-status");

  statusEl.textContent = status;
  statusEl.className = "status-pill";
  if (status === "Mati") statusEl.classList.add("off");
  if (status === "Kendali tidak tersedia" || status === "Tidak tersedia") statusEl.classList.add("unavailable");

  $("#gauge-number").textContent = formatNumber(level, 1);
  $("#control-node").textContent = control?.determining_node_id || "Tidak ada";
  $("#control-pwm").textContent = `${formatNumber(pwm, 1)}%`;
  $("#control-time").textContent = formatTime(control?.created_at, true);
  $("#control-config").textContent = control?.config_version || "—";

  const circumference = 2 * Math.PI * 54;
  $("#gauge-value").style.strokeDashoffset = String(circumference * (1 - Math.min(100, Math.max(0, level)) / 100));
}

function renderNodesTable() {
  const body = $("#nodes-table");
  if (!state.nodes.length) {
    body.innerHTML = `<tr><td colspan="7" class="table-loading">Belum ada data node.</td></tr>`;
    return;
  }

  body.innerHTML = state.nodes.map((node) => {
    const conditionClass = classNameForCondition(node.condition_class);
    const quality = dataQuality(node);
    return `
      <tr data-node-id="${escapeHtml(node.node_id)}" class="${node.node_id === state.selectedNodeId ? "selected" : ""} ${node.is_determining_node ? "determining" : ""}">
        <td><span class="node-name">${escapeHtml(node.node_id)}</span></td>
        <td>${formatNumber(node.temperature)} °C</td>
        <td>${formatNumber(node.humidity)}%</td>
        <td>${formatNumber(node.dust_index, 2)}</td>
        <td><strong class="condition-text ${conditionClass}">${escapeHtml(node.condition_class || "Belum dinilai")}</strong></td>
        <td>${formatNumber(node.control_level, 1)}</td>
        <td><span class="table-status ${quality.className}"><i></i>${quality.label}</span></td>
      </tr>
    `;
  }).join("");

  $$("#nodes-table tr[data-node-id]").forEach((row) => {
    row.addEventListener("click", () => selectNode(row.dataset.nodeId));
  });
}

function renderNodeInfo() {
  const node = selectedNode();
  const pill = $("#condition-pill");
  $("#info-title").textContent = node ? `Informasi ${node.node_id}` : "Informasi Node";
  pill.textContent = node?.condition_class || "Belum dinilai";
  pill.className = `condition-pill ${classNameForCondition(node?.condition_class)}`;
  $("#info-time").textContent = formatTime(node?.source_timestamp, true);
  $("#info-validity").textContent = node ? dataQuality(node).label : "—";
  $("#info-score").textContent = formatNumber(node?.condition_score, 1);
  $("#info-control").textContent = formatNumber(node?.control_level, 1);
  $("#info-dust-voltage").textContent = Number.isFinite(Number(node?.dust_raw_voltage)) ? `${formatNumber(node.dust_raw_voltage, 2)} V` : "—";
}

function renderHistoryChart() {
  const container = $("#history-chart");
  const config = metricConfig[state.metric];
  const values = state.history.map((item) => Number(item[state.metric])).filter(Number.isFinite);
  $("#legend-label").textContent = config.label;
  $("#history-caption").textContent = `${config.label} ${state.selectedNodeId || "node"} dalam ${state.range === "1h" ? "1 jam" : state.range === "6h" ? "6 jam" : "24 jam"} terakhir`;

  if (!values.length) {
    container.innerHTML = `<div class="chart-empty">Belum ada data pada rentang waktu ini.</div>`;
    return;
  }

  const width = 760;
  const height = 220;
  const left = 44;
  const right = 16;
  const top = 12;
  const bottom = 31;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;
  const points = values.map((value, index) => ({
    x: left + (values.length === 1 ? plotWidth / 2 : (index / (values.length - 1)) * plotWidth),
    y: top + plotHeight - ((Math.min(config.max, Math.max(config.min, value)) - config.min) / (config.max - config.min)) * plotHeight,
  }));
  const line = pathFromPoints(points);
  const area = points.length > 1 ? `${line} L${points.at(-1).x} ${top + plotHeight} L${points[0].x} ${top + plotHeight} Z` : "";
  const grid = [0, 1, 2, 3, 4].map((step) => {
    const ratio = step / 4;
    const y = top + plotHeight * ratio;
    const labelValue = config.max - (config.max - config.min) * ratio;
    const label = state.metric === "dust_index" ? labelValue.toFixed(2) : Math.round(labelValue);
    return `<line class="chart-grid" x1="${left}" y1="${y}" x2="${width - right}" y2="${y}"></line><text class="chart-axis-text" x="${left - 9}" y="${y + 3}" text-anchor="end">${label}</text>`;
  }).join("");
  const timeIndexes = [...new Set([0, Math.floor((state.history.length - 1) / 2), state.history.length - 1])];
  const timeLabels = timeIndexes.map((index) => {
    const point = points[Math.min(index, points.length - 1)];
    const time = formatTime(state.history[index]?.timestamp);
    return `<text class="chart-axis-text" x="${point.x}" y="${height - 7}" text-anchor="middle">${time}</text>`;
  }).join("");

  container.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Grafik ${config.label}">
      <defs><linearGradient id="chartArea" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${config.color}" stop-opacity=".28"/><stop offset="1" stop-color="${config.color}" stop-opacity="0"/></linearGradient></defs>
      ${grid}
      ${area ? `<path class="chart-area" d="${area}"></path>` : ""}
      <path class="chart-line" d="${line}" style="stroke:${config.color}"></path>
      ${points.map((point) => `<circle class="chart-point" cx="${point.x}" cy="${point.y}" r="${points.length === 1 ? 4 : 2.6}" style="stroke:${config.color}"></circle>`).join("")}
      ${timeLabels}
    </svg>
  `;
}

function renderAll() {
  renderConnection();
  renderNodeSelect();
  renderMetrics();
  renderControl();
  renderNodesTable();
  renderNodeInfo();
  renderHistoryChart();
}

async function loadHistory() {
  if (!state.selectedNodeId) {
    state.history = [];
    return;
  }
  state.history = await fetchJson(`${API_BASE}/nodes/${encodeURIComponent(state.selectedNodeId)}/history?range=${state.range}`);
}

async function updateData() {
  const refreshButton = $("#refresh-button");
  refreshButton.classList.add("loading");
  try {
    const [nodes, control] = await Promise.all([
      fetchJson(`${API_BASE}/nodes/latest`),
      fetchJson(`${API_BASE}/control/latest`),
    ]);
    state.nodes = nodes;
    state.control = control;

    if (!state.selectedNodeId || !nodes.some((node) => node.node_id === state.selectedNodeId)) {
      state.selectedNodeId = control?.determining_node_id || nodes[0]?.node_id || null;
    }
    await loadHistory();
    renderAll();
  } catch (error) {
    console.error(error);
    state.nodes = [];
    state.history = [];
    renderAll();
    showToast("Dashboard belum terhubung", "Pastikan layanan backend aktif, lalu coba muat ulang data.");
  } finally {
    refreshButton.classList.remove("loading");
  }
}

async function selectNode(nodeId) {
  state.selectedNodeId = nodeId;
  $("#node-select").value = nodeId;
  try {
    await loadHistory();
  } catch (error) {
    console.error(error);
    state.history = [];
  }
  renderMetrics();
  renderNodesTable();
  renderNodeInfo();
  renderHistoryChart();
}

let toastTimer;
function showToast(title, message) {
  clearTimeout(toastTimer);
  $("#toast-title").textContent = title;
  $("#toast-message").textContent = message;
  $("#toast").classList.add("show");
  toastTimer = setTimeout(() => $("#toast").classList.remove("show"), 3200);
}

function bindEvents() {
  $("#refresh-button").addEventListener("click", updateData);
  $("#node-select").addEventListener("change", (event) => selectNode(event.target.value));

  $$("#metric-tabs button").forEach((button) => {
    button.addEventListener("click", () => {
      state.metric = button.dataset.metric;
      $$("#metric-tabs button").forEach((item) => item.classList.toggle("active", item === button));
      renderHistoryChart();
    });
  });

  $$("#range-tabs button").forEach((button) => {
    button.addEventListener("click", async () => {
      state.range = button.dataset.range;
      $$("#range-tabs button").forEach((item) => item.classList.toggle("active", item === button));
      $("#history-chart").innerHTML = `<div class="chart-loading">Memuat riwayat data...</div>`;
      try {
        await loadHistory();
      } catch (error) {
        console.error(error);
        state.history = [];
      }
      renderMetrics();
      renderHistoryChart();
    });
  });

  $$('[data-next-phase]').forEach((button) => {
    button.addEventListener("click", () => showToast(button.dataset.nextPhase, "Fondasi menunya sudah disiapkan. Isi halaman ini akan dibuat pada tahap berikutnya."));
  });

  const sidebar = $("#sidebar");
  const backdrop = $("#sidebar-backdrop");
  const closeSidebar = () => {
    sidebar.classList.remove("open");
    backdrop.classList.remove("show");
  };
  $("#menu-button").addEventListener("click", () => {
    sidebar.classList.add("open");
    backdrop.classList.add("show");
  });
  backdrop.addEventListener("click", closeSidebar);
}

document.addEventListener("DOMContentLoaded", () => {
  bindEvents();
  updateData();
  setInterval(updateData, 10000);
});
