import { icon } from "/src/icons.js";
import { createFan } from "/src/fan-canvas.js?v=20261106-3";
import { buildSidebar, showToast, apiFetch, setConnectionBadge, fmtNumber, fmtClock, parseTs,
         startPolling, getSession, adminPost } from "/src/shared.js?v=20261106-3";

buildSidebar("fan");
const $ = (id) => document.getElementById(id);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[c]));
const fan = createFan($("fan-canvas"));
let cfg = null;
let session = { authenticated: false };
let sliderTouched = false;

function chainStep(iconName, label, value, hint = "") {
  return `<div class="chain-step"><span class="chain-step-icon">${icon(iconName)}</span>
    <div class="chain-step-body"><span>${label}</span><strong>${value}</strong>${hint ? `<span class="chain-values">${hint}</span>` : ""}</div></div>`;
}

function renderChain(ctrl, nodes, unavailable, manual) {
  const valid = nodes.filter((n) => n.data_status === "Valid");
  const perNode = valid.length ? valid.map((n) => `${esc(n.node_id)} ${fmtNumber(n.control_level, 1)}`).join("  |  ") : "Tidak ada node valid";
  const delta = cfg?.delta_d_update;
  const dTxt = delta != null ? ` ${fmtNumber(delta, 0)}%` : "";

  let filter = "—";
  if (!unavailable && ctrl.candidate_pwm_percent != null) {
    if (ctrl.hysteresis_held) filter = `Ditahan, selisih kurang dari${dTxt}`;
    else if (ctrl.auto_pwm_percent === 0) filter = "Tidak berlaku, fan mati";
    else filter = "Perubahan diteruskan";
  }
  const cand = unavailable || ctrl.candidate_pwm_percent == null ? "—" : `${fmtNumber(ctrl.candidate_pwm_percent, 1)}%`;
  const prev = unavailable || ctrl.previous_pwm_percent == null || manual ? "" : `PWM sebelumnya ${fmtNumber(ctrl.previous_pwm_percent, 1)}%`;
  const hasAuto = ctrl.zone_control_level != null;

  $("chain-steps").innerHTML = [
    chainStep("hash", "u tiap node", perNode),
    chainStep("bars", "Tingkat kendali zona", hasAuto ? fmtNumber(ctrl.zone_control_level, 1) : "—", hasAuto ? `Node penentu: ${esc(ctrl.determining_node_id ?? "tidak ada")}` : ""),
    chainStep("gauge", "PWM hasil hitung", cand),
    chainStep("repeat", "Penyaring perubahan kecil", filter, prev),
    chainStep("check", "Perintah PWM", unavailable ? "—" : `${fmtNumber(ctrl.pwm_command_percent, 1)}%`, manual ? "Manual, mengabaikan hasil otomatis" : ""),
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

// ── Kontrol admin ──────────────────────────────────────────────────────────
function renderAdmin(manual, ctrl) {
  $("admin-controls").hidden = !session.authenticated;
  $("admin-hint").hidden = session.authenticated;
  $("manual-auto").hidden = !manual;
  $("mode-pill").textContent = manual ? "Manual" : "Otomatis";
  $("mode-pill").className = manual ? "pill-warn" : "pill-good";
  $("mode-text").textContent = manual
    ? "Perintah fan ditentukan admin dan mengabaikan hasil otomatis."
    : "Perintah fan dihitung otomatis dari data node.";
  if (session.authenticated && !sliderTouched) {
    const v = Math.round(ctrl.pwm_command_percent ?? 0);
    $("manual-slider").value = v;
    $("manual-value").textContent = `${v}%`;
  }
}

async function adminAction(path, body, okTitle, okText) {
  try {
    await adminPost(path, body);
    showToast(okTitle, okText, "success");
    sliderTouched = false;
    await fetchAll();
  } catch (e) {
    showToast("Perintah tidak dapat diterapkan", e.message, "error");
    session = await getSession(true);
    await fetchAll();
  }
}

$("manual-slider").addEventListener("input", (e) => {
  sliderTouched = true;
  $("manual-value").textContent = `${e.target.value}%`;
});
$("manual-apply").addEventListener("click", () => {
  const v = Number($("manual-slider").value);
  adminAction("/api/control/manual", { pwm_percent: v }, "Mode manual aktif", `PWM ${v}% diterapkan.`);
});
$("manual-auto").addEventListener("click", () => {
  adminAction("/api/control/auto", {}, "Mode otomatis aktif", "Perintah fan kembali mengikuti hasil otomatis.");
});

// ── Pemuatan data ──────────────────────────────────────────────────────────
async function fetchAll() {
  try {
    const [ctrl, nodes] = await Promise.all([apiFetch("/api/control/latest"), apiFetch("/api/nodes/latest")]);
    if (!cfg) cfg = await apiFetch("/api/config/active").catch(() => null);
    session = await getSession();

    const manual = ctrl.control_mode === "manual";
    const unavailable = !manual && (ctrl.fan_command_status === "Kendali tidak tersedia" || !ctrl.worker_alive);
    $("fan-card").classList.toggle("unavailable", unavailable);
    $("zone-label").textContent = `Perintah PWM, ${ctrl.zone_id ?? "zona"}`;

    const pill = $("fan-status");
    pill.className = "status-pill";
    const note = $("decision-note");
    if (unavailable) {
      pill.textContent = "Kendali tidak tersedia";
      pill.classList.add("unavailable");
      note.textContent = !ctrl.worker_alive ? "Pengolahan data sedang terhenti." : `Tidak ada node valid dalam ${ctrl.freshness_seconds} detik terakhir.`;
      fan.setTarget(0, true);
      $("pwm-value").textContent = "—";
    } else {
      pill.textContent = ctrl.fan_command_status;
      if (ctrl.fan_command_status === "Mati") pill.classList.add("off");
      note.textContent = manual ? `PWM otomatis ${fmtNumber(ctrl.auto_pwm_percent, 1)}%.`
        : ctrl.hysteresis_held ? `Hasil hitung ${fmtNumber(ctrl.candidate_pwm_percent, 1)}%, perintah ditahan.` : "";
      fan.setTarget(ctrl.pwm_command_percent, false);
      $("pwm-value").textContent = `${fmtNumber(ctrl.pwm_command_percent, 1)}%`;
    }

    const hasAuto = ctrl.zone_control_level != null;
    $("stat-uzona").textContent = unavailable || !hasAuto ? "—" : fmtNumber(ctrl.zone_control_level, 1);
    $("stat-node").textContent = unavailable || !hasAuto ? "—" : (ctrl.determining_node_id ?? "Tidak ada");
    $("stat-mode").textContent = manual ? "Manual" : "Otomatis";
    $("stat-config").textContent = ctrl.config_version ?? "—";

    $("det-cycle").textContent = ctrl.processing_cycle_id ?? "—";
    $("det-time").textContent = ctrl.created_at ? fmtClock(parseTs(ctrl.created_at)) : "—";
    $("det-eval").textContent = ctrl.last_evaluated_at ? fmtClock(parseTs(ctrl.last_evaluated_at)) : "—";
    $("det-fresh").textContent = `${ctrl.freshness_seconds} detik`;
    $("row-auto").hidden = !manual;
    $("det-auto").textContent = `${fmtNumber(ctrl.auto_pwm_percent, 1)}%`;
    $("updated-at").textContent = ctrl.last_evaluated_at ? `Diperbarui ${fmtClock(parseTs(ctrl.last_evaluated_at))}` : "—";

    renderChain(ctrl, nodes, unavailable, manual);
    renderAdmin(manual, ctrl);
    setConnectionBadge(true, $("connection-badge"));

    if (hasAuto && ctrl.determining_node_id) {
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
