/**
 * nodes.js — Halaman Node Sensor
 */
import { icon } from "./icons.js";
import { buildSidebar, showToast, apiFetch, setConnectionBadge, setUpdatedAt,
         fmtRelative, fmtNumber, startPolling, normalizeNode, normalizeControl,
         dataQuality, dataQualityPill, nodeName, dustLevel, signalLevel, needLabel } from "/src/shared.js?v=20261111-3";

buildSidebar("nodes");

// ── State ──────────────────────────────────────────────────────────────────
let nodesData  = [];
let controlData = null;
let cfg = null;

const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[c]));
const CLASS_KEY = { "Baik": "good", "Perlu Perhatian": "warn", "Buruk": "bad" };

// ── Render Helpers ─────────────────────────────────────────────────────────
function condPill(node) {
  if (!node.usable || !node.condition_class) return `<span class="pill-unknown">Belum dinilai</span>`;
  return `<span class="pill-${CLASS_KEY[node.condition_class] ?? "unknown"}">${esc(node.condition_class)}</span>`;
}

function renderNodeCard(node) {
  const isDetermining = controlData?.control_node_id === node.node_id && node.usable;
  const cls = node.usable ? (CLASS_KEY[node.condition_class] ?? "unknown") : "unknown";
  const uiPct = node.control_level != null ? Math.round(node.control_level) : null;
  const dust = dustLevel(node.dust_index);
  const sig = signalLevel(node.rssi, node.snr);
  const quality = dataQuality(node);

  return `
    <div class="node-card ${isDetermining ? "determining" : ""}" data-node="${esc(node.node_id)}">
      <div class="node-card-head">
        <span class="node-id-badge">${esc(nodeName(node.node_id))}</span>
        <span class="node-code">${esc(node.node_id)}</span>
        ${isDetermining ? `<span class="node-determining-tag" title="Kipas mengikuti sensor dengan kebutuhan tertinggi">${icon("target")} Diikuti kipas</span>` : ""}
        <span style="margin-left:auto;font-size:.72rem;color:var(--text-soft);">${fmtRelative(node.timestamp)}</span>
      </div>
      <div class="node-params node-params-4">
        <div class="node-param"><span>Suhu</span><strong>${fmtNumber(node.temperature)} °C</strong></div>
        <div class="node-param"><span>Kelembapan</span><strong>${fmtNumber(node.humidity, 0)}%</strong></div>
        <div class="node-param"><span>Debu</span><strong class="level-word ${dust.key}">${dust.label}</strong></div>
        <div class="node-param"><span>Tekanan udara</span><strong>${node.pressure_hpa != null ? `${fmtNumber(node.pressure_hpa, 0)} hPa` : "—"}</strong></div>
      </div>
      <div class="node-condition">
        <span class="cond-dot cond-${cls}"></span>
        <span>${node.usable && node.condition_class ? esc(node.condition_class) : "Belum dinilai"}</span>
        <span style="margin-left:auto;font-size:.72rem;color:var(--text-soft);">Sinyal <b class="level-word ${sig.key}">${sig.label}</b></span>
      </div>
      ${uiPct != null && node.usable ? `
      <div class="node-control-bar">
        <div class="bar-label"><span>Kebutuhan kipas</span><strong>${needLabel(node.control_level, cfg)}</strong></div>
        <div class="mini-bar"><div class="mini-bar-fill" style="width:${uiPct}%"></div></div>
      </div>` : ""}
      <div class="node-footer">
        <span class="node-quality quality-${quality.key}">${quality.label}</span>
        <a href="/dashboard/nodes/detail.html?node=${encodeURIComponent(node.node_id)}" style="color:var(--blue);font-weight:600;">Detail ${icon("arrow-right")}</a>
      </div>
    </div>`;
}

