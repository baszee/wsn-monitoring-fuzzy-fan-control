/**
 * fan.js — Halaman Fan & Kendali
 * Animasi baling-baling menggunakan Canvas + requestAnimationFrame
 */
import { buildSidebar, showToast, apiFetch, setConnectionBadge, setUpdatedAt,
         fmtTime, fmtNumber, startPolling, normalizeControl } from "/src/shared.js?v=20261029-3";

buildSidebar("fan");

// ── Fan Animation ──────────────────────────────────────────────────────────
const canvas = document.getElementById("fan-canvas");
const ctx    = canvas.getContext("2d");
const CX = 110, CY = 110, R = 96;

let targetPWM  = 0;   // 0–100
let currentPWM = 0;   // smooth
let angle      = 0;
let lastTs     = null;

function lerp(a, b, t) { return a + (b - a) * t; }

function drawFan(ts) {
  if (lastTs === null) lastTs = ts;
  const dt = Math.min((ts - lastTs) / 1000, 0.1);
  lastTs = ts;

  // Smoothly approach target
  currentPWM = lerp(currentPWM, targetPWM, 1 - Math.pow(0.02, dt));

  // Angular velocity: max ~720 deg/s at 100%, stops at 0%
  const omega = (currentPWM / 100) * 720;
  angle = (angle + omega * dt) % 360;

  // Clear
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  // Hub background circle
  ctx.save();
  ctx.beginPath();
  ctx.arc(CX, CY, R, 0, Math.PI * 2);
  ctx.fillStyle = "#f0f6ff";
  ctx.fill();
  ctx.strokeStyle = "#dbeafe";
  ctx.lineWidth = 2;
  ctx.stroke();
  ctx.restore();

  // Blades
  const BLADES = 4;
  ctx.save();
  ctx.translate(CX, CY);
  ctx.rotate((angle * Math.PI) / 180);
  for (let i = 0; i < BLADES; i++) {
    ctx.save();
    ctx.rotate((i * Math.PI * 2) / BLADES);
    // Blade shape
    const grad = ctx.createLinearGradient(0, 0, 60, -30);
    grad.addColorStop(0, "#2563EB");
    grad.addColorStop(1, "#60a5fa");
    ctx.beginPath();
    ctx.moveTo(8, 0);
    ctx.bezierCurveTo(12, -20, 50, -35, 65, -20);
    ctx.bezierCurveTo(72, -12, 55, 5, 40, 8);
    ctx.bezierCurveTo(25, 12, 8, 18, 8, 0);
    ctx.fillStyle = grad;
    ctx.globalAlpha = 0.88;
    ctx.fill();
    ctx.restore();
  }
  ctx.restore();

  // Hub cap
  ctx.save();
  ctx.beginPath();
  ctx.arc(CX, CY, 14, 0, Math.PI * 2);
  const hubGrad = ctx.createRadialGradient(CX - 3, CY - 3, 2, CX, CY, 14);
  hubGrad.addColorStop(0, "#60a5fa");
  hubGrad.addColorStop(1, "#1d4ed8");
  ctx.fillStyle = hubGrad;
  ctx.fill();
  ctx.restore();

  // PWM text
  ctx.save();
  ctx.font = `bold 16px 'DM Sans', sans-serif`;
  ctx.fillStyle = "#1e40af";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(`${Math.round(currentPWM)}%`, CX, CY + R + 16);
  ctx.restore();

  requestAnimationFrame(drawFan);
}

requestAnimationFrame(drawFan);

// ── Data Fetch ─────────────────────────────────────────────────────────────
let determiningNodeId = null;

