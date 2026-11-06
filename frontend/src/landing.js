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

/* Ilustrasi alur: pilih bagian untuk melihat perannya */
(function flowSelect() {
  const stage = document.querySelector(".stage");
  const note = document.getElementById("flow-note");
  if (!flow || !stage || !note) return;
  const INFO = {
    node: { title: "Node sensor.", routes: ["A", "B"], text: "Membaca suhu, kelembapan, tekanan udara, dan debu, lalu mengirimkannya lewat sinyal radio LoRa 433 MHz." },
    penerima: { title: "Penerima.", routes: ["A", "B", "C"], text: "Orange Pi menerima paket LoRa, memeriksa datanya, lalu menyimpannya ke PostgreSQL." },
    dashboard: { title: "Dashboard.", routes: ["C", "D"], text: "Menampilkan data tiap node dan menilai kondisinya: Baik, Perlu Perhatian, atau Buruk." },
    kipas: { title: "Kipas.", routes: ["D"], text: "Node yang paling perlu ditangani menentukan daya kipas (PWM) pada zona." },
  };
  const hint = note.textContent;
  const count = document.getElementById("flow-count");
  const ORDER = ["node", "penerima", "dashboard", "kipas"];
  const parts = [...flow.querySelectorAll(".hit")];
  const routes = [...flow.querySelectorAll(".route")];
  let current = null;

  function select(key) {
    current = key;
    parts.forEach((p) => {
      const on = p.dataset.key === key;
      p.classList.toggle("sel", on);
      p.setAttribute("aria-pressed", on ? "true" : "false");
    });
    routes.forEach((r) => r.classList.toggle("on", !!key && INFO[key].routes.includes(r.dataset.r)));
    if (count) count.textContent = (key ? ORDER.indexOf(key) + 1 : 0) + " / 4";
    note.textContent = "";
    if (key) {
      stage.dataset.sel = key;
      const b = document.createElement("b");
      b.textContent = INFO[key].title;
      note.append(b, " " + INFO[key].text);
    } else {
      delete stage.dataset.sel;
      note.textContent = hint;
    }
  }
  const toggle = (key) => select(current === key ? null : key);
  const step = (d) => {
    const i = current ? ORDER.indexOf(current) : (d > 0 ? -1 : 0);
    select(ORDER[(i + d + ORDER.length) % ORDER.length]);
  };
  const prev = document.getElementById("flow-prev");
  const next = document.getElementById("flow-next");
  if (prev) prev.addEventListener("click", () => step(-1));
  if (next) next.addEventListener("click", () => step(1));

  parts.forEach((p) => {
    p.addEventListener("click", () => toggle(p.dataset.key));
    p.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(p.dataset.key); }
    });
  });
})();

/* Statistik hero: tekan untuk penjelasan satu kalimat */
(function heroFacts() {
  const btns = [...document.querySelectorAll(".fact")];
  const note = document.getElementById("fact-note");
  if (!btns.length || !note) return;
  const hint = note.textContent;
  btns.forEach((b) => b.addEventListener("click", () => {
    const on = b.getAttribute("aria-pressed") !== "true";
    btns.forEach((x) => x.setAttribute("aria-pressed", x === b && on ? "true" : "false"));
    note.textContent = on ? b.dataset.note : hint;
  }));
})();

/* Cara kerja: pilih tahap 1 sampai 4 */
(function stepRail() {
  const rail = document.getElementById("rail");
  if (!rail) return;
  const btns = [...rail.querySelectorAll(".rail-step")];
  const cards = [...document.querySelectorAll(".steps .step")];
  function pick(n) {
    rail.style.setProperty("--p", String(n - 1));
    rail.dataset.tone = n >= 3 ? "purple" : "blue";
    btns.forEach((b, i) => {
      b.classList.toggle("is-active", i + 1 === n);
      b.classList.toggle("is-done", i + 1 < n);
      b.setAttribute("aria-pressed", i + 1 === n ? "true" : "false");
    });
    cards.forEach((c, i) => c.classList.toggle("is-active", i + 1 === n));
  }
  btns.forEach((b, i) => b.addEventListener("click", () => pick(i + 1)));
  cards.forEach((c, i) => c.addEventListener("click", () => pick(i + 1)));
  pick(1);
})();

/* Menu untuk HP dan tablet */
(function mobileMenu() {
  const header = document.querySelector(".site-header");
  const btn = document.querySelector(".nav-toggle");
  const nav = document.getElementById("site-nav");
  if (!header || !btn || !nav) return;
  const isOpen = () => header.classList.contains("menu-open");
  const set = (open) => {
    header.classList.toggle("menu-open", open);
    btn.setAttribute("aria-expanded", open ? "true" : "false");
    btn.setAttribute("aria-label", open ? "Tutup menu" : "Buka menu");
  };
  btn.addEventListener("click", () => set(!isOpen()));
  nav.addEventListener("click", (e) => { if (e.target.closest("a")) set(false); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && isOpen()) { set(false); btn.focus(); } });
  document.addEventListener("click", (e) => { if (isOpen() && !header.contains(e.target)) set(false); });
  const mq = matchMedia("(min-width: 861px)");
  const onChange = (e) => { if (e.matches) set(false); };
  if (mq.addEventListener) mq.addEventListener("change", onChange); else if (mq.addListener) mq.addListener(onChange);
})();
