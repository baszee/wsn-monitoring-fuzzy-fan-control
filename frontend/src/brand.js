/**
 * brand.js - satu-satunya tempat nama dan logo aplikasi.
 * Untuk mengganti nama atau logo, ubah objek BRAND di bawah, lalu ganti
 * berkas di src/brand/ bila perlu. Halaman lain hanya membaca berkas ini.
 */
export const BRAND = {
  name: "WSNova",
  tagline: "Monitoring lingkungan dan kendali fan",
  logo: {
    full: "/src/brand/wsnova-full-on-light.svg",
    fullLight: "/src/brand/wsnova-full-on-dark.svg",
    mark: "/src/brand/wsnova-mark.svg",
    markLight: "/src/brand/wsnova-mark.svg",
  },
  favicon: "/src/brand/wsnova-favicon.svg",
  touchIcon: "/src/brand/apple-touch-icon.png",
};

/** Markup <img> logo, dipakai oleh sidebar yang dibuat lewat JavaScript. */
export function brandLogoHTML(kind = "full", className = "brand-logo") {
  const src = BRAND.logo[kind] || BRAND.logo.full;
  return `<img class="${className}" data-brand-logo="${kind}" src="${src}" alt="${BRAND.name}" />`;
}

function setLink(rel, href, type) {
  let el = document.querySelector(`link[rel="${rel}"]`);
  if (!el) {
    el = document.createElement("link");
    el.rel = rel;
    document.head.appendChild(el);
  }
  if (type) el.type = type;
  el.href = href;
}

/**
 * Menerapkan brand ke halaman: logo, teks nama, favicon, dan judul tab.
 * Aman dipanggil berulang. Markup statis sudah berisi nilai awal, jadi
 * halaman tetap benar walaupun fungsi ini belum sempat berjalan.
 */
export function applyBrand(root = document) {
  root.querySelectorAll("[data-brand-logo]").forEach((img) => {
    const kind = img.getAttribute("data-brand-logo");
    img.src = BRAND.logo[kind] || BRAND.logo.full;
    img.alt = BRAND.name;
  });
  root.querySelectorAll("[data-brand-name]").forEach((el) => {
    el.textContent = BRAND.name;
  });
  root.querySelectorAll("[data-brand-tagline]").forEach((el) => {
    el.textContent = BRAND.tagline;
  });
  setLink("icon", BRAND.favicon, "image/svg+xml");
  setLink("apple-touch-icon", BRAND.touchIcon);

  // Judul tab: "<Halaman> \u2014 <Nama>". Pada halaman yang nama brandnya
  // di depan (beranda), <title data-brand-first> menandai posisinya.
  const titleEl = document.querySelector("title");
  const parts = document.title.split(" \u2014 ");
  if (titleEl && parts.length > 1) {
    const first = titleEl.hasAttribute("data-brand-first");
    parts[first ? 0 : parts.length - 1] = BRAND.name;
    document.title = parts.join(" \u2014 ");
  }
}
