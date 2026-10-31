/**
 * node-detail.js — Halaman Detail Node
 */
import { buildSidebar, showToast, apiFetch, setConnectionBadge, setUpdatedAt,
         fmtTime, fmtNumber, conditionClass, conditionLabel, startPolling,
         normalizeNode, dataQualityPill } from "/src/shared.js?v=20261101-3";

buildSidebar("nodes");

const params = new URLSearchParams(location.search);
const NODE_ID = params.get("node") ?? "";

if (!NODE_ID) {
  document.getElementById("page-title").textContent = "Node tidak ditemukan";
  document.getElementById("page-sub").textContent   = "Parameter node tidak tersedia.";
}

document.getElementById("page-title").textContent = `Detail ${NODE_ID}`;
document.getElementById("page-sub").textContent   = NODE_ID;

// ── Chart State ────────────────────────────────────────────────────────────
let currentMetric = "temperature";
let currentRange  = "24h";
let histData      = [];

// ── Fetch Latest ───────────────────────────────────────────────────────────
async function fetchLatest() {
  try {
    const [nodesAll, detail] = await Promise.all([
      apiFetch("/api/nodes/latest"),
      apiFetch(`/api/fuzzy/${encodeURIComponent(NODE_ID)}/detail`).catch(() => null),
    ]);

    const nodes = Array.isArray(nodesAll) ? nodesAll : (nodesAll.nodes ?? []);
    const node  = nodes.map(normalizeNode).find(n => n.node_id === NODE_ID);

    if (node) {
      document.getElementById("rd-temp").textContent    = fmtNumber(node.temperature);
      document.getElementById("rd-rh").textContent      = fmtNumber(node.humidity);
      document.getElementById("rd-voltage").textContent = fmtNumber(node.dust_raw_voltage, 3);
      document.getElementById("rd-dust").textContent    = node.dust_index != null ? fmtNumber(node.dust_index, 4) : "—";
      document.getElementById("rd-score").textContent   = fmtNumber(node.condition_score);
      document.getElementById("rd-control").textContent = fmtNumber(node.control_level);

      const cls = conditionClass(node.condition_score);
      document.getElementById("info-class").innerHTML   = `<span class="pill-${cls}">${conditionLabel(cls)}</span>`;
      document.getElementById("info-score2").textContent = fmtNumber(node.condition_score);
      document.getElementById("info-ctrl").textContent   = fmtNumber(node.control_level);
      document.getElementById("info-valid").innerHTML    = dataQualityPill(node);
      document.getElementById("info-zone").textContent = node.zone_id ?? "—";
      document.getElementById("page-sub").textContent = `${node.zone_id ?? "—"} · ${NODE_ID}`;
      document.getElementById("info-time").textContent  = fmtTime(node.timestamp);
      setUpdatedAt(node.timestamp);
    }

    if (detail) {
      renderMFList(detail.memberships ?? {});
      renderRules(detail.active_rules ?? []);
    }

    setConnectionBadge(true, document.getElementById("connection-badge"));
  } catch(e) {
    setConnectionBadge(false, document.getElementById("connection-badge"));
    showToast("Gagal memuat detail", e.message, "error");
  }
}

// ── Membership Degrees ─────────────────────────────────────────────────────
function renderMFList(mfMap) {
  const container = document.getElementById("mf-list");
  const labels = { temperature: "Suhu", humidity: "Kelembapan", dust: "Debu" };
  const entries = Object.entries(mfMap).flatMap(([group, terms]) =>
    Object.entries(terms ?? {}).map(([term, value]) => [`${labels[group] ?? group} · ${term}`, value])
  );
  if (!entries.length) { container.innerHTML = `<p style="color:var(--text-soft);font-size:.8rem;">Tidak ada data.</p>`; return; }

  container.innerHTML = entries.map(([key, val]) => {
    const pct = (Number(val) * 100).toFixed(1);
    return `
      <div>
        <div style="display:flex;justify-content:space-between;font-size:.75rem;margin-bottom:.2rem;">
          <span style="color:var(--text-soft);">${key.replace(/_/g," ")}</span>
          <strong style="color:var(--text);">${pct}%</strong>
        </div>
        <div class="mini-bar"><div class="mini-bar-fill" style="width:${pct}%;background:${val > 0.5 ? "#2F80ED" : "#94a3b8"};"></div></div>
      </div>`;
  }).join("");
}

