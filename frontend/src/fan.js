import { icon } from "/src/icons.js";
import { createFan } from "/src/fan-canvas.js";
import { buildSidebar, showToast, apiFetch, setConnectionBadge, fmtNumber, fmtClock, parseTs, startPolling } from "/src/shared.js?v=20261029-3";

buildSidebar("fan");
const $ = (id) => document.getElementById(id);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[c]));
const fan = createFan($("fan-canvas"));
let cfg = null;

function chainStep(iconName, label, value, hint = "") {
  return `<div class="chain-step"><span class="chain-step-icon">${icon(iconName)}</span>
    <div class="chain-step-body"><span>${label}</span><strong>${value}</strong>${hint ? `<span class="chain-values">${hint}</span>` : ""}</div></div>`;
}

function renderChain(ctrl, nodes, unavailable) {
  const valid = nodes.filter((n) => n.data_status === "Valid");
  const perNode = valid.length ? valid.map((n) => `${esc(n.node_id)} ${fmtNumber(n.control_level, 1)}`).join("  |  ") : "Tidak ada node valid";
  const delta = cfg?.delta_d_update;
  const dTxt = delta != null ? ` ${fmtNumber(delta, 0)}%` : "";

  let filter = "—";
  if (!unavailable && ctrl.candidate_pwm_percent != null) {
    if (ctrl.hysteresis_held) filter = `Ditahan, selisih kurang dari${dTxt}`;
    else if (ctrl.pwm_command_percent === 0) filter = "Tidak berlaku, fan mati";
    else filter = "Perubahan diteruskan";
  }
  const cand = unavailable || ctrl.candidate_pwm_percent == null ? "—" : `${fmtNumber(ctrl.candidate_pwm_percent, 1)}%`;
  const prev = unavailable || ctrl.previous_pwm_percent == null ? "" : `PWM sebelumnya ${fmtNumber(ctrl.previous_pwm_percent, 1)}%`;

  $("chain-steps").innerHTML = [
    chainStep("hash", "u tiap node", perNode),
    chainStep("bars", "u zona (nilai u tertinggi)", unavailable ? "—" : fmtNumber(ctrl.zone_control_level, 1), unavailable ? "" : `Node penentu: ${esc(ctrl.determining_node_id ?? "tidak ada")}`),
    chainStep("gauge", "PWM hasil hitung", cand),
    chainStep("repeat", "Penyaring perubahan kecil", filter, prev),
    chainStep("check", "Perintah PWM", unavailable ? "—" : `${fmtNumber(ctrl.pwm_command_percent, 1)}%`),
  ].join("");
}

function renderRules(rules) {
  const box = $("determining-rules");
  const active = rules.filter((r) => (r.alpha ?? 0) > 0).sort((a, b) => b.alpha - a.alpha).slice(0, 10);
  if (!active.length) {
    box.innerHTML = `<p style="color:var(--text-soft);font-size:.82rem;">Tidak ada aturan aktif.</p>`;
    return;
  }
  box.innerHTML = `<div class="sim-rules-list">${active.map((r) => {
    const pct = (r.alpha * 100).toFixed(0);
    return `<div class="sim-rule-row active">
      <span class="sim-rule-alpha">${pct}%</span>
      <span class="sim-rule-text">Aturan ${esc(r.id)}: debu ${esc(r.dust)}, RH ${esc(r.rh)}, suhu ${esc(r.temp)}. Hasil: kondisi ${esc(r.condition_class)}, kendali ${esc(r.control_level)}</span>
      <div class="sim-alpha-bar-wrap"><div class="sim-alpha-bar" style="width:${pct}%"></div></div></div>`;
  }).join("")}</div>`;
}

async function fetchAll() {
  try {
    const [ctrl, nodes] = await Promise.all([apiFetch("/api/control/latest"), apiFetch("/api/nodes/latest")]);
    if (!cfg) cfg = await apiFetch("/api/config/active").catch(() => null);

    const unavailable = ctrl.fan_command_status === "Kendali tidak tersedia" || !ctrl.worker_alive;
    $("fan-card").classList.toggle("unavailable", unavailable);
    $("zone-label").textContent = `Perintah PWM, ${ctrl.zone_id ?? "zona"}`;

    const pill = $("fan-status");
    pill.className = "status-pill";
    const note = $("decision-note");
    if (unavailable) {
      pill.textContent = "Kendali tidak tersedia";
      pill.classList.add("unavailable");
      note.textContent = !ctrl.worker_alive ? "Pemroses data tidak berjalan." : `Tidak ada node valid dalam ${ctrl.freshness_seconds} detik terakhir.`;
      fan.setTarget(0, true);
      $("pwm-value").textContent = "—";
    } else {
      pill.textContent = ctrl.fan_command_status;
      if (ctrl.fan_command_status === "Mati") pill.classList.add("off");
      note.textContent = ctrl.hysteresis_held ? `Hasil hitung ${fmtNumber(ctrl.candidate_pwm_percent, 1)}%, perintah ditahan.` : "";
      fan.setTarget(ctrl.pwm_command_percent, false);
      $("pwm-value").textContent = `${fmtNumber(ctrl.pwm_command_percent, 1)}%`;
    }

    $("stat-uzona").textContent = unavailable ? "—" : fmtNumber(ctrl.zone_control_level, 1);
    $("stat-node").textContent = unavailable ? "—" : (ctrl.determining_node_id ?? "Tidak ada");
    const manual = ctrl.control_mode === "manual";
    $("stat-mode").textContent = manual ? "Manual" : "Otomatis";
    $("mode-pill").textContent = manual ? "Manual" : "Otomatis";
    $("stat-config").textContent = ctrl.config_version ?? "—";

    $("det-cycle").textContent = ctrl.processing_cycle_id ?? "—";
    $("det-time").textContent = ctrl.created_at ? fmtClock(parseTs(ctrl.created_at)) : "—";
    $("det-eval").textContent = ctrl.last_evaluated_at ? fmtClock(parseTs(ctrl.last_evaluated_at)) : "—";
    $("det-fresh").textContent = `${ctrl.freshness_seconds} detik`;
    $("updated-at").textContent = ctrl.last_evaluated_at ? `Diperbarui ${fmtClock(parseTs(ctrl.last_evaluated_at))}` : "—";

    renderChain(ctrl, nodes, unavailable);
    setConnectionBadge(true, $("connection-badge"));

    if (!unavailable && ctrl.determining_node_id) {
      const detail = await apiFetch(`/api/fuzzy/${encodeURIComponent(ctrl.determining_node_id)}/detail`).catch(() => null);
      renderRules(detail?.active_rules ?? []);
    } else {
      $("determining-rules").innerHTML = `<p style="color:var(--text-soft);font-size:.82rem;">Tidak ada node penentu.</p>`;
    }
  } catch (e) {
    setConnectionBadge(false, $("connection-badge"));
    showToast("Gagal memuat data kendali", e.message, "error");
  }
}

$("refresh-btn").addEventListener("click", fetchAll);
startPolling(fetchAll, 5000);
