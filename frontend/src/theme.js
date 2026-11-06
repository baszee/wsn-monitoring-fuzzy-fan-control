/* theme.js — warna untuk JavaScript (grafik SVG, canvas kipas, kurva fuzzy).
   Nilainya harus sama dengan src/tokens.css. Atribut SVG dan canvas tidak
   bisa membaca variabel CSS dengan andal, jadi warnanya ditulis di sini. */
export const COLORS = {
  ink: "#18122b",
  blue: "#2f80ed",
  blueDark: "#1b54ad",
  cyan: "#0891b2",
  purple: "#5912ec",
  purpleDark: "#4a0fcb",
  purpleLight: "#7c4dff",
  purpleSoft: "#eee9ff",
  purpleSurface: "#f7f4ff",
  good: "#0f8a6a",
  warning: "#b76e00",
  danger: "#c94055",
  unknown: "#64748b",
  slate: "#94a3b8",
  grid: "#e2e8f0",
};

/* Warna garis per node. Sengaja tidak memakai hijau, kuning, merah (warna status)
   ataupun ungu (dicadangkan untuk hasil zona dan keputusan). */
export const NODE_PALETTE = ["#2f80ed", "#0891b2", "#64748b", "#1e3a8a"];

/* Garis hasil gabungan zona. */
export const ZONE_COLOR = COLORS.purple;
