/**
 * Komponen Panel Simulasi What-If (FR-14).
 * Memungkinkan pengujian interaktif masukan hipotetis tanpa efek ke aktuator fan.
 */

import { simulateFuzzy } from '../api.js';

export function renderSimulationPanel(container) {
  let tempVal = 24.0;
  let rhVal = 50.0;
  let dustRawVal = 0.15;
  let isSimulating = false;
  let simResult = null;

  function updateView() {
    container.innerHTML = `
      <div class="glass-card rounded-2xl p-6 space-y-6">
        <!-- Header -->
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800 pb-4">
          <div>
            <h2 class="text-lg font-bold text-white flex items-center gap-2">
              <span>Simulasi Interaktif "What-If"</span>
              <span class="text-xs px-2.5 py-0.5 rounded-full bg-cyan-950 text-cyan-400 border border-cyan-800">
                Mode Demo
              </span>
            </h2>
            <p class="text-xs text-slate-400">
              Uji coba kombinasi masukan sensor tanpa menyentuh perintah fan fisik maupun basis data
            </p>
          </div>
          <!-- Presets -->
          <div class="flex flex-wrap gap-2">
            <button data-preset="normal" class="px-2.5 py-1 rounded-lg text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 transition">
              Normal
            </button>
            <button data-preset="cold-dry" class="px-2.5 py-1 rounded-lg text-xs bg-slate-800 hover:bg-slate-700 text-cyan-300 transition" title="Bukti Pemisahan 2 Keluaran">
              Dingin & Kering
            </button>
            <button data-preset="heavy-dust" class="px-2.5 py-1 rounded-lg text-xs bg-slate-800 hover:bg-slate-700 text-rose-300 transition">
              Pekat Debu
            </button>
          </div>
        </div>

        <!-- Layout: 3 Sliders (Kiri) vs Hasil Simulasi (Kanan) -->
        <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <!-- Kolom Sliders -->
          <div class="lg:col-span-6 space-y-5 bg-slate-900/40 p-4 rounded-xl border border-slate-800/80">
            <!-- Slider Suhu -->
            <div class="space-y-1.5">
              <div class="flex justify-between text-xs">
                <span class="text-slate-300 font-semibold">Suhu (°C)</span>
                <span class="font-mono text-sky-400 font-bold" id="val-temp">${tempVal.toFixed(1)} °C</span>
              </div>
              <input 
                id="slider-temp" 
                type="range" 
                min="0" 
                max="50" 
                step="0.5" 
                value="${tempVal}" 
                class="w-full accent-sky-500 h-2 bg-slate-800 rounded-lg cursor-pointer"
              />
              <div class="flex justify-between text-[10px] text-slate-500">
                <span>0 °C (Rendah)</span>
                <span>18 - 30 °C (Normal)</span>
                <span>50 °C (Tinggi)</span>
              </div>
            </div>

            <!-- Slider RH -->
            <div class="space-y-1.5">
              <div class="flex justify-between text-xs">
                <span class="text-slate-300 font-semibold">Kelembapan Relatif / RH (%)</span>
                <span class="font-mono text-cyan-400 font-bold" id="val-rh">${rhVal.toFixed(1)} %</span>
              </div>
              <input 
                id="slider-rh" 
                type="range" 
                min="0" 
                max="100" 
                step="1" 
                value="${rhVal}" 
                class="w-full accent-cyan-500 h-2 bg-slate-800 rounded-lg cursor-pointer"
              />
              <div class="flex justify-between text-[10px] text-slate-500">
                <span>0 % (Kering)</span>
                <span>40 - 60 % (Normal)</span>
                <span>100 % (Lembap)</span>
              </div>
            </div>

            <!-- Slider Tegangan Sensor Debu -->
            <div class="space-y-1.5">
              <div class="flex justify-between text-xs">
                <span class="text-slate-300 font-semibold">Tegangan Sensor Debu (V)</span>
                <span class="font-mono text-amber-400 font-bold" id="val-dust">${dustRawVal.toFixed(2)} V</span>
              </div>
              <input 
                id="slider-dust" 
                type="range" 
                min="0.0" 
                max="3.5" 
                step="0.05" 
                value="${dustRawVal}" 
                class="w-full accent-amber-500 h-2 bg-slate-800 rounded-lg cursor-pointer"
              />
              <div class="flex justify-between text-[10px] text-slate-500">
                <span>0.05 V (Rendah)</span>
                <span>0.50 V (Sedang)</span>
                <span>3.50 V (Tinggi)</span>
              </div>
            </div>
          </div>

          <!-- Kolom Output Simulasi -->
          <div class="lg:col-span-6 bg-slate-900/40 p-4 rounded-xl border border-slate-800/80 flex flex-col justify-between">
            <span class="text-xs font-bold text-sky-400 uppercase tracking-wider block mb-3">
              Hasil Inferensi Simulasi
            </span>

            <div id="sim-output-container">
              ${renderSimOutput(simResult)}
            </div>

            <div class="mt-4 p-2.5 rounded-lg bg-slate-950/80 border border-slate-800 text-[11px] text-slate-400 text-center">
              Perhitungan menggunakan 27 aturan min-max dan centroid semesta 0-100 secara deterministik.
            </div>
          </div>
        </div>
      </div>
    `;

    bindEvents();
  }

  function renderSimOutput(res) {
    if (!res) {
      return `
        <div class="text-center py-8 text-slate-400 text-xs">
          Geser slider untuk melihat hasil inferensi real-time.
        </div>
      `;
    }

    const { condition_score, condition_class, control_level } = res.outputs;
    const dustIdx = res.simulated_inputs.dust_index ?? 0.0;

    let classColor = 'text-slate-300';
    let classBg = 'bg-slate-800';
    if (condition_class === 'Baik') {
      classColor = 'text-emerald-400';
      classBg = 'bg-emerald-500/20 border-emerald-500/40';
    } else if (condition_class === 'Perlu Perhatian') {
      classColor = 'text-amber-400';
      classBg = 'bg-amber-500/20 border-amber-500/40';
    } else if (condition_class === 'Buruk') {
      classColor = 'text-rose-400';
      classBg = 'bg-rose-500/20 border-rose-500/40';
    }

    // Hitung proyeksi PWM hipotetis jika kendali zona = control_level
    let simPwm = 0.0;
    if (control_level > 15.0) {
      simPwm = 30.0 + ((control_level - 15.0) / (88.33 - 15.0)) * 70.0;
      simPwm = Math.min(Math.max(simPwm, 30.0), 100.0);
    }

    return `
      <div class="space-y-4">
        <!-- Dual Output Badges -->
        <div class="grid grid-cols-2 gap-3">
          <div class="bg-slate-950/70 p-3 rounded-xl border border-slate-800 text-center">
            <span class="text-[11px] text-slate-400 block">Skor Kondisi</span>
            <span class="font-mono font-extrabold text-2xl text-white">${condition_score.toFixed(1)}</span>
            <div class="mt-1">
              <span class="px-2 py-0.5 rounded text-[11px] font-semibold border ${classBg} ${classColor}">
                ${condition_class}
              </span>
            </div>
          </div>

          <div class="bg-slate-950/70 p-3 rounded-xl border border-slate-800 text-center">
            <span class="text-[11px] text-slate-400 block">Tingkat Kendali</span>
            <span class="font-mono font-extrabold text-2xl text-cyan-400">${control_level.toFixed(1)}</span>
            <div class="mt-1">
              <span class="text-[11px] text-slate-400 font-mono">
                Proyeksi PWM: <b class="text-white">${simPwm.toFixed(1)}%</b>
              </span>
            </div>
          </div>
        </div>

        <!-- Info Tambahan Indeks & Aturan -->
        <div class="text-xs space-y-1.5 pt-2 border-t border-slate-800/80">
          <div class="flex justify-between">
            <span class="text-slate-400">Indeks Debu Ternormalisasi:</span>
            <span class="font-mono font-bold text-amber-300">${dustIdx.toFixed(3)}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-slate-400">Jumlah Aturan Terpicu:</span>
            <span class="font-mono font-bold text-sky-400">${res.active_rules.length} Aturan</span>
          </div>
        </div>
      </div>
    `;
  }

  async function triggerSimulation() {
    isSimulating = true;
    const res = await simulateFuzzy({
      temperature: tempVal,
      humidity: rhVal,
      dust_raw: dustRawVal,
      include_curves: false,
    });
    isSimulating = false;
    simResult = res;

    const outContainer = container.querySelector('#sim-output-container');
    if (outContainer) {
      outContainer.innerHTML = renderSimOutput(simResult);
    }
  }

  function bindEvents() {
    const sTemp = container.querySelector('#slider-temp');
    const sRh = container.querySelector('#slider-rh');
    const sDust = container.querySelector('#slider-dust');

    const vTemp = container.querySelector('#val-temp');
    const vRh = container.querySelector('#val-rh');
    const vDust = container.querySelector('#val-dust');

    let debounceTimer = null;
    const onSliderChange = () => {
      tempVal = parseFloat(sTemp.value);
      rhVal = parseFloat(sRh.value);
      dustRawVal = parseFloat(sDust.value);

      if (vTemp) vTemp.textContent = `${tempVal.toFixed(1)} °C`;
      if (vRh) vRh.textContent = `${rhVal.toFixed(1)} %`;
      if (vDust) vDust.textContent = `${dustRawVal.toFixed(2)} V`;

      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(triggerSimulation, 60);
    };

    if (sTemp) sTemp.addEventListener('input', onSliderChange);
    if (sRh) sRh.addEventListener('input', onSliderChange);
    if (sDust) sDust.addEventListener('input', onSliderChange);

    // Presets
    container.querySelectorAll('[data-preset]').forEach(btn => {
      btn.addEventListener('click', () => {
        const p = btn.getAttribute('data-preset');
        if (p === 'normal') {
          tempVal = 24.0; rhVal = 50.0; dustRawVal = 0.15;
        } else if (p === 'cold-dry') {
          tempVal = 10.0; rhVal = 20.0; dustRawVal = 0.05;
        } else if (p === 'heavy-dust') {
          tempVal = 28.0; rhVal = 55.0; dustRawVal = 3.20;
        }
        updateView();
        triggerSimulation();
      });
    });
  }

  // Initial render & initial simulation call
  updateView();
  triggerSimulation();
}
