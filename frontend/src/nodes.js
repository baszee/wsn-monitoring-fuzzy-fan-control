/**
 * nodes.js — Halaman Node Sensor
 */
import { buildSidebar, showToast, apiFetch, setConnectionBadge, setUpdatedAt,
         fmtRelative, fmtNumber, conditionClass, conditionLabel, startPolling,
         normalizeNode, normalizeControl, dataQuality, dataQualityPill } from "/src/shared.js?v=20261029-3";

buildSidebar("nodes");

// ── State ──────────────────────────────────────────────────────────────────
let nodesData  = [];
let controlData = null;

// ── Render Helpers ─────────────────────────────────────────────────────────
function condPill(cls) {
  return `<span class="pill-${cls}">${conditionLabel(cls)}</span>`;
}

function renderNodeCard(node) {
  const isDetermining = controlData?.control_node_id === node.node_id;
  const cls = conditionClass(node.condition_score);
  const uiPct = node.control_level != null ? Math.round(node.control_level) : null;
  const dust  = node.dust_index != null ? node.dust_index : null;
  const quality = dataQuality(node);

  return `
    <div class="node-card ${isDetermining ? "determining" : ""}" data-node="${node.node_id}">
      <div class="node-card-head">
        <span class="node-id-badge">${node.node_id}</span>
        ${isDetermining ? `<span class="node-determining-tag">Penentu ★</span>` : ""}
        <span style="margin-left:auto;font-size:.72rem;color:var(--text-soft);">${fmtRelative(node.timestamp)}</span>
      </div>
      <div class="node-params">
        <div class="node-param">
          <span>Suhu</span>
          <strong>${fmtNumber(node.temperature)}°</strong>
        </div>
        <div class="node-param">
          <span>Kelembapan</span>
          <strong>${fmtNumber(node.humidity)}%</strong>
        </div>
        <div class="node-param">
          <span>Indeks Debu</span>
          <strong>${dust != null ? fmtNumber(dust, 3) : "—"}</strong>
        </div>
      </div>
      <div class="node-condition">
        <span class="cond-dot cond-${cls}"></span>
        <span>${conditionLabel(cls)}</span>
        ${node.condition_score != null ? `<span style="margin-left:auto;font-size:.72rem;color:var(--text-soft);">Skor ${fmtNumber(node.condition_score)}</span>` : ""}
      </div>
      ${uiPct != null ? `
      <div class="node-control-bar">
        <div class="bar-label"><span>Tingkat Kendali</span><strong>${fmtNumber(node.control_level)}</strong></div>
        <div class="mini-bar"><div class="mini-bar-fill" style="width:${uiPct}%"></div></div>
      </div>` : ""}
      <div class="node-footer">
        <span class="node-quality quality-${quality.key}">${quality.label}</span>
        <a href="/dashboard/nodes/detail.html?node=${encodeURIComponent(node.node_id)}" style="color:var(--blue);font-weight:600;">Detail →</a>
      </div>
    </div>`;
}

function renderNodeRow(node) {
  const isDetermining = controlData?.control_node_id === node.node_id;
  const cls = conditionClass(node.condition_score);
  return `
    <tr ${isDetermining ? 'style="background:rgba(37,99,235,.05);"' : ""}>
      <td><strong>${node.node_id}</strong>${isDetermining ? " ★" : ""}</td>
      <td>${fmtNumber(node.temperature)}</td>
      <td>${fmtNumber(node.humidity)}</td>
      <td>${node.dust_index != null ? fmtNumber(node.dust_index, 3) : "—"}</td>
      <td>${node.condition_score != null ? fmtNumber(node.condition_score) : "—"}</td>
      <td>${condPill(cls)}</td>
      <td>${node.control_level != null ? fmtNumber(node.control_level) : "—"}</td>
      <td>${dataQualityPill(node)}</td>
      <td style="font-size:.72rem;color:var(--text-soft);">${fmtRelative(node.timestamp)}</td>
      <td><a href="/dashboard/nodes/detail.html?node=${encodeURIComponent(node.node_id)}" style="color:var(--blue);font-weight:600;font-size:.8rem;">Detail →</a></td>
    </tr>`;
}

function renderKPIs() {
  const active = nodesData.length;
  const valid  = nodesData.filter(n => dataQuality(n).key === "valid").length;
  document.getElementById("kpi-active").textContent = active;
  document.getElementById("kpi-valid").textContent  = valid;
  document.getElementById("kpi-determining").textContent = controlData?.control_node_id ?? "—";

  // Worst condition across valid nodes
  const scores = nodesData.filter(n => n.is_valid && n.condition_score != null).map(n => n.condition_score);
  if (scores.length) {
    const worst = Math.max(...scores);
    const cls = conditionClass(worst);
    document.getElementById("kpi-condition").innerHTML = condPill(cls);
  } else {
    document.getElementById("kpi-condition").textContent = "—";
  }
}

function render() {
  renderKPIs();
  const grid = document.getElementById("node-grid");
  const tbody = document.getElementById("nodes-table-full");

  if (!nodesData.length) {
    grid.innerHTML  = `<div class="empty-state"><p>Belum ada data node.</p></div>`;
    tbody.innerHTML = `<tr><td colspan="10" class="table-loading">Tidak ada data.</td></tr>`;
    return;
  }

  grid.innerHTML  = nodesData.map(renderNodeCard).join("");
  tbody.innerHTML = nodesData.map(renderNodeRow).join("");

  // Latest update time
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
