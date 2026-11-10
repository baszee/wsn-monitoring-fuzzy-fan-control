/**
 * fuzzy-analysis.js — Halaman Analisis Fuzzy
 * Visualisasi fungsi keanggotaan + 27 aturan
 */
import { COLORS } from "/src/theme.js?v=20261111-4";
import { buildSidebar, showToast, apiFetch, setConnectionBadge, setUpdatedAt,
         fmtNumber, conditionClass, conditionLabel, normalizeNode, startPolling, nodeName } from "/src/shared.js?v=20261111-4";

buildSidebar("fuzzy");

// ── MF Definitions (diambil dari konfigurasi aktif, bukan disalin manual) ─
const MF_STYLE = {
  temp:  { universe: [0, 50],  colors: { Rendah: COLORS.blue, Normal: "#0f8a6a", Tinggi: "#c94055" } },
  rh:    { universe: [0, 100], colors: { Kering: "#b76e00", Normal: "#0f8a6a", Lembap: "#0891b2" } },
  dust:  { universe: [0, 1],   colors: { Rendah: COLORS.blue, Sedang: "#b76e00", Tinggi: "#c94055" } },
  score: { universe: [0, 100], colors: { Baik: "#0f8a6a", "Perlu Perhatian": "#b76e00", Buruk: "#c94055" } },
};
const SRC_KEY = { temp: "temp", rh: "rh", dust: "dust", score: "condition_score" };

let membership = {};
try { membership = (await apiFetch("/api/config/active")).membership_params ?? {}; }
catch (e) { showToast("Gagal memuat konfigurasi", e.message, "error"); }

const MF_DEFS = Object.fromEntries(Object.entries(MF_STYLE).map(([key, style]) => [key, {
  universe: style.universe,
  terms: Object.entries(membership[SRC_KEY[key]] ?? {}).map(([name, spec]) => {
    const p = spec.params;
    return { name, color: style.colors[name] ?? "#64748b", fn: spec.type === "trimf" ? (x) => trimf(x, ...p) : (x) => trapmf(x, ...p) };
  }),
}]));

function trapmf(x, a, b, c, d) {
  if (x <= a || x >= d) return 0;
  if (x >= b && x <= c) return 1;
  if (x < b) return (x - a) / (b - a || 1);
  return (d - x) / (d - c || 1);
}
function trimf(x, a, b, c) {
  if (x <= a || x >= c) return 0;
  if (x <= b) return (x - a) / (b - a || 1);
  return (c - x) / (c - b || 1);
}

// ── Draw MF Chart ──────────────────────────────────────────────────────────
function drawMFChart(svgId, legendId, defKey, currentVal, activeMF) {
  const svg = document.getElementById(svgId);
  const leg = document.getElementById(legendId);
  if (!svg) return;

  const def = MF_DEFS[defKey];
  const W = 300, H = 120, PL = 28, PR = 8, PT = 8, PB = 22;
  const [uMin, uMax] = def.universe;
  const uRange = uMax - uMin;

  const toX = (u) => PL + ((u - uMin) / uRange) * (W - PL - PR);
  const toY = (v) => PT + (1 - v) * (H - PT - PB);

  const N = 200;
  let pathsHTML = def.terms.map(t => {
    const pts = [];
    for (let i = 0; i <= N; i++) {
      const u = uMin + (i / N) * uRange;
      pts.push(`${toX(u)},${toY(t.fn(u))}`);
    }
    return `<polyline points="${pts.join(" ")}" fill="none" stroke="${t.color}" stroke-width="1.8" opacity="0.9"/>`;
  }).join("");

  // Grid
  const gridHTML = [0, 0.5, 1].map(v => {
    const y = toY(v);
    return `<line x1="${PL}" y1="${y}" x2="${W - PR}" y2="${y}" stroke="#e2e8f0" stroke-dasharray="3 4"/>
            <text x="${PL - 4}" y="${y + 4}" text-anchor="end" font-size="8" fill="#94a3b8">${v}</text>`;
  }).join("");

  // Axis labels
  const axisHTML = [0, 0.25, 0.5, 0.75, 1].map(f => {
    const u = uMin + f * uRange;
    return `<text x="${toX(u)}" y="${H - 4}" text-anchor="middle" font-size="8" fill="#94a3b8">${Number(u.toFixed(2))}</text>`;
  }).join("");

  // Current value marker
  let markerHTML = "";
  if (currentVal != null) {
    const mx = toX(currentVal);
    markerHTML = `<line x1="${mx}" y1="${PT}" x2="${mx}" y2="${H - PB}" stroke="#5912ec" stroke-width="1.5" stroke-dasharray="3 3"/>
                  <text x="${mx}" y="${PT - 1}" text-anchor="middle" font-size="8" fill="#5912ec">${Number(currentVal.toFixed(2))}</text>`;
  }

  svg.innerHTML = gridHTML + pathsHTML + markerHTML + axisHTML;

  // Legend
  leg.innerHTML = def.terms.map(t => {
    const val = currentVal != null ? t.fn(currentVal) : null;
    const isActive = activeMF?.[t.name] > 0;
    return `<span class="mf-legend-item">
      <span class="mf-legend-color" style="background:${t.color};${isActive ? "height:5px;" : ""}"></span>
      ${t.name}${val != null ? ` <span class="mf-badge-val">${Math.round(val * 100)}%</span>` : ""}
    </span>`;
  }).join("");
}

