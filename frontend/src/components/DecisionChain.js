/**
 * Komponen Visualisasi Rantai Keputusan (Decision Chain Panel).
 * Menjelaskan alasan logis inferensi fuzzy hingga perintah PWM (FR-12).
 */

export function renderDecisionChain(container, { fuzzyDetail, selectedNodeId, isDetermining, pwmValue }) {
  if (!fuzzyDetail) {
    container.innerHTML = `
      <div class="glass-card rounded-2xl p-6 text-center text-slate-400">
        <p>Memuat rincian keputusan fuzzy untuk ${selectedNodeId || 'node penentu'}...</p>
      </div>
    `;
    return;
  }

  const { inputs, memberships, active_rules, outputs } = fuzzyDetail;

  // Derajat Keanggotaan Suhu, RH, Debu
  const renderMuBars = (muObj, title) => {
    return Object.entries(muObj).map(([label, val]) => {
      const pct = (val * 100).toFixed(0);
      return `
        <div class="space-y-1">
          <div class="flex justify-between text-[11px]">
            <span class="text-slate-300 font-medium">${label}</span>
            <span class="font-mono text-slate-400">${pct}%</span>
          </div>
          <div class="w-full h-1.5 rounded-full bg-slate-800 overflow-hidden">
            <div class="h-full bg-sky-500 rounded-full" style="width: ${pct}%"></div>
          </div>
        </div>
      `;
    }).join('');
  };

  // Kartu Aturan Aktif (alpha > 0)
  const rulesHtml = active_rules.map(r => `
    <div class="p-2.5 rounded-xl bg-slate-900/70 border border-slate-800 text-xs space-y-1">
      <div class="flex items-center justify-between">
        <span class="font-bold text-sky-400 font-mono">Aturan #${r.id}</span>
        <span class="px-2 py-0.5 rounded bg-sky-500/20 text-sky-300 font-mono text-[10px]">
          ${Math.round(r.alpha * 100)}%
        </span>
      </div>
      <p class="text-slate-300 text-[11px]">
        JIKA Debu <b class="text-amber-300">${r.dust}</b> & RH <b class="text-cyan-300">${r.rh}</b> & Suhu <b class="text-sky-300">${r.temp}</b>
      </p>
      <p class="text-slate-400 text-[10px]">
        MAKA Kondisi: <span class="text-emerald-300 font-semibold">${r.condition_class}</span> | Kendali: <span class="text-sky-300 font-semibold">${r.control_level}</span>
      </p>
    </div>
  `).join('');

  container.innerHTML = `
    <div class="glass-card rounded-2xl p-6 space-y-6">
      <!-- Header -->
      <div class="flex items-center justify-between border-b border-slate-800 pb-4">
        <div>
          <h2 class="text-lg font-bold text-white flex items-center gap-2">
            <span>Rantai Keputusan Logika Fuzzy</span>
            <span class="text-xs px-2.5 py-0.5 rounded-md bg-sky-950 text-sky-400 border border-sky-800 font-mono">
              ${selectedNodeId}
            </span>
          </h2>
          <p class="text-xs text-slate-400">Transparansi inferensi Mamdani & pemetaan PWM</p>
        </div>
        ${isDetermining ? `
          <span class="px-2.5 py-1 rounded-full text-xs font-bold bg-amber-500/20 text-amber-400 border border-amber-500/40">
            ★ Penentu Siklus Ini
          </span>
        ` : ''}
      </div>

      <!-- 4 Langkah Rantai Keputusan -->
      <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
        <!-- Langkah 1: Input & Fuzzifikasi -->
        <div class="bg-slate-900/50 p-4 rounded-xl border border-slate-800/80 space-y-3">
          <span class="text-xs font-bold text-sky-400 uppercase tracking-wider block">1. Fuzzifikasi</span>
          <div class="space-y-2">
            <span class="text-[10px] text-slate-500 uppercase tracking-wider block">Derajat Keanggotaan Suhu</span>
            ${renderMuBars(memberships.temperature, 'Suhu')}
          </div>
          <div class="space-y-2 pt-2 border-t border-slate-800/60">
            <span class="text-[10px] text-slate-500 uppercase tracking-wider block">Derajat Keanggotaan RH</span>
            ${renderMuBars(memberships.humidity, 'RH')}
          </div>
          <div class="space-y-2 pt-2 border-t border-slate-800/60">
            <span class="text-[10px] text-slate-500 uppercase tracking-wider block">Derajat Keanggotaan Debu</span>
            ${renderMuBars(memberships.dust, 'Debu')}
          </div>
        </div>

        <!-- Langkah 2: Aturan Aktif -->
        <div class="bg-slate-900/50 p-4 rounded-xl border border-slate-800/80 space-y-3 md:col-span-2">
          <div class="flex items-center justify-between">
            <span class="text-xs font-bold text-sky-400 uppercase tracking-wider">2. Aturan yang Memengaruhi Hasil</span>
            <span class="text-xs text-slate-400">${active_rules.length} Aturan Terpicu</span>
          </div>
          <div class="space-y-2 max-h-64 overflow-y-auto pr-1">
            ${rulesHtml}
          </div>
        </div>

        <!-- Langkah 3 & 4: Defuzzifikasi & Pemetaan PWM -->
        <div class="bg-slate-900/50 p-4 rounded-xl border border-slate-800/80 space-y-4">
          <div>
            <span class="text-xs font-bold text-sky-400 uppercase tracking-wider block mb-2">3. Defuzzifikasi</span>
            <div class="space-y-2 bg-slate-950/60 p-3 rounded-lg border border-slate-800">
              <div class="flex justify-between text-xs">
                <span class="text-slate-400">Skor Kondisi:</span>
                <span class="font-bold text-white font-mono">${outputs.condition_score}</span>
              </div>
              <div class="flex justify-between text-xs">
                <span class="text-slate-400">Kelas Kondisi:</span>
                <span class="font-bold text-sky-400">${outputs.condition_class}</span>
              </div>
              <div class="flex justify-between text-xs">
                <span class="text-slate-400">Tingkat Kendali:</span>
                <span class="font-bold text-cyan-300 font-mono">${outputs.control_level}</span>
              </div>
            </div>
          </div>

          <div class="pt-2 border-t border-slate-800">
            <span class="text-xs font-bold text-sky-400 uppercase tracking-wider block mb-2">4. Pemetaan PWM</span>
            <div class="bg-slate-950/60 p-3 rounded-lg border border-slate-800 space-y-1 text-xs">
              <div class="flex justify-between">
                <span class="text-slate-400">Duty Cycle:</span>
                <span class="font-mono font-bold text-emerald-400 text-sm">${pwmValue !== undefined ? pwmValue.toFixed(1) : '--'}%</span>
              </div>
              <p class="text-[10px] text-slate-500 pt-1">
                Perintah akhir disaring agar perubahan kecil tidak membuat fan sering naik-turun.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  `;
}