// ── Active Rules ───────────────────────────────────────────────────────────
function renderRules(rules) {
  const container = document.getElementById("rules-container");
  if (!rules.length) {
    container.innerHTML = `<p style="color:var(--text-soft);font-size:.8rem;">Tidak ada aturan aktif.</p>`;
    return;
  }

  const sorted = [...rules].sort((a, b) => (b.alpha ?? 0) - (a.alpha ?? 0));
  container.innerHTML = `
    <table class="rules-table">
      <thead><tr><th>Aturan</th><th>Kondisi Masukan</th><th>Hasil</th><th>Kekuatan</th><th>Visual</th></tr></thead>
      <tbody>
        ${sorted.map((r, i) => {
          const alpha = r.alpha ?? 0;
          const pct   = (alpha * 100).toFixed(1);
          return `
            <tr class="${alpha > 0 ? "active-rule" : ""}">
              <td style="color:var(--text-soft);">${r.id ?? i + 1}</td>
              <td style="font-size:.75rem;">Suhu ${r.temp ?? "—"}, kelembapan ${r.rh ?? "—"}, debu ${r.dust ?? "—"}</td>
              <td style="font-size:.75rem;">${r.condition_class ?? "—"} · Kendali ${r.control_level ?? "—"}</td>
              <td style="font-weight:700;color:${alpha > 0 ? "var(--blue)" : "var(--text-soft)"};">${pct}%</td>
              <td><div class="alpha-bar" style="width:${pct}%;max-width:80px;"></div></td>
            </tr>`;
        }).join("")}
      </tbody>
    </table>`;
}

// ── History Chart ──────────────────────────────────────────────────────────
async function fetchHistory() {
  try {
    const data = await apiFetch(`/api/nodes/${encodeURIComponent(NODE_ID)}/history?range=${currentRange}`);
    histData = Array.isArray(data) ? data : (data.history ?? []);
    drawHistoryChart();
  } catch(e) {
    document.getElementById("detail-chart-wrap").innerHTML = `<p style="color:var(--text-soft);padding:1rem;">Gagal memuat riwayat: ${e.message}</p>`;
  }
}

function drawHistoryChart() {
  const wrap = document.getElementById("detail-chart-wrap");
  if (!histData.length) { wrap.innerHTML = `<p style="color:var(--text-soft);padding:1rem;font-size:.85rem;">Tidak ada data riwayat.</p>`; return; }

  const W = 700, H = 160, PL = 40, PR = 10, PT = 10, PB = 30;
  const values = histData.map(d => d[currentMetric] ?? 0).filter(v => v != null);
  const times  = histData.map(d => new Date(d.timestamp));

  const minV = Math.min(...values), maxV = Math.max(...values);
  const rangeV = maxV - minV || 1;
  const rangeT = (times[times.length - 1] - times[0]) || 1;

  const toX = (t) => PL + ((t - times[0]) / rangeT) * (W - PL - PR);
  const toY = (v) => PT + (1 - (v - minV) / rangeV) * (H - PT - PB);

  const points = histData.map((d, i) => `${toX(times[i])},${toY(d[currentMetric] ?? minV)}`).join(" ");

  // Grid lines
  const gridLines = [0, 0.25, 0.5, 0.75, 1].map(f => {
    const y = PT + f * (H - PT - PB);
    const v = (maxV - f * rangeV).toFixed(1);
    return `<line x1="${PL}" y1="${y}" x2="${W - PR}" y2="${y}" class="h-grid-line"/>
            <text x="${PL - 4}" y="${y + 4}" text-anchor="end" class="h-axis-label">${v}</text>`;
  }).join("");

  // Time labels
  const step = Math.max(1, Math.floor(histData.length / 5));
  const timeLabels = histData.filter((_, i) => i % step === 0).map((d, i) => {
    const t = new Date(d.timestamp);
    const x = toX(t);
    const label = `${String(t.getHours()).padStart(2,"0")}:${String(t.getMinutes()).padStart(2,"0")}`;
    return `<text x="${x}" y="${H - 2}" text-anchor="middle" class="h-axis-label">${label}</text>`;
  }).join("");

  wrap.innerHTML = `
    <svg viewBox="0 0 ${W} ${H}" style="width:100%;height:${H}px;">
      ${gridLines}
      <polyline points="${points}" fill="none" stroke="#2F80ED" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
      ${histData.map((d, i) => `<circle cx="${toX(times[i])}" cy="${toY(d[currentMetric] ?? minV)}" r="3" fill="#2F80ED"/>`).join("")}
      ${timeLabels}
    </svg>`;
}

// ── Tab Listeners ──────────────────────────────────────────────────────────
document.getElementById("hist-metric-tabs").addEventListener("click", e => {
  const btn = e.target.closest("button");
  if (!btn) return;
  document.querySelectorAll("#hist-metric-tabs button").forEach(b => b.classList.remove("active"));
  btn.classList.add("active");
  currentMetric = btn.dataset.m;
  drawHistoryChart();
});

document.getElementById("hist-range-tabs").addEventListener("click", e => {
  const btn = e.target.closest("button");
  if (!btn) return;
  document.querySelectorAll("#hist-range-tabs button").forEach(b => b.classList.remove("active"));
  btn.classList.add("active");
  currentRange = btn.dataset.r;
  fetchHistory();
});

// ── Init ───────────────────────────────────────────────────────────────────
if (NODE_ID) {
  startPolling(fetchLatest, 10000);
  fetchHistory();
}