async function fetchAll() {
  try {
    const ctrl = normalizeControl(await apiFetch("/api/control/latest"));

    const pwm   = ctrl.pwm_command_percent ?? 0;
    targetPWM   = pwm;
    determiningNodeId = ctrl.control_node_id ?? null;

    // Stats
    document.getElementById("stat-pwm").textContent    = `${fmtNumber(pwm, 1)} %`;
    document.getElementById("stat-status").textContent = ctrl.fan_command_status ?? "—";
    document.getElementById("stat-uzonal").textContent = fmtNumber(ctrl.zone_control_level);
    document.getElementById("stat-node").textContent   = ctrl.control_node_id ?? "—";
    setUpdatedAt(ctrl.created_at);

    // Detail rows
    document.getElementById("det-cycle").textContent    = ctrl.processing_cycle_id ?? "—";
    document.getElementById("det-zone").textContent     = ctrl.zone_id ?? "—";
    document.getElementById("det-node").textContent     = ctrl.control_node_id ?? "—";
    document.getElementById("det-uzone").textContent    = fmtNumber(ctrl.zone_control_level);
    document.getElementById("det-pwm-cand").textContent = fmtNumber(ctrl.pwm_command_percent, 1) + " %";
    document.getElementById("det-pwm-final").textContent= fmtNumber(ctrl.pwm_command_percent, 1) + " %";
    document.getElementById("det-mode").textContent     = ctrl.control_mode === "auto" ? "Otomatis" : (ctrl.control_mode === "manual" ? "Manual" : "—");
    document.getElementById("det-config").textContent   = ctrl.config_version ?? "—";
    document.getElementById("det-time").textContent     = fmtTime(ctrl.created_at);

    renderChain(ctrl);
    setConnectionBadge(true, document.getElementById("connection-badge"));

    // Fetch fuzzy detail of determining node
    if (determiningNodeId) {
      const detail = await apiFetch(`/api/fuzzy/${encodeURIComponent(determiningNodeId)}/detail`).catch(() => null);
      if (detail) renderDeterminingRules(detail.active_rules ?? []);
    }
  } catch(e) {
    setConnectionBadge(false, document.getElementById("connection-badge"));
    showToast("Gagal memuat data kendali", e.message, "error");
  }
}

// ── Chain Steps ────────────────────────────────────────────────────────────
function renderChain(ctrl) {
  const steps = [
    { icon: "📡", label: "Node Penentu", value: ctrl.control_node_id ?? "Tidak ada" },
    { icon: "🔢", label: "Kebutuhan kendali tertinggi", value: fmtNumber(ctrl.zone_control_level) },
    { icon: "📊", label: "Tingkat kendali zona", value: fmtNumber(ctrl.zone_control_level) },
    { icon: "⚡", label: "Perintah awal fan", value: `${fmtNumber(ctrl.pwm_command_percent, 1)} %` },
    { icon: "🔁", label: "Penyaring perubahan kecil", value: "Diterapkan" },
    { icon: "✅", label: "Perintah akhir fan", value: `${fmtNumber(ctrl.pwm_command_percent, 1)} %` },
  ];

  document.getElementById("chain-steps").innerHTML = steps.map((s, i) => `
    ${i > 0 ? `<div class="chain-arrow">↓</div>` : ""}
    <div class="chain-step">
      <span class="chain-step-icon">${s.icon}</span>
      <div class="chain-step-body">
        <span>${s.label}</span>
        <strong>${s.value}</strong>
      </div>
    </div>`).join("");
}

// ── Determining Node Fuzzy Rules ───────────────────────────────────────────
function renderDeterminingRules(rules) {
  const container = document.getElementById("determining-rules");
  if (!rules.length) {
    container.innerHTML = `<p style="color:var(--text-soft);font-size:.82rem;">Tidak ada aturan aktif.</p>`;
    return;
  }

  const sorted = [...rules].sort((a, b) => (b.alpha ?? 0) - (a.alpha ?? 0)).slice(0, 10);
  container.innerHTML = `
    <div class="sim-rules-list">
      ${sorted.map(r => {
        const alpha = r.alpha ?? 0;
        const pct   = (alpha * 100).toFixed(0);
        return `
          <div class="sim-rule-row ${alpha > 0 ? "active" : ""}">
            <span class="sim-rule-alpha">${pct}%</span>
            <span class="sim-rule-text">Suhu ${r.temp ?? "—"}, kelembapan ${r.rh ?? "—"}, debu ${r.dust ?? "—"} → ${r.condition_class ?? "—"}, kendali ${r.control_level ?? "—"}</span>
            <div class="sim-alpha-bar-wrap"><div class="sim-alpha-bar" style="width:${pct}%"></div></div>
          </div>`;
      }).join("")}
    </div>`;
}

// ── Init ───────────────────────────────────────────────────────────────────
document.getElementById("refresh-btn").addEventListener("click", fetchAll);
startPolling(fetchAll, 8000);
