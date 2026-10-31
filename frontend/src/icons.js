// Ikon garis 24x24. Warna mengikuti currentColor.
const PATHS = {
  menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
  "arrow-left": '<path d="M19 12H5m6-6-6 6 6 6"/>',
  "arrow-right": '<path d="M5 12h14m-6-6 6 6-6 6"/>',
  "arrow-up-right": '<path d="M7 17 17 7M8 7h9v9"/>',
  "arrow-down": '<path d="M12 5v14m-6-6 6 6 6-6"/>',
  refresh: '<path d="M20 6v5h-5M4 18v-5h5M6.1 9a7 7 0 0 1 11.7-2.6L20 11M4 13l2.2 4.6A7 7 0 0 0 18 15"/>',
  thermometer: '<path d="M14 14.8V5a2 2 0 0 0-4 0v9.8a4 4 0 1 0 4 0Z"/>',
  droplet: '<path d="M12 3s6 6.2 6 10.5a6 6 0 0 1-12 0C6 9.2 12 3 12 3Z"/>',
  dust: '<circle cx="7" cy="8" r="1.5"/><circle cx="14" cy="6" r="1"/><circle cx="17" cy="12" r="1.8"/><circle cx="9" cy="14" r="1"/><circle cx="13" cy="18" r="1.5"/>',
  radio: '<circle cx="12" cy="12" r="3"/><path d="M5.6 18.4a9 9 0 0 1 0-12.8m12.8 0a9 9 0 0 1 0 12.8M8.5 15.5a5 5 0 0 1 0-7m7 0a5 5 0 0 1 0 7"/>',
  fan: '<circle cx="12" cy="12" r="2"/><path d="M12 10c-1-5 1-7 3-7 3 1 3 5-1 8m0 2c5-1 7 1 7 3-1 3-5 3-8-1m-2-1c1 5-1 7-3 7-3-1-3-5 1-8m1-2C5 12 3 10 3 8c1-3 5-3 8 1"/>',
  bars: '<path d="M4 19V9m5 10V5m5 14v-7m5 7V3"/>',
  activity: '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
  flask: '<path d="M9 3h6m-5 0v6l-5 9a2 2 0 0 0 2 3h10a2 2 0 0 0 2-3l-5-9V3M8 15h8"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a2 2 0 0 0 .4 2.2l.1.1-2.6 2.6-.1-.1a2 2 0 0 0-2.2-.4 2 2 0 0 0-1.2 1.8V21h-3.6v-.2A2 2 0 0 0 9 19a2 2 0 0 0-2.2.4l-.1.1-2.6-2.6.1-.1A2 2 0 0 0 4.6 15a2 2 0 0 0-1.8-1.2H3v-3.6h.2A2 2 0 0 0 5 9a2 2 0 0 0-.4-2.2l-.1-.1 2.6-2.6.1.1A2 2 0 0 0 9 4.6a2 2 0 0 0 1.2-1.8V3h3.6v.2A2 2 0 0 0 15 5a2 2 0 0 0 2.2-.4l.1-.1 2.6 2.6-.1.1a2 2 0 0 0-.4 2.2 2 2 0 0 0 1.8 1.2h.2v3.6h-.2A2 2 0 0 0 19.4 15Z"/>',
  grid: '<path d="M4 13h6V4H4v9Zm0 7h6v-4H4v4Zm10 0h6v-9h-6v9Zm0-16v4h6V4h-6Z"/>',
  check: '<path d="m5 12 5 5 9-10"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
  alert: '<path d="M10.3 4 2.6 17.5A2 2 0 0 0 4.3 20.5h15.4a2 2 0 0 0 1.7-3L13.7 4a2 2 0 0 0-3.4 0ZM12 10v4m0 3h.01"/>',
  x: '<path d="M6 6l12 12M18 6 6 18"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  target: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
  hash: '<path d="M5 9h14M5 15h14M10 4 8 20m8-16-2 16"/>',
  gauge: '<path d="M4 17a8 8 0 1 1 16 0"/><path d="M12 17l4-5"/>',
  repeat: '<path d="m17 2 4 4-4 4M3 11V9a3 3 0 0 1 3-3h15M7 22l-4-4 4-4m14-1v2a3 3 0 0 1-3 3H3"/>',
  leaf: '<path d="M5 19C5 10 10 5 20 5c0 10-5 15-14 15"/><path d="M5 19c2-5 5-8 9-10"/>',
  lock: '<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
  "log-out": '<path d="M10 17l-5-5 5-5M5 12h11M15 4h4a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1h-4"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
};

export function icon(name, cls = "") {
  const body = PATHS[name];
  if (!body) return "";
  return `<svg class="ic-svg ${cls}" viewBox="0 0 24 24" aria-hidden="true" focusable="false">${body}</svg>`;
}

// Mengganti <i data-icon="nama"></i> di HTML statis dengan SVG.
export function hydrateIcons(root = document) {
  root.querySelectorAll("[data-icon]:not([data-icon-ready])").forEach((el) => {
    el.innerHTML = icon(el.dataset.icon);
    el.classList.add("ic");
    el.dataset.iconReady = "1";
  });
}
