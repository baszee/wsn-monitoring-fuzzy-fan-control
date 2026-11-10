/**
 * technical.js — Halaman "Detail teknis" (gabungan analisis fuzzy, kendali kipas,
 * simulasi, dan konfigurasi). Skrip ini memuat sidebar lebih dulu, mengatur
 * bagian yang dibuka lewat alamat (#fuzzy, #kendali, #simulasi, #konfigurasi),
 * dan mengisi bagian Kendali kipas.
 */
import { buildSidebar, apiFetch, fmtNumber, fmtClock, parseTs, startPolling } from "/src/shared.js?v=20261111-3";

buildSidebar("teknis");

const sections = [...document.querySelectorAll("details.tech-section")];

function openFromHash() {
  const id = location.hash.replace("#", "");
  const target = sections.find((d) => d.id === id);
  if (target) { target.open = true; target.scrollIntoView({ block: "start" }); }
}
sections.forEach((d) => d.addEventListener("toggle", () => {
  if (d.open && location.hash !== `#${d.id}`) history.replaceState(null, "", `${location.pathname}${location.search}#${d.id}`);
}));
window.addEventListener("hashchange", openFromHash);
openFromHash();

const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[c]));
let cfg = null;

async function renderControl() {
  const box = document.getElementById("control-tech");
  try {
    const ctrl = await apiFetch("/api/control/latest");
    if (!cfg) cfg = await apiFetch("/api/config/active").catch(() => null);
    const pct = (v, d = 1) => (v == null ? "—" : `${fmtNumber(v, d)}%`);
    const rows = [
      ["Mode", ctrl.control_mode === "manual" ? "Manual" : "Otomatis"],
      ["Tingkat kendali zona u_zona", ctrl.zone_control_level != null ? fmtNumber(ctrl.zone_control_level, 2) : "—"],
      ["Node penentu (u_i terbesar)", esc(ctrl.determining_node_id ?? "—")],
      ["Umur data node penentu", ctrl.determining_data_age_seconds != null ? `${fmtNumber(ctrl.determining_data_age_seconds, 0)} detik` : "—"],
      ["Memakai data lama", ctrl.using_stale_data ? "Ya" : "Tidak"],
      ["PWM hasil pemetaan (kandidat)", pct(ctrl.candidate_pwm_percent)],
      ["PWM sebelumnya", pct(ctrl.previous_pwm_percent)],
      ["PWM otomatis", pct(ctrl.auto_pwm_percent)],
      ["PWM yang dikirim ke kipas", pct(ctrl.pwm_command_percent)],
      ["Ditahan histeresis", ctrl.hysteresis_held ? "Ya" : "Tidak"],
      ["u_off · u_max", cfg ? `${fmtNumber(cfg.u_off, 2)} · ${fmtNumber(cfg.u_max, 2)}` : "—"],
      ["D_min · ΔD_update", cfg ? `${fmtNumber(cfg.d_min, 0)}% · ${fmtNumber(cfg.delta_d_update, 0)}%` : "—"],
      ["Rumus pemetaan", "D = D_min + clip((u − u_off)/(u_max − u_off), 0, 1) × (100 − D_min); u ≤ u_off → 0%"],
      ["Batas data disebut terbaru (FRESHNESS_SECONDS)", `${ctrl.freshness_seconds ?? "—"} detik`],
      ["Batas data lama masih dipakai (CONTROL_HOLD_SECONDS)", `${ctrl.control_hold_seconds ?? "—"} detik`],
      ["Status perintah (backend)", esc(ctrl.fan_command_status ?? "—")],
      ["Catatan uji fisik", "Pada PWM 0% kipas XF-120-K tetap berputar (putaran minimum)"],
      ["Versi konfigurasi", esc(ctrl.config_version ?? "—")],
      ["ID siklus", esc(ctrl.processing_cycle_id ?? "—")],
      ["Terakhir dievaluasi", ctrl.last_evaluated_at ? fmtClock(parseTs(ctrl.last_evaluated_at)) : "—"],
    ];
    box.innerHTML = rows.map(([k, v]) => `<div class="settings-row"><span>${k}</span><strong>${v}</strong></div>`).join("");
  } catch (e) {
    box.innerHTML = `<p style="color:var(--text-soft)">Data kendali belum dapat dimuat: ${esc(e.message)}</p>`;
  }
}
startPolling(renderControl, 5000);