function renderNodeRow(node) {
  const isDetermining = controlData?.control_node_id === node.node_id && node.usable;
  const dust = dustLevel(node.dust_index);
  const sig = signalLevel(node.rssi, node.snr);
  return `
    <tr ${isDetermining ? 'style="background:rgba(89,18,236,.05);"' : ""}>
      <td><strong>${esc(nodeName(node.node_id))}</strong>${isDetermining ? ` ${icon("target")}` : ""}</td>
      <td>${condPill(node)}</td>
      <td>${fmtNumber(node.temperature)}</td>
      <td>${fmtNumber(node.humidity)}</td>
      <td><span class="level-word ${dust.key}">${dust.label}</span></td>
      <td>${fmtNumber(node.pressure_hpa, 1)}</td>
      <td><span class="level-word ${sig.key}">${sig.label}</span></td>
      <td>${dataQualityPill(node)}</td>
      <td style="font-size:.72rem;color:var(--text-soft);">${fmtRelative(node.timestamp)}</td>
      <td><a href="/dashboard/nodes/detail.html?node=${encodeURIComponent(node.node_id)}" style="color:var(--blue);font-weight:600;font-size:.8rem;">Detail ${icon("arrow-right")}</a></td>
    </tr>`;
}

function renderKPIs() {
  const active = nodesData.length;
  const valid  = nodesData.filter(n => dataQuality(n).key === "valid").length;
  document.getElementById("kpi-active").textContent = active;
  document.getElementById("kpi-valid").textContent  = valid;
  document.getElementById("kpi-determining").textContent =
    controlData && controlData.fan_command_status !== "Kendali tidak tersedia" && controlData.control_node_id
      ? nodeName(controlData.control_node_id) : "—";

  // Kondisi ruangan = kondisi terburuk di antara sensor yang datanya terbaru.
  const order = ["Baik", "Perlu Perhatian", "Buruk"];
  const classes = nodesData.filter(n => n.usable && n.condition_class).map(n => n.condition_class);
  if (classes.length) {
    const worst = classes.reduce((a, c) => (order.indexOf(c) > order.indexOf(a) ? c : a), "Baik");
    document.getElementById("kpi-condition").innerHTML = `<span class="pill-${CLASS_KEY[worst]}">${worst}</span>`;
  } else {
    document.getElementById("kpi-condition").textContent = "—";
  }
}

function render() {
  renderKPIs();
  const grid = document.getElementById("node-grid");
  const tbody = document.getElementById("nodes-table-full");

  if (!nodesData.length) {
    grid.innerHTML  = `<div class="empty-state"><p>Belum ada data sensor.</p></div>`;
    tbody.innerHTML = `<tr><td colspan="10" class="table-loading">Tidak ada data.</td></tr>`;
    return;
  }

  grid.innerHTML  = nodesData.map(renderNodeCard).join("");
  tbody.innerHTML = nodesData.map(renderNodeRow).join("");

  const latest = nodesData.reduce((a, n) => (!a || n.timestamp > a) ? n.timestamp : a, null);
  setUpdatedAt(latest);
}

// ── Fetch ──────────────────────────────────────────────────────────────────
async function fetchAll() {
  try {
    const [nodes, ctrl] = await Promise.all([
      apiFetch("/api/nodes/latest"),
      apiFetch("/api/control/latest").catch(() => null),
    ]);
    if (!cfg) cfg = await apiFetch("/api/config/active").catch(() => null);
    nodesData   = (Array.isArray(nodes) ? nodes : (nodes.nodes ?? [])).map(normalizeNode);
    controlData = ctrl ? normalizeControl(ctrl) : null;
    setConnectionBadge(true, document.getElementById("connection-badge"));
    render();
  } catch (e) {
    setConnectionBadge(false, document.getElementById("connection-badge"));
    showToast("Gagal memuat data", e.message, "error");
  }
}

// ── Init ───────────────────────────────────────────────────────────────────
document.getElementById("refresh-btn").addEventListener("click", fetchAll);
startPolling(fetchAll, 8000);