// ── Node Select ────────────────────────────────────────────────────────────
let nodeIds = [];
let currentNodeId = null;

async function loadNodes() {
  try {
    const data  = await apiFetch("/api/nodes/latest");
    const nodes = Array.isArray(data) ? data : (data.nodes ?? []);
    nodeIds     = nodes.map(n => n.node_id);

    const sel = document.getElementById("node-select");
    sel.innerHTML = nodeIds.map(id => `<option value="${id}">${nodeName(id)} (${id})</option>`).join("");
    if (nodeIds.length) {
      const wanted = new URLSearchParams(location.search).get("node");
      currentNodeId = nodeIds.includes(wanted) ? wanted : nodeIds[0];
      sel.value     = currentNodeId;
      fetchDetail();
    }
  } catch(e) {
    showToast("Gagal memuat daftar node", e.message, "error");
  }
}

document.getElementById("node-select").addEventListener("change", e => {
  currentNodeId = e.target.value;
  if (currentNodeId) fetchDetail();
});

// ── Fetch & Render ─────────────────────────────────────────────────────────
let latestNodes = [];

async function fetchDetail() {
  if (!currentNodeId) return;
  try {
    const [nodesAll, detail] = await Promise.all([
      apiFetch("/api/nodes/latest"),
      apiFetch(`/api/fuzzy/${encodeURIComponent(currentNodeId)}/detail`),
    ]);

    latestNodes = (Array.isArray(nodesAll) ? nodesAll : (nodesAll.nodes ?? [])).map(normalizeNode);
    const node  = latestNodes.find(n => n.node_id === currentNodeId);

    const mf = detail.memberships ?? {};
    const ar = detail.active_rules ?? [];
    const outputs = detail.outputs ?? {};

    // Outputs
    const score = outputs.condition_score ?? node?.condition_score;
    document.getElementById("out-score").textContent   = fmtNumber(score);
    document.getElementById("out-control").textContent = fmtNumber(outputs.control_level ?? node?.control_level);
    const cls = conditionClass(score);
    document.getElementById("out-class").innerHTML = `<span class="pill-${cls}">${outputs.condition_class ?? node?.condition_class ?? conditionLabel(cls)}</span>`;
    document.getElementById("out-rules").textContent   = ar.filter(r => (r.alpha ?? 0) > 0).length;
    setUpdatedAt(node?.timestamp);

    // MF Charts — extract current values from node
    const tempVal  = node?.temperature ?? null;
    const rhVal    = node?.humidity ?? null;
    const dustVal  = node?.dust_index ?? null;
    const scoreVal = node?.condition_score ?? null;

    drawMFChart("mf-temp",  "legend-temp",  "temp",  tempVal,  mf.temperature);
    drawMFChart("mf-rh",    "legend-rh",    "rh",    rhVal,    mf.humidity);
    drawMFChart("mf-dust",  "legend-dust",  "dust",  dustVal,  mf.dust);
    drawMFChart("mf-score", "legend-score", "score", scoreVal, null);

    // Rules table
    renderRulesTable(ar);

    setConnectionBadge(true, document.getElementById("connection-badge"));
  } catch(e) {
    setConnectionBadge(false, document.getElementById("connection-badge"));
    showToast("Gagal memuat detail fuzzy", e.message, "error");
  }
}

// ── Rules Table ────────────────────────────────────────────────────────────
function renderRulesTable(rules) {
  const tbody = document.getElementById("rules-tbody");
  if (!rules.length) {
    tbody.innerHTML = `<tr><td colspan="8" class="table-loading">Tidak ada data aturan.</td></tr>`;
    return;
  }

  tbody.innerHTML = rules.map((r, i) => {
    const alpha  = r.alpha ?? 0;
    const pct    = (alpha * 100).toFixed(0);
    const active = alpha > 0;

    return `
      <tr class="${active ? "active-rule" : ""}">
        <td style="color:var(--text-soft);">${i + 1}</td>
        <td>${r.temp ?? "—"}</td>
        <td>${r.rh ?? "—"}</td>
        <td>${r.dust ?? "—"}</td>
        <td>${r.condition_class ?? "—"}</td>
        <td>${r.control_level ?? "—"}</td>
        <td style="font-weight:700;color:${active ? "var(--purple)" : "var(--text-soft)"};">${pct}%</td>
        <td><div class="alpha-bar" style="width:${pct}%;max-width:70px;"></div></td>
      </tr>`;
  }).join("");
}

// ── Init ───────────────────────────────────────────────────────────────────
document.getElementById("refresh-btn").addEventListener("click", () => { if (currentNodeId) fetchDetail(); });
loadNodes();
startPolling(() => { if (currentNodeId) fetchDetail(); }, 10000);
