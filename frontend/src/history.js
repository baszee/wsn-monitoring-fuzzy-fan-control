import { buildSidebar, showToast, apiFetch, setConnectionBadge, setUpdatedAt, fmtRelative, fmtNumber, dataQualityPill, normalizeNode, startPolling, parseTs } from "/src/shared.js?v=20261101-1";
import { drawChart, legendHtml, thin, PALETTE } from "/src/chart.js";

buildSidebar("riwayat");

const METRICS = {
  control_level:   { label: "Tingkat kendali (u)", dec: 1, fixed: [0, 100] },
  condition_score: { label: "Skor kondisi (s)",    dec: 1, fixed: [0, 100] },
  temperature:     { label: "Suhu (°C)",           dec: 1 },
  humidity:        { label: "Kelembapan (% RH)",   dec: 1, floor: 0 },
  dust_index:      { label: "Indeks debu",         dec: 2, floor: 0 },
};
const RANGES = { "1h": ["1 jam", 3600e3], "6h": ["6 jam", 21600e3], "24h": ["24 jam", 86400e3] };
const state = { nodes: [], node: "ALL", metric: "control_level", range: "6h", history: null };

const $ = (id) => document.getElementById(id);
const nodeSel = $("node-select"), metricSel = $("metric-select"), rangeSel = $("range-select");
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[c]));
const badge = () => $("connection-badge");

metricSel.innerHTML = Object.entries(METRICS).map(([k, m]) => `<option value="${k}">${m.label}</option>`).join("");
rangeSel.innerHTML = Object.entries(RANGES).map(([k, r]) => `<option value="${k}">${r[0]}</option>`).join("");
metricSel.value = state.metric;
rangeSel.value = state.range;

function fillNodeSelect() {
  const ids = state.nodes.map((n) => n.node_id).sort();
  nodeSel.innerHTML = `<option value="ALL">Semua node</option>` + ids.map((id) => `<option value="${esc(id)}">${esc(id)}</option>`).join("");
  nodeSel.value = ids.includes(state.node) || state.node === "ALL" ? state.node : "ALL";
}

function condPill(n) {
  if (n.data_status !== "Valid") return dataQualityPill(n);
  const k = n.condition_class === "Baik" ? "good" : n.condition_class === "Perlu Perhatian" ? "warn" : n.condition_class === "Buruk" ? "bad" : "unknown";
  return `<span class="pill-${k}">${esc(n.condition_class ?? "Belum dinilai")}</span>`;
}

function renderTable() {
  const el = $("comparison-table");
  if (!state.nodes.length) {
    el.innerHTML = `<tr><td colspan="8" class="table-loading">Tidak ada data node.</td></tr>`;
    return;
  }
  el.innerHTML = state.nodes.map((n) => `
    <tr style="${n.node_id === state.node ? "background:rgba(37,99,235,.05);" : ""}">
      <td><strong>${esc(n.node_id)}</strong></td>
      <td>${fmtNumber(n.temperature, 1)}</td>
      <td>${fmtNumber(n.humidity, 1)}</td>
      <td>${fmtNumber(n.dust_index, 2)}</td>
      <td>${fmtNumber(n.condition_score, 1)}</td>
      <td>${fmtNumber(n.control_level, 1)}</td>
      <td>${condPill(n)}</td>
      <td style="font-size:.72rem;color:var(--text-soft);">${fmtRelative(n.timestamp)}</td>
    </tr>`).join("");
  setUpdatedAt(state.nodes.reduce((a, n) => (!a || parseTs(n.timestamp) > parseTs(a) ? n.timestamp : a), null));
}

function renderChart() {
  const m = METRICS[state.metric], [rangeText, rangeMs] = RANGES[state.range];
  const wrap = $("main-chart-wrap"), h = state.history;
  $("chart-title").textContent = `${m.label}, ${state.node === "ALL" ? "semua node" : state.node}, ${rangeText} terakhir`;

  const allIds = h ? Object.keys(h.nodes).sort() : [];
  const series = allIds.filter((id) => state.node === "ALL" || id === state.node).map((id) => ({
    name: id, color: PALETTE[allIds.indexOf(id) % PALETTE.length], width: 1.8,
    pts: thin(h.nodes[id].map((r) => ({ t: parseTs(r.timestamp), v: r[state.metric] })).filter((p) => Number.isFinite(p.t))),
  }));
  if (h && state.metric === "control_level" && state.node === "ALL") {
    const pts = h.zone.map((r) => ({ t: parseTs(r.timestamp), v: r.zone_control_level })).filter((p) => Number.isFinite(p.t));
    if (pts.length) pts.push({ t: Date.now(), v: pts[pts.length - 1].v });
    series.push({ name: "Zona", color: "#10213c", width: 2.6, step: true, pts });
  }

  const t1 = Date.now();
  const items = drawChart(wrap, { series, t0: t1 - rangeMs, t1, fixed: m.fixed, floor: m.floor, dec: m.dec, label: m.label });
  if (!items) {
    wrap.innerHTML = `<div class="empty-state"><p>Belum ada data pada rentang ini.</p></div>`;
    $("chart-stats").textContent = "0 titik data";
    $("chart-legend").innerHTML = "";
    return;
  }
  $("chart-legend").innerHTML = legendHtml(items);
  $("chart-stats").textContent = series.filter((s) => !s.step).map((s) => {
    const v = s.pts.map((p) => Number(p.v)).filter(Number.isFinite);
    if (!v.length) return "";
    const avg = v.reduce((a, b) => a + b, 0) / v.length;
    return `${s.name}: min ${fmtNumber(Math.min(...v), m.dec)}, maks ${fmtNumber(Math.max(...v), m.dec)}, rata-rata ${fmtNumber(avg, m.dec)} (${v.length} data)`;
  }).filter(Boolean).join("  |  ");
}

async function loadNodes() {
  const data = await apiFetch("/api/nodes/latest");
  state.nodes = (Array.isArray(data) ? data : (data.nodes ?? [])).map(normalizeNode);
  if (!nodeSel.options.length || nodeSel.options.length - 1 !== state.nodes.length) fillNodeSelect();
  renderTable();
}

async function loadHistory() {
  $("main-chart-wrap").innerHTML = `<div class="chart-loading">Memuat riwayat...</div>`;
  state.history = await apiFetch(`/api/control/history?range=${state.range}`);
  renderChart();
}

async function loadAll() {
  try {
    await Promise.all([loadNodes(), loadHistory()]);
    setConnectionBadge(true, badge());
  } catch (e) {
    setConnectionBadge(false, badge());
    $("main-chart-wrap").innerHTML = `<div class="empty-state"><p>Gagal memuat riwayat: ${esc(e.message)}</p></div>`;
    showToast("Gagal memuat riwayat", e.message, "error");
  }
}

nodeSel.addEventListener("change", () => { state.node = nodeSel.value; renderTable(); renderChart(); });
metricSel.addEventListener("change", () => { state.metric = metricSel.value; renderChart(); });
rangeSel.addEventListener("change", () => { state.range = rangeSel.value; loadHistory().catch((e) => showToast("Gagal memuat riwayat", e.message, "error")); });
$("load-btn").addEventListener("click", () => { state.node = nodeSel.value; state.metric = metricSel.value; state.range = rangeSel.value; loadAll(); });
$("refresh-btn").addEventListener("click", async () => { await loadAll(); showToast("Data diperbarui", "Riwayat dan perbandingan dimuat ulang.", "success"); });

loadAll();
startPolling(async () => { try { await loadNodes(); } catch {} }, 10000);   // tabel perbandingan
setInterval(() => loadHistory().catch(() => {}), 30000);
