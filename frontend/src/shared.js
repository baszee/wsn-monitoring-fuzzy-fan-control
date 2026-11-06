/**
 * shared.js — Utilitas bersama seluruh halaman dashboard
 * Sidebar dinamis, toast, format helper, polling helper
 */


import { COLORS } from "/src/theme.js?v=20261106-3";
import { BRAND, brandLogoHTML } from "/src/brand.js?v=1";
import { icon, hydrateIcons } from "./icons.js";

// ─── Konfigurasi Sidebar ───────────────────────────────────────────────────
const NAV_ITEMS = [
  { group: "Monitoring", items: [
    { id: "ringkasan",   label: "Ringkasan",        href: "/dashboard/",            icon: "grid" },
    { id: "nodes",       label: "Node Sensor",      href: "/dashboard/nodes/",      icon: "radio" },
    { id: "fan",         label: "Fan & Kendali",    href: "/dashboard/fan/",        icon: "fan" },
    { id: "riwayat",     label: "Riwayat",          href: "/dashboard/history/",    icon: "bars" },
  ]},
  { group: "Analisis", items: [
    { id: "fuzzy",       label: "Analisis Fuzzy",   href: "/dashboard/fuzzy/",      icon: "activity" },
    { id: "simulasi",    label: "Simulasi What-If", href: "/dashboard/simulation/", icon: "flask" },
  ]},
  { group: "Sistem", items: [
    { id: "konfigurasi", label: "Konfigurasi",      href: "/dashboard/settings/",   icon: "settings" },
  ]},
];

/**
 * Bangun HTML sidebar dan injeksikan ke elemen target.
 * @param {string} activeId - id item aktif (misal "nodes", "fan")
 * @param {string} [targetSelector="#sidebar-root"] - selector elemen container
 */
export function buildSidebar(activeId, targetSelector = "#sidebar-root") {
  const root = document.querySelector(targetSelector);
  if (!root) return;

  const navHTML = NAV_ITEMS.map(({ group, items }) => {
    const linksHTML = items
      .map(({ id, label, href, icon: iconName }) => {
        const isActive = id === activeId;
        const badgeHTML = id === "nodes"
          ? `<em id="sidebar-node-badge" style="display:none;"></em>`
          : "";
        return `<a class="${isActive ? "active" : ""}" href="${href}" title="${label}" aria-label="${label}" aria-current="${isActive ? "page" : "false"}">${icon(iconName)}<span>${label}</span>${badgeHTML}</a>`;
      })
      .join("");
    return `<span class="nav-label">${group}</span>${linksHTML}`;
  }).join("");

  root.innerHTML = `
    <div class="sidebar-head">
      <a class="brand sidebar-brand" href="/" aria-label="${BRAND.name}, kembali ke beranda">${brandLogoHTML("full", "brand-logo brand-logo-sidebar")}${brandLogoHTML("mark", "brand-logo brand-logo-mark")}</a>
      <button class="rail-toggle" id="sidebar-toggle" type="button" aria-label="Ciutkan atau perluas navigasi" aria-expanded="true"><span class="ic">${icon("menu")}</span></button>
    </div>

    <div class="sidebar-zone">
      <span>Zona aktif</span>
      <strong id="sidebar-zone-name"><i></i> Zona</strong>
      <small id="sidebar-zone-count">Memuat...</small>
    </div>

    <nav class="side-nav" aria-label="Navigasi dashboard">
      ${navHTML}
    </nav>

    <div class="sidebar-footer">
      <a href="/dashboard/login/" id="admin-link" class="side-admin" title="Masuk admin"><span class="ic">${icon("lock")}</span><span class="lbl">Masuk admin</span></a>
      <a href="/" class="side-home" title="Kembali ke beranda"><span class="ic">${icon("arrow-left")}</span><span class="lbl">Kembali ke beranda</span></a>
    </div>
  `;

  _initAdminLink();
  _initModeBanner();

  // Update jumlah node dan badge secara dinamis dari API
  apiFetch("/api/nodes/latest")
    .then((nodes) => {
      const list = Array.isArray(nodes) ? nodes : (nodes.nodes ?? []);
      const count = list.length;
      const zoneEl = root.querySelector("#sidebar-zone-count");
      if (zoneEl) zoneEl.textContent = `${count} node terdaftar`;
      const zoneNameEl = root.querySelector("#sidebar-zone-name");
      if (zoneNameEl && list[0]?.zone_id) {
        zoneNameEl.innerHTML = `<i></i> ${list[0].zone_id}`;
      }
      const badgeEl = root.querySelector("#sidebar-node-badge");
      if (badgeEl && count > 0) {
        badgeEl.textContent = String(count);
        badgeEl.style.display = "";
      }
    })
    .catch(() => {});

  // Mobile sidebar toggle & collapsible rail
  _initRail();
  _initSidebarToggle();
}

