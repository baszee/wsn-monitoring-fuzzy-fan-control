/**
 * settings.js — Halaman Konfigurasi Sistem
 * Menampilkan konfigurasi kendali aktif, parameter fuzzy, dan metadata penelitian
 */
import {
  buildSidebar,
  showToast,
  apiFetch,
  setConnectionBadge,
  setUpdatedAt,
  fmtRelative,
  fmtNumber,
  normalizeNode,
  dataQualityPill,
} from "/src/shared.js?v=20261101-1";

buildSidebar("konfigurasi");

// ── Elements ───────────────────────────────────────────────────────────────
const cfgVersionEl = document.getElementById("cfg-version");
const cfgStatusEl  = document.getElementById("cfg-status");
const cfgC0El      = document.getElementById("cfg-c0");
const cfgChEl      = document.getElementById("cfg-ch");
const cfgUoffEl    = document.getElementById("cfg-uoff");
const cfgUmaxEl    = document.getElementById("cfg-umax");
const cfgDminEl    = document.getElementById("cfg-dmin");
const cfgDeltaEl   = document.getElementById("cfg-delta");
const cfgRulesEl   = document.getElementById("cfg-rules");
const nodesTableEl = document.getElementById("registered-nodes-table");
const refreshBtnEl = document.getElementById("refresh-btn");

const MF_TITLES = { temp: "Suhu (°C)", rh: "Kelembapan (% RH)", dust: "Indeks debu (0–1)", condition_score: "Skor kondisi (0–100)", control_level: "Tingkat kendali (0–100)" };
const MF_SHAPE = { trapmf: "trapesium", trimf: "segitiga" };

function renderMfSummary(params = {}) {
  const el = document.getElementById("mf-summary");
  if (!el) return;
  el.innerHTML = Object.entries(MF_TITLES).map(([key, title]) => `
    <div class="mf-box"><strong>${title}</strong><ul>
      ${Object.entries(params[key] ?? {}).map(([name, s]) =>
        `<li><b>${name}:</b> ${MF_SHAPE[s.type] ?? s.type} [${s.params.map((x) => fmtNumber(x, Number.isInteger(x) ? 0 : 2)).join(", ")}]</li>`).join("")}
    </ul></div>`).join("");
}

// ── Fetch & Render ─────────────────────────────────────────────────────────
async function fetchConfigAndNodes() {
  try {
    const [cfg, nodesData] = await Promise.all([
      apiFetch("/api/config/active").catch(() => null),
      apiFetch("/api/nodes/latest").catch(() => []),
    ]);

    setConnectionBadge(true, document.getElementById("connection-badge"));

    // Render Config
    if (cfg) {
      cfgVersionEl.textContent = cfg.config_version ?? "—";
      cfgStatusEl.innerHTML    = cfg.is_active
        ? `<span class="active-pill">Aktif</span>`
        : `<span class="inactive-pill">Nonaktif</span>`;
      cfgC0El.textContent      = `${fmtNumber(cfg.dust_low_reference, 2)} V`;
      cfgChEl.textContent      = `${fmtNumber(cfg.dust_high_reference, 2)} V`;
      cfgUoffEl.textContent    = fmtNumber(cfg.u_off, 1);
      cfgUmaxEl.textContent    = fmtNumber(cfg.u_max, 2);
      cfgDminEl.textContent    = `${fmtNumber(cfg.d_min, 1)} %`;
      cfgDeltaEl.textContent   = `${fmtNumber(cfg.delta_d_update, 1)} %`;
      cfgRulesEl.textContent   = `${cfg.rule_base_count ?? "—"} aturan`;
      renderMfSummary(cfg.membership_params);
    }

    // Render Registered Nodes Table
    const nodes = (Array.isArray(nodesData) ? nodesData : (nodesData.nodes ?? [])).map(normalizeNode);
    if (!nodes.length) {
      nodesTableEl.innerHTML = `<tr><td colspan="5" class="table-loading">Tidak ada data node terdaftar.</td></tr>`;
      return;
    }

    nodesTableEl.innerHTML = nodes
      .map((node) => {
        const isActiveReg = node.is_active ?? true;
        return `
          <tr>
            <td><strong>${node.node_id}</strong></td>
            <td>${node.zone_id ?? "—"}</td>
            <td>
              <span class="${isActiveReg ? "active-pill" : "inactive-pill"}">
                ${isActiveReg ? "Terdaftar & Aktif" : "Nonaktif"}
              </span>
            </td>
            <td>
              ${dataQualityPill(node)}
            </td>
            <td style="font-size:0.75rem;color:var(--text-soft);">
              ${fmtRelative(node.timestamp || node.source_timestamp)}
            </td>
          </tr>
        `;
      })
      .join("");

    const latestTs = nodes.reduce(
      (acc, n) => (!acc || (n.timestamp || n.source_timestamp) > acc ? (n.timestamp || n.source_timestamp) : acc),
      null
    );
    setUpdatedAt(latestTs);
  } catch (err) {
    setConnectionBadge(false, document.getElementById("connection-badge"));
    showToast("Gagal memuat konfigurasi", err.message, "error");
  }
}

// ── Refresh Button ─────────────────────────────────────────────────────────
refreshBtnEl.addEventListener("click", async () => {
  await fetchConfigAndNodes();
  showToast("Konfigurasi Diperbarui", "Data konfigurasi dan status node berhasil dimuat ulang.", "success");
});

// Run Initial
fetchConfigAndNodes();
