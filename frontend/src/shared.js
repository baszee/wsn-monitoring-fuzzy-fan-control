/**
 * shared.js — Utilitas bersama seluruh halaman dashboard
 * Sidebar dinamis, toast, format helper, polling helper
 */

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
      <button class="rail-toggle" id="sidebar-toggle" type="button" aria-label="Ciutkan atau perluas navigasi" aria-expanded="true">${icon("menu")}</button>
      <a class="brand sidebar-brand" href="/">
        <span class="brand-mark" aria-hidden="true">
          <svg viewBox="0 0 32 32"><path d="M16 22V9m-5 13h10M12 9a4 4 0 0 1 8 0"/><path d="M8.8 12.2a9.5 9.5 0 0 1 14.4 0M5.5 8.7a14 14 0 0 1 21 0"/></svg>
        </span>
        <span><strong>WSN Monitor</strong><small>Monitoring dan kendali fan</small></span>
      </a>
    </div>

    <div class="sidebar-zone">
      <span>Zona aktif</span>
      <strong><i></i> Zona 1</strong>
      <small id="sidebar-zone-count">Memuat...</small>
    </div>

    <nav class="side-nav" aria-label="Navigasi dashboard">
      ${navHTML}
    </nav>

    <div class="sidebar-footer">
      <a href="/" title="Kembali ke beranda">${icon("arrow-left")} <span class="lbl">Kembali ke beranda</span></a>
      <small>Prototipe penelitian</small>
    </div>
  `;

  // Update jumlah node dan badge secara dinamis dari API
  apiFetch("/api/nodes/latest")
    .then((nodes) => {
      const list = Array.isArray(nodes) ? nodes : (nodes.nodes ?? []);
      const count = list.length;
      const zoneEl = root.querySelector("#sidebar-zone-count");
      if (zoneEl) zoneEl.textContent = `${count} node terdaftar`;
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
export function fmtTime(isoStr) {
  if (!isoStr) return "—";
  const d = new Date(isoStr);
  if (isNaN(d)) return "—";
  return d.toLocaleString("id-ID", { hour: "2-digit", minute: "2-digit", second: "2-digit", day: "2-digit", month: "short" });
}

export function fmtRelative(isoStr) {
  if (!isoStr) return "—";
  const diff = Date.now() - new Date(isoStr).getTime();
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
  const map = { good: "#16a34a", warn: "#d97706", bad: "#dc2626", unknown: "#6b7280" };
  return map[classStr] ?? "#6b7280";
}

// ─── Normalisasi respons API & kualitas data ───────────────────────────────
export function normalizeNode(node = {}) {
  return {
    ...node,
    timestamp: node.source_timestamp ?? node.timestamp ?? null,
    is_valid: node.status_valid ?? node.is_valid ?? false,
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
    throw new Error(err.detail ?? `HTTP ${res.status}`);
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
  const id = setInterval(fetchFn, intervalMs);
  return { stop: () => clearInterval(id) };
}

// ─── Mini Sparkline SVG ────────────────────────────────────────────────────
export function drawSparkline(svgEl, values, color = "#2563EB") {
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