function _initSidebarToggle() {
  const sidebar = document.getElementById("sidebar-root");
  const backdrop = document.getElementById("sidebar-backdrop");
  const menuBtn = document.getElementById("menu-button");
  if (!sidebar || !backdrop || !menuBtn) return;

  function open() {
    sidebar.classList.add("open");
    backdrop.classList.add("visible");
  }
  function close() {
    sidebar.classList.remove("open");
    backdrop.classList.remove("visible");
  }

  menuBtn.addEventListener("click", open);
  backdrop.addEventListener("click", close);
  sidebar.querySelectorAll("a").forEach((a) => a.addEventListener("click", close));
}

const RAIL_KEY = "wsn.sidebar.collapsed";

function _applyRail(collapsed) {
  document.body.classList.toggle("sidebar-collapsed", collapsed);
  const btn = document.getElementById("sidebar-toggle");
  if (btn) {
    btn.setAttribute("aria-expanded", String(!collapsed));
    btn.title = collapsed ? "Perluas navigasi" : "Ciutkan navigasi";
  }
}

function _initRail() {
  let collapsed = false;
  try { collapsed = localStorage.getItem(RAIL_KEY) === "1"; } catch {}
  _applyRail(collapsed);

  document.getElementById("sidebar-toggle")?.addEventListener("click", () => {
    // Di layar kecil, tombol ini menutup laci navigasi.
    if (window.matchMedia("(max-width: 980px)").matches) {
      document.getElementById("sidebar-root")?.classList.remove("open");
      document.getElementById("sidebar-backdrop")?.classList.remove("visible");
      return;
    }
    const next = !document.body.classList.contains("sidebar-collapsed");
    _applyRail(next);
    try { localStorage.setItem(RAIL_KEY, next ? "1" : "0"); } catch {}
  });
}

// ─── Sesi admin ────────────────────────────────────────────────────────────
let _session = null;

export async function getSession(force = false) {
  if (_session && !force) return _session;
  try { _session = await apiFetch("/api/auth/session"); }
  catch { _session = { authenticated: false }; }
  return _session;
}

/** POST ke endpoint admin dengan token CSRF dari sesi. */
export async function adminPost(path, body) {
  const s = await getSession();
  return apiFetch(path, {
    method: "POST",
    headers: { "X-CSRF-Token": s.csrf_token ?? "" },
    body: JSON.stringify(body ?? {}),
  });
}

export async function logoutAdmin() {
  try { await adminPost("/api/auth/logout"); } catch { /* sesi sudah berakhir */ }
  _session = null;
  location.href = "/dashboard/";
}

async function _initAdminLink() {
  const link = document.getElementById("admin-link");
  if (!link) return;
  const s = await getSession();
  if (!s.authenticated) return;
  link.title = `Keluar (${s.username})`;
  link.href = "#";
  link.innerHTML = `<span class="ic">${icon("log-out")}</span><span class="lbl">Keluar</span>`;
  link.addEventListener("click", (e) => { e.preventDefault(); logoutAdmin(); });
}

