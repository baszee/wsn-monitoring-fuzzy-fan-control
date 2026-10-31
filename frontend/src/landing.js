/* landing.js — hanya untuk beranda. Tidak memuat kode dashboard dan tidak memanggil API. */
import { applyBrand } from "/src/brand.js?v=1";

applyBrand();

const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
const hasIO = "IntersectionObserver" in window;
const flow = document.getElementById("flow");

/* Reveal saat scroll */
(function reveal() {
  const els = document.querySelectorAll(".reveal");
  if (reduceMotion || !hasIO) {
    els.forEach((e) => e.classList.add("in"));
    return;
  }
  const io = new IntersectionObserver(
    (entries) => {
      entries.forEach((en) => {
        if (!en.isIntersecting) return;
        en.target.classList.add("in");
        io.unobserve(en.target);
      });
    },
    { threshold: 0.12, rootMargin: "0px 0px -6% 0px" }
  );
  els.forEach((e) => io.observe(e));
})();

/* Menu aktif sesuai posisi scroll */
(function activeNav() {
  if (!hasIO) return;
  const links = [...document.querySelectorAll(".site-nav a")];
  const map = new Map(links.map((a) => [a.getAttribute("href").slice(1), a]));
  const io = new IntersectionObserver(
    (entries) => {
      entries.forEach((en) => {
        if (!en.isIntersecting) return;
        links.forEach((a) => a.removeAttribute("aria-current"));
        const a = map.get(en.target.id);
        if (a) a.setAttribute("aria-current", "true");
      });
    },
    { rootMargin: "-40% 0px -55% 0px" }
  );
  map.forEach((_, id) => { const s = document.getElementById(id); if (s) io.observe(s); });
})();

/* Jeda animasi ilustrasi saat tidak terlihat, atau bila gerak dikurangi */
(function pauseOffscreen() {
  const hero = document.querySelector(".hero");
  if (!hero || !flow) return;
  const setPaused = (p) => {
    hero.classList.toggle("paused", p);
    if (typeof flow.pauseAnimations === "function") p ? flow.pauseAnimations() : flow.unpauseAnimations();
  };
  if (reduceMotion) { setPaused(true); return; }
  if (hasIO) new IntersectionObserver(([e]) => setPaused(!e.isIntersecting)).observe(hero);
  document.addEventListener("visibilitychange", () => setPaused(document.hidden));
})();
