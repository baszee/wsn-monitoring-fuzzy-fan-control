/**
 * shared.js — Utilitas bersama seluruh halaman dashboard
 * Sidebar dinamis, toast, format helper, polling helper
 */

// ─── Konfigurasi Sidebar ───────────────────────────────────────────────────
const NAV_ITEMS = [
  {
    group: "Monitoring",
    items: [
      { id: "ringkasan",  label: "Ringkasan",       href: "/dashboard/",              icon: `<svg viewBox="0 0 24 24"><path d="M4 13h6V4H4v9Zm0 7h6v-4H4v4Zm10 0h6v-9h-6v9Zm0-16v4h6V4h-6Z"/></svg>` },
      { id: "nodes",      label: "Node Sensor",     href: "/dashboard/nodes/",        icon: `<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M5.6 18.4a9 9 0 0 1 0-12.8m12.8 0a9 9 0 0 1 0 12.8M8.5 15.5a5 5 0 0 1 0-7m7 0a5 5 0 0 1 0 7"/></svg>`, badge: null },
      { id: "fan",        label: "Fan & Kendali",   href: "/dashboard/fan/",          icon: `<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="2"/><path d="M12 10c-1-5 1-7 3-7 3 1 3 5-1 8m0 2c5-1 7 1 7 3-1 3-5 3-8-1m-2-1c1 5-1 7-3 7-3-1-3-5 1-8m1-2C5 12 3 10 3 8c1-3 5-3 8 1"/></svg>` },
      { id: "riwayat",    label: "Riwayat",         href: "/dashboard/history/",      icon: `<svg viewBox="0 0 24 24"><path d="M4 19V9m5 10V5m5 14v-7m5 7V3"/></svg>` },
    ],
  },
  {
    group: "Analisis",
    items: [
      { id: "fuzzy",      label: "Analisis Fuzzy",  href: "/dashboard/fuzzy/",        icon: `<svg viewBox="0 0 24 24"><path d="M4 16c3-7 5-9 8-9s5 2 8 9M4 12h16M8 5v14m8-14v14"/></svg>` },
      { id: "simulasi",   label: "Simulasi What-If",href: "/dashboard/simulation/",   icon: `<svg viewBox="0 0 24 24"><path d="M9 3h6m-5 0v6l-5 9a2 2 0 0 0 2 3h10a2 2 0 0 0 2-3l-5-9V3M8 15h8"/></svg>` },
    ],
  },
  {
    group: "Sistem",
    items: [
      { id: "konfigurasi",label: "Konfigurasi",     href: "/dashboard/settings/",     icon: `<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a2 2 0 0 0 .4 2.2l.1.1-2.6 2.6-.1-.1a2 2 0 0 0-2.2-.4 2 2 0 0 0-1.2 1.8V21h-3.6v-.2A2 2 0 0 0 9 19a2 2 0 0 0-2.2.4l-.1.1-2.6-2.6.1-.1A2 2 0 0 0 4.6 15a2 2 0 0 0-1.8-1.2H3v-3.6h.2A2 2 0 0 0 5 9a2 2 0 0 0-.4-2.2l-.1-.1 2.6-2.6.1.1A2 2 0 0 0 9 4.6a2 2 0 0 0 1.2-1.8V3h3.6v.2A2 2 0 0 0 15 5a2 2 0 0 0 2.2-.4l.1-.1 2.6 2.6-.1.1a2 2 0 0 0-.4 2.2 2 2 0 0 0 1.8 1.2h.2v3.6h-.2A2 2 0 0 0 19.4 15Z"/></svg>` },
    ],
  },
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
      .map(({ id, label, href, icon, badge }) => {
        const isActive = id === activeId;
        const badgeHTML = badge != null ? `<em>${badge}</em>` : "";
        return `<a class="${isActive ? "active" : ""}" href="${href}" aria-current="${isActive ? "page" : "false"}">${icon}<span>${label}</span>${badgeHTML}</a>`;
      })
      .join("");
    return `<span class="nav-label">${group}</span>${linksHTML}`;
  }).join("");

  root.innerHTML = `
    <a class="brand sidebar-brand" href="/">
      <span class="brand-mark" aria-hidden="true">
        <svg viewBox="0 0 32 32"><path d="M16 22V9m-5 13h10M12 9a4 4 0 0 1 8 0"/><path d="M8.8 12.2a9.5 9.5 0 0 1 14.4 0M5.5 8.7a14 14 0 0 1 21 0"/></svg>
      </span>
      <span><strong>WSN Monitor</strong><small>Control center</small></span>
    </a>

    <div class="sidebar-zone">
      <span>Zona aktif</span>
      <strong><i></i> Zona 1</strong>
      <small>3 node terdaftar</small>
    </div>

    <nav class="side-nav" aria-label="Navigasi dashboard">
      ${navHTML}
    </nav>

    <div class="sidebar-footer">
      <a href="/"><span>←</span> Kembali ke beranda</a>
      <small>Versi prototipe 0.1.0</small>
    </div>
  `;

  // Mobile sidebar toggle
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
  const iconMap = { info: "ℹ", success: "✓", warn: "⚠", error: "✕" };
  el.querySelector("span").textContent = iconMap[type] ?? "ℹ";
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
  return isNaN(n) ? "—" : n.toFixed(digits);
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
// Satu sumber kebenaran untuk nama field backend agar semua halaman konsisten.
export const STALE_AFTER_MS = 10 * 60 * 1000;

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

export function dataQuality(node = {}, staleAfterMs = STALE_AFTER_MS) {
  const item = normalizeNode(node);
  const required = [item.temperature, item.humidity, item.dust_index];
  const incomplete = required.some((value) => value == null || !Number.isFinite(Number(value)));
  const time = item.timestamp ? new Date(item.timestamp).getTime() : NaN;
  const stale = Number.isFinite(time) && Date.now() - time > staleAfterMs;

  if (!item.is_valid) return { key: "invalid", label: "Tidak valid", className: "pill-bad" };
  if (incomplete) return { key: "incomplete", label: "Belum lengkap", className: "pill-warn" };
  if (!Number.isFinite(time) || stale) return { key: "stale", label: "Data lama", className: "pill-warn" };
  return { key: "valid", label: "Valid", className: "pill-good" };
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
  badgeEl.className = `data-badge ${ok ? "badge-ok" : "badge-err"}`;
  badgeEl.querySelector("i").textContent = ok ? "●" : "●";
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