// ─── Banner MODE MANUAL (semua halaman dashboard) ──────────────────────────
function _initModeBanner() {
  const render = (c) => {
    let el = document.getElementById("mode-banner");
    if (c?.control_mode !== "manual") { el?.remove(); return; }
    if (!el) {
      const host = document.querySelector(".dashboard-main, .p2-main");
      if (!host) return;
      el = document.createElement("div");
      el.id = "mode-banner";
      el.className = "mode-banner";
      el.setAttribute("role", "status");
      host.insertBefore(el, host.firstChild);
    }
    el.innerHTML = `<strong>MODE MANUAL</strong><span>Perintah fan ditentukan admin. PWM otomatis saat ini ${fmtNumber(c.auto_pwm_percent, 1)}%.</span>`;
  };
  const tick = async () => { try { render(await apiFetch("/api/control/latest")); } catch { /* abaikan */ } };
  tick();
  visibleInterval(tick, 5000);
}

// ─── Toast ─────────────────────────────────────────────────────────────────
let _toastTimer = null;

/**
 * Tampilkan toast notifikasi.
 * @param {string} title
 * @param {string} message
 * @param {"info"|"success"|"warn"|"error"} type
 * @param {number} duration ms
 */
export function showToast(title, message, type = "info", duration = 3500) {
  const el = document.getElementById("toast");
  if (!el) return;
  const iconMap = { info: "info", success: "check", warn: "alert", error: "x" };
  el.querySelector("span").innerHTML = icon(iconMap[type] ?? "info");
  el.querySelector("#toast-title").textContent = title;
  el.querySelector("#toast-message").textContent = message;
  el.className = `toast toast-${type} show`;
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => el.classList.remove("show"), duration);
}

// ─── Format Helpers ────────────────────────────────────────────────────────
// SQLite mengirim waktu tanpa zona; anggap UTC supaya tidak bergeser 7 jam.
export function parseTs(v) {
  if (!v) return NaN;
  const s = String(v);
  return Date.parse(/(Z|[+-]\d{2}:?\d{2})$/.test(s) ? s : `${s}Z`);
}

export function fmtClock(ms, withSeconds = true) {
  if (!Number.isFinite(ms)) return "—";
  const d = new Date(ms), p = (n) => String(n).padStart(2, "0");
  return `${p(d.getHours())}:${p(d.getMinutes())}${withSeconds ? `:${p(d.getSeconds())}` : ""}`;
}

export function fmtTime(isoStr) {
  const ms = parseTs(isoStr);
  if (!Number.isFinite(ms)) return "—";
  return new Date(ms).toLocaleString("id-ID", { hour: "2-digit", minute: "2-digit", second: "2-digit", day: "2-digit", month: "short" });
}

export function fmtRelative(isoStr) {
  const ms = parseTs(isoStr);
  if (!Number.isFinite(ms)) return "—";
  const diff = Date.now() - ms;
  if (diff < 0) return "baru saja";
  if (diff < 60_000) return `${Math.floor(diff / 1000)} dtk lalu`;
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)} mnt lalu`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)} jam lalu`;
  return `${Math.floor(diff / 86_400_000)} hari lalu`;
}

export function fmtNumber(v, digits = 1) {
  if (v == null || v === "") return "—";
  const n = parseFloat(v);
  return Number.isNaN(n) ? "—" : n.toFixed(digits).replace(".", ",");
}

export function conditionClass(score) {
  if (score == null) return "unknown";
  if (score < 35) return "good";
  if (score < 65) return "warn";
  return "bad";
}

export function conditionLabel(classStr) {
  const map = { good: "Baik", warn: "Perlu Perhatian", bad: "Buruk", unknown: "—" };
  return map[classStr] ?? classStr;
}

export function conditionColor(classStr) {
  const map = { good: "#0f8a6a", warn: "#b76e00", bad: "#c94055", unknown: "#64748b" };
  return map[classStr] ?? "#64748b";
}

// ─── Normalisasi respons API & kualitas data ───────────────────────────────
export function normalizeNode(node = {}) {
  return {
    ...node,
    timestamp: node.source_timestamp ?? node.timestamp ?? null,
    // "valid" berarti lolos validasi M2 dan masih segar menurut backend
    is_valid: node.data_status ? node.data_status === "Valid" : (node.status_valid ?? false),
  };
}

