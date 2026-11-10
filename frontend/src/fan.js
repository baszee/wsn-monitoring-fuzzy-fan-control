import { icon } from "/src/icons.js";
import { createFan } from "/src/fan-canvas.js?v=20261111-2";
import { buildSidebar, showToast, apiFetch, setConnectionBadge, fmtNumber, fmtClock, parseTs,
         startPolling, getSession, adminPost, nodeName, zoneName, needLabel, fanStatusLabel,
         techDetails, durationWords, staleControlNote, ageWords } from "/src/shared.js?v=20261111-2";

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
  const valid = nodes.filter((n) => n.data_status === "Valid" || n.used_for_control);
  const perNode = valid.length
    ? valid.map((n) => `${esc(nodeName(n.node_id))}: ${needLabel(n.control_level, cfg).toLowerCase()}${n.data_status !== "Valid" ? ` (data ${ageWords(n.data_age_seconds)})` : ""}`).join(" · ")
    : `Tidak ada data sensor dalam ${durationWords(ctrl.control_hold_seconds)} terakhir`;
  const hasAuto = ctrl.zone_control_level != null && !unavailable;

  let step3 = "—";
  if (!unavailable && ctrl.candidate_pwm_percent != null) {
    if (ctrl.hysteresis_held) step3 = "Dipertahankan, perubahan kebutuhan masih kecil";
    else if (ctrl.auto_pwm_percent === 0) step3 = "Kebutuhan rendah, kipas di putaran terendah";
    else step3 = "Kecepatan baru diterapkan";
  }
  const out = unavailable ? "—" : `${fmtNumber(ctrl.pwm_command_percent, 0)}%`;

  $("chain-steps").innerHTML = [
    chainStep("radio", "1. Setiap sensor menilai kebutuhan kipas", perNode),
    chainStep("target", "2. Kipas mengikuti kebutuhan tertinggi", hasAuto ? `${esc(nodeName(ctrl.determining_node_id))}, kebutuhan ${needLabel(ctrl.zone_control_level, cfg).toLowerCase()}` : "—"),
    chainStep("repeat", "3. Perubahan kecil diabaikan agar kipas tidak naik-turun", step3),
    chainStep("check", "4. Kecepatan yang dikirim ke kipas", out, manual ? "Mode manual: diatur langsung oleh admin" : ""),
  ].join("");
}

function renderTech(ctrl, rules) {
  const root = $("tech-root");
  const prev = root.querySelector("details");
  const open = prev ? prev.open : false;
  const rows = [
    ["Tingkat kendali zona u", ctrl.zone_control_level != null ? fmtNumber(ctrl.zone_control_level, 2) : "—"],
    ["Node penentu", esc(ctrl.determining_node_id ?? "—")],
    ["PWM hasil pemetaan (kandidat)", ctrl.candidate_pwm_percent != null ? `${fmtNumber(ctrl.candidate_pwm_percent, 1)}%` : "—"],
    ["PWM sebelumnya", ctrl.previous_pwm_percent != null ? `${fmtNumber(ctrl.previous_pwm_percent, 1)}%` : "—"],
    ["PWM otomatis (pembanding saat Manual)", ctrl.auto_pwm_percent != null ? `${fmtNumber(ctrl.auto_pwm_percent, 1)}%` : "—"],
    ["Ditahan histeresis", ctrl.hysteresis_held ? "Ya" : "Tidak"],
    ["u_off · u_max", cfg ? `${fmtNumber(cfg.u_off, 2)} · ${fmtNumber(cfg.u_max, 2)}` : "—"],
    ["D_min · ΔD_update", cfg ? `${fmtNumber(cfg.d_min, 0)}% · ${fmtNumber(cfg.delta_d_update, 0)}%` : "—"],
    ["Batas data disebut terbaru (FRESHNESS_SECONDS)", `${ctrl.freshness_seconds ?? "—"} detik`],
    ["Batas data lama masih dipakai kipas (CONTROL_HOLD_SECONDS)", `${ctrl.control_hold_seconds ?? "—"} detik`],
    ["Umur data node penentu", ctrl.determining_data_age_seconds != null ? `${fmtNumber(ctrl.determining_data_age_seconds, 0)} detik` : "—"],
    ["Status perintah (backend)", esc(ctrl.fan_command_status ?? "—")],
    ["Versi konfigurasi", esc(ctrl.config_version ?? "—")],
    ["ID siklus", esc(ctrl.processing_cycle_id ?? "—")],
    ["Terakhir dievaluasi", ctrl.last_evaluated_at ? fmtClock(parseTs(ctrl.last_evaluated_at)) : "—"],
  ];
  const active = rules.filter((r) => (r.alpha ?? 0) > 0).sort((a, b) => b.alpha - a.alpha).slice(0, 10);
  const rulesHtml = active.length ? active.map((r) =>
    `<div class="settings-row"><span>Aturan ${esc(r.id)}: debu ${esc(r.dust)}, RH ${esc(r.rh)}, suhu ${esc(r.temp)} → ${esc(r.condition_class)} · kendali ${esc(r.control_level)}</span><strong>${(r.alpha * 100).toFixed(0)}%</strong></div>`).join("")
    : `<p style="color:var(--text-soft)">Tidak ada aturan aktif.</p>`;
  root.innerHTML = techDetails("pemetaan u → PWM, histeresis, dan aturan fuzzy node penentu",
    `<div class="settings-list">${rows.map(([k, v]) => `<div class="settings-row"><span>${k}</span><strong>${v}</strong></div>`).join("")}</div>
     <h4 style="margin:1rem 0 .4rem;font-size:.8rem;">Aturan fuzzy aktif pada node penentu</h4>
     <div class="settings-list">${rulesHtml}</div>`);
  root.querySelector("details").open = open;
}

