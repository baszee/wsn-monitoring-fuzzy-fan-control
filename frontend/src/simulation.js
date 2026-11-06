/**
 * simulation.js — Halaman Simulasi What-If Fuzzy
 * Interaktif tanpa memicu aktuator fan
 */
import {
  buildSidebar,
  showToast,
  apiFetch,
  fmtNumber,
  conditionClass,
  conditionLabel,
} from "/src/shared.js?v=20261106-3";

buildSidebar("simulasi");

// ── Elements ───────────────────────────────────────────────────────────────
const tempInput  = document.getElementById("sim-temp");
const rhInput    = document.getElementById("sim-rh");
const dustInput  = document.getElementById("sim-dust");

const valTemp    = document.getElementById("val-temp");
const valRh      = document.getElementById("val-rh");
const valDust    = document.getElementById("val-dust");

const resScore   = document.getElementById("res-score");
const resClass   = document.getElementById("res-class");
const resControl = document.getElementById("res-control");
const resPwm     = document.getElementById("res-pwm");

const mfBadgesEl = document.getElementById("sim-mf-badges");
const rulesListEl= document.getElementById("sim-rules-list");
const rulesCountEl=document.getElementById("active-rules-count");
const resetBtn   = document.getElementById("reset-btn");

// ── Debounced Simulation API Call ──────────────────────────────────────────
let debounceTimer = null;

function requestSimulation() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(runSimulation, 150);
}

async function runSimulation() {
  const temperature = parseFloat(tempInput.value);
  const humidity    = parseFloat(rhInput.value);
  const dust_index  = parseFloat(dustInput.value);

  valTemp.textContent = `${temperature.toFixed(1)} °C`;
  valRh.textContent   = `${Math.round(humidity)} %`;
  valDust.textContent = dust_index.toFixed(3);

  try {
    const res = await apiFetch("/api/fuzzy/simulate", {
      method: "POST",
      body: JSON.stringify({
        temperature,
        humidity,
        dust_index,
        include_curves: false,
      }),
    });

    renderResults(res);
  } catch (err) {
    showToast("Simulasi Gagal", err.message, "error");
  }
}

// ── Render Simulation Results ──────────────────────────────────────────────
function renderResults(res) {
  const score = res.outputs?.condition_score;
  const ctrl  = res.outputs?.control_level;
  const cls   = res.outputs?.condition_class;

  resScore.textContent   = fmtNumber(score, 1);
  resControl.textContent = fmtNumber(ctrl, 1);

  const condCls = conditionClass(score);
  resClass.innerHTML = `<span class="pill-${condCls}">${cls || conditionLabel(condCls)}</span>`;

  // PWM Calculation
  const candPWM = Number(res.candidate_pwm_percent ?? 0);
  if (candPWM === 0.0) {
    resPwm.innerHTML = `0.0% <span style="font-size:0.75rem;font-weight:400;color:var(--text-soft);">(Fan Mati)</span>`;
  } else {
    resPwm.innerHTML = `${candPWM.toFixed(1)}% <span style="font-size:0.75rem;font-weight:400;color:var(--text-soft);">(Fan Aktif)</span>`;
  }

  // Membership degrees badges
  const mfEntries = [];
  if (res.memberships) {
    if (res.memberships.temperature) {
      for (const [k, v] of Object.entries(res.memberships.temperature)) {
        if (v > 0) mfEntries.push(`Suhu ${k}: ${Math.round(v * 100)}%`);
      }
    }
    if (res.memberships.humidity) {
      for (const [k, v] of Object.entries(res.memberships.humidity)) {
        if (v > 0) mfEntries.push(`Kelembapan ${k}: ${Math.round(v * 100)}%`);
      }
    }
    if (res.memberships.dust) {
      for (const [k, v] of Object.entries(res.memberships.dust)) {
        if (v > 0) mfEntries.push(`Debu ${k}: ${Math.round(v * 100)}%`);
      }
    }
  }

  if (mfEntries.length) {
    mfBadgesEl.innerHTML = mfEntries
      .map((txt) => `<span class="mf-badge">${txt}</span>`)
      .join("");
  } else {
    mfBadgesEl.innerHTML = `<span style="font-size:0.75rem;color:var(--text-soft);">Tidak ada derajat keanggotaan aktif</span>`;
  }

  // Active rules
  const activeRules = (res.active_rules || []).filter((r) => (r.alpha ?? 0) > 0);
  rulesCountEl.textContent = `${activeRules.length} aturan aktif`;

  if (!activeRules.length) {
    rulesListEl.innerHTML = `<div class="sim-empty">Tidak ada aturan yang terpicu pada skenario ini.</div>`;
    return;
  }

  // Sort descending by alpha
  activeRules.sort((a, b) => b.alpha - a.alpha);

  rulesListEl.innerHTML = activeRules
    .map((r) => {
      const alphaPct = Math.round(r.alpha * 100);
      return `
        <div class="sim-rule-row active">
          <span class="sim-rule-alpha">${alphaPct}%</span>
          <div class="sim-rule-text">
            <strong>Aturan ${r.id}:</strong> Suhu ${r.temp}, kelembapan ${r.rh}, debu ${r.dust}, Hasil: kondisi <strong>${r.condition_class}</strong>, kendali <strong>${r.control_level}</strong>
          </div>
          <div class="sim-alpha-bar-wrap">
            <div class="sim-alpha-bar" style="width: ${alphaPct}%;"></div>
          </div>
        </div>
      `;
    })
    .join("");
}

// ── Slider Listeners ───────────────────────────────────────────────────────
[tempInput, rhInput, dustInput].forEach((input) => {
  input.addEventListener("input", () => {
    valTemp.textContent = `${parseFloat(tempInput.value).toFixed(1)} °C`;
    valRh.textContent   = `${Math.round(rhInput.value)} %`;
    valDust.textContent = parseFloat(dustInput.value).toFixed(3);
    requestSimulation();
  });
});

// ── Presets ────────────────────────────────────────────────────────────────
document.querySelectorAll(".sim-preset-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    tempInput.value = btn.dataset.t;
    rhInput.value   = btn.dataset.rh;
    dustInput.value = btn.dataset.d;
    requestSimulation();
  });
});

// ── Reset ──────────────────────────────────────────────────────────────────
resetBtn.addEventListener("click", () => {
  tempInput.value = 28.0;
  rhInput.value   = 55;
  dustInput.value = 0.25;
  requestSimulation();
  showToast("Reset Berhasil", "Slider simulasi dikembalikan ke nilai default.", "info");
});

// Run initial simulation
runSimulation();