export function normalizeControl(control = {}) {
  return {
    ...control,
    control_node_id: control.determining_node_id ?? control.control_node_id ?? null,
  };
}

// Status data dihitung backend (FRESHNESS_SECONDS). Frontend hanya menampilkan.
export function dataQuality(node = {}) {
  const table = {
    "Valid":          { key: "valid",   className: "pill-good" },
    "Data lama":      { key: "stale",   className: "pill-warn" },
    "Masukan tidak lengkap": { key: "incomplete", className: "pill-warn" },
    "Tidak valid":    { key: "invalid", className: "pill-bad" },
    "Tidak ada data": { key: "none",    className: "pill-unknown" },
  };
  const label = node.data_status ?? "Tidak ada data";
  return { ...(table[label] ?? table["Tidak ada data"]), label };
}

export function dataQualityPill(node) {
  const quality = dataQuality(node);
  return `<span class="${quality.className}">${quality.label}</span>`;
}

// ─── API Base ───────────────────────────────────────────────────────────────
const API_BASE = "";   // same origin; FastAPI serves both

export async function apiFetch(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers: { "Content-Type": "application/json", ...(options.headers ?? {}) } });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const d = err.detail;
    throw new Error((Array.isArray(d) ? d.map((x) => x.msg).join("; ") : d) ?? `HTTP ${res.status}`);
  }
  return res.json();
}

// ─── Connection Badge ──────────────────────────────────────────────────────
export function setConnectionBadge(ok, badgeEl) {
  if (!badgeEl) return;
  badgeEl.classList.toggle("offline", !ok);
  badgeEl.querySelector("span").textContent = ok ? "Terhubung" : "Tidak terhubung";
}

// ─── Polling Helper ────────────────────────────────────────────────────────
/**
 * Mulai polling periodik.
 * @param {Function} fetchFn - async fungsi yang dipanggil
 * @param {number} intervalMs
 * @returns {{ stop: Function }}
 */
export function startPolling(fetchFn, intervalMs = 8000) {
  fetchFn();
  return visibleInterval(fetchFn, intervalMs);
}

/**
 * Seperti setInterval, tetapi berhenti saat tab browser tidak aktif.
 * Begitu tab dibuka lagi, fungsi langsung dipanggil sekali lalu jadwal berlanjut.
 * @returns {{ stop: Function }}
 */
export function visibleInterval(fn, intervalMs) {
  let id = null;
  let stopped = false;
  const start = () => { if (id === null && !stopped) id = setInterval(fn, intervalMs); };
  const pause = () => { if (id !== null) { clearInterval(id); id = null; } };
  const onVisibility = () => {
    if (stopped) return;
    if (document.hidden) pause();
    else { fn(); start(); }
  };
  document.addEventListener("visibilitychange", onVisibility);
  if (!document.hidden) start();
  return { stop: () => { stopped = true; pause(); document.removeEventListener("visibilitychange", onVisibility); } };
}

// ─── Mini Sparkline SVG ────────────────────────────────────────────────────
export function drawSparkline(svgEl, values, color = COLORS.blue) {
  if (!svgEl || !values?.length) return;
  const W = 100, H = 28, PAD = 2;
  const min = Math.min(...values), max = Math.max(...values);
  const range = max - min || 1;
  const pts = values.map((v, i) => {
    const x = PAD + (i / (values.length - 1 || 1)) * (W - 2 * PAD);
    const y = H - PAD - ((v - min) / range) * (H - 2 * PAD);
    return `${x},${y}`;
  });
  svgEl.innerHTML = `<polyline fill="none" stroke="${color}" stroke-width="1.5" stroke-linejoin="round" points="${pts.join(" ")}"/>`;
}

// ─── Shared Topbar updater ─────────────────────────────────────────────────
export function setUpdatedAt(isoStr) {
  const el = document.getElementById("updated-at");
  if (el) el.textContent = isoStr ? `Diperbarui ${fmtRelative(isoStr)}` : "—";
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => hydrateIcons());
} else {
  hydrateIcons();
}