// ── Kontrol admin ──────────────────────────────────────────────────────────
function renderAdmin(manual, ctrl) {
  $("admin-controls").hidden = !session.authenticated;
  $("admin-hint").hidden = session.authenticated;
  $("manual-auto").hidden = !manual;
  $("mode-pill").textContent = manual ? "Manual" : "Otomatis";
  $("mode-pill").className = manual ? "pill-warn" : "pill-good";
  $("mode-text").textContent = manual
    ? "Kecepatan kipas sedang diatur langsung oleh admin. Penilaian otomatis tetap berjalan di latar belakang."
    : "Kecepatan kipas diatur otomatis dari data sensor.";
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
  adminAction("/api/control/manual", { pwm_percent: v }, "Mode manual aktif", `Kecepatan ${v}% diterapkan.`);
});
$("manual-auto").addEventListener("click", () => {
  adminAction("/api/control/auto", {}, "Mode otomatis aktif", "Kecepatan kipas kembali diatur otomatis dari sensor.");
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
    $("zone-label").textContent = `Kecepatan kipas, ${zoneName(ctrl.zone_id)}`;

    const pill = $("fan-status");
    pill.className = "status-pill";
    const note = $("decision-note");
    if (unavailable) {
      pill.textContent = fanStatusLabel("Kendali tidak tersedia");
      pill.classList.add("unavailable");
      note.textContent = !ctrl.worker_alive ? "Pengolahan data sedang berhenti."
        : `Tidak ada data sensor dalam ${durationWords(ctrl.control_hold_seconds)} terakhir. Kipas diatur ke putaran terendah.`;
      fan.setTarget(0, true);
      $("pwm-value").textContent = "—";
    } else {
      pill.textContent = fanStatusLabel(ctrl.fan_command_status);
      if (ctrl.fan_command_status === "Mati") pill.classList.add("off");
      note.textContent = manual ? "Kecepatan sedang diatur langsung oleh admin."
        : ctrl.using_stale_data ? staleControlNote(ctrl)
        : ctrl.hysteresis_held ? "Kecepatan dipertahankan karena perubahan kebutuhan masih kecil."
        : Number(ctrl.pwm_command_percent) <= 0 ? "Kondisi ruangan tidak memerlukan kipas. Kipas berputar pelan pada pengaturan terendah."
        : "";
      fan.setTarget(ctrl.pwm_command_percent, false);
      $("pwm-value").textContent = `${fmtNumber(ctrl.pwm_command_percent, 0)}%`;
    }

    const hasAuto = ctrl.zone_control_level != null && !unavailable;
    $("stat-uzona").textContent = hasAuto ? needLabel(ctrl.zone_control_level, cfg) : "—";
    $("stat-node").textContent = hasAuto && ctrl.determining_node_id ? nodeName(ctrl.determining_node_id) : "—";
    $("stat-mode").textContent = manual ? "Manual" : "Otomatis";
    $("stat-time").textContent = ctrl.created_at ? fmtClock(parseTs(ctrl.created_at)) : "—";
    $("updated-at").textContent = ctrl.last_evaluated_at ? `Diperbarui ${fmtClock(parseTs(ctrl.last_evaluated_at))}` : "—";

    renderChain(ctrl, nodes, unavailable, manual);
    renderAdmin(manual, ctrl);
    setConnectionBadge(true, $("connection-badge"));

    const detail = hasAuto && ctrl.determining_node_id
      ? await apiFetch(`/api/fuzzy/${encodeURIComponent(ctrl.determining_node_id)}/detail`).catch(() => null)
      : null;
    renderTech(ctrl, detail?.active_rules ?? []);
  } catch (e) {
    setConnectionBadge(false, $("connection-badge"));
    showToast("Gagal memuat data kipas", e.message, "error");
  }
}

$("refresh-btn").addEventListener("click", fetchAll);
startPolling(fetchAll, 5000);
