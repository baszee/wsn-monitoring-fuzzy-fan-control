/**
 * Komponen Panel Kendali Fan DC 12V & Animasi Baling-Baling SVG (requestAnimationFrame).
 */

let animationFrameId = null;
let currentRotation = 0;
let lastTimestamp = 0;

export function renderFanControlPanel(container, { controlData }) {
  const pwmPercent = controlData?.pwm_command_percent ?? 0.0;
  const statusCommand = controlData?.fan_command_status || 'Memuat...';
  const uZona = controlData?.zone_control_level !== null && controlData?.zone_control_level !== undefined
    ? controlData.zone_control_level.toFixed(1)
    : '--';
  const determiningNode = controlData?.determining_node_id || 'Tidak ada';

  let statusBadge = 'bg-slate-800 text-slate-400 border border-slate-700';
  if (statusCommand === 'Aktif') {
    statusBadge = 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 animate-pulse';
  } else if (statusCommand === 'Mati') {
    statusBadge = 'bg-slate-700/50 text-slate-400 border border-slate-600';
  } else if (statusCommand === 'Kendali tidak tersedia') {
    statusBadge = 'bg-amber-500/20 text-amber-400 border border-amber-500/40';
  }

  container.innerHTML = `
    <div class="glass-card rounded-2xl p-6 relative overflow-hidden flex flex-col justify-between h-full">
      <!-- Header Panel -->
      <div class="flex items-center justify-between mb-4">
        <div>
          <h2 class="text-lg font-bold text-white flex items-center gap-2">
            <span>Status Perintah Fan DC 12V</span>
          </h2>
          <p class="text-xs text-slate-400">Pengendali Terbuka (Open-Loop Actuator)</p>
        </div>
        <span class="px-3 py-1 rounded-full text-xs font-semibold ${statusBadge}">
          ${statusCommand}
        </span>
      </div>

      <!-- Main Visual Section (Fan SVG & Duty Cycle Gauge) -->
      <div class="flex flex-col sm:flex-row items-center justify-around gap-6 my-4">
        <!-- SVG Interactive Fan -->
        <div class="relative flex flex-col items-center">
          <div class="w-44 h-44 rounded-full bg-slate-900 border-2 border-slate-800 flex items-center justify-center p-3 relative shadow-inner">
            <!-- Protective Grill SVG -->
            <svg class="w-full h-full pointer-events-none absolute inset-0 z-10 opacity-30" viewBox="0 0 200 200">
              <circle cx="100" cy="100" r="90" fill="none" stroke="#64748b" stroke-width="2"/>
              <circle cx="100" cy="100" r="60" fill="none" stroke="#64748b" stroke-width="1.5" stroke-dasharray="4,4"/>
              <circle cx="100" cy="100" r="30" fill="none" stroke="#64748b" stroke-width="1.5"/>
              <line x1="10" y1="100" x2="190" y2="100" stroke="#64748b" stroke-width="1.5"/>
              <line x1="100" y1="10" x2="100" y2="190" stroke="#64748b" stroke-width="1.5"/>
            </svg>

            <!-- Rotating Fan Blades SVG -->
            <svg class="w-36 h-36" viewBox="0 0 200 200">
              <g id="fan-blades-group" transform="rotate(0 100 100)">
                <!-- 4 Blades -->
                <!-- Blade 1 -->
                <path d="M100 100 C95 60, 65 30, 95 15 C115 15, 115 55, 100 100 Z" fill="url(#bladeGrad1)"/>
                <!-- Blade 2 -->
                <path d="M100 100 C140 95, 170 65, 185 95 C185 115, 145 115, 100 100 Z" fill="url(#bladeGrad2)"/>
                <!-- Blade 3 -->
                <path d="M100 100 C105 140, 135 170, 105 185 C85 185, 85 145, 100 100 Z" fill="url(#bladeGrad1)"/>
                <!-- Blade 4 -->
                <path d="M100 100 C60 105, 30 135, 15 105 C15 85, 55 85, 100 100 Z" fill="url(#bladeGrad2)"/>
                <!-- Center Rotor Hub -->
                <circle cx="100" cy="100" r="22" fill="#0f172a" stroke="#0ea5e9" stroke-width="3"/>
                <circle cx="100" cy="100" r="8" fill="#38bdf8"/>
              </g>
              <defs>
                <linearGradient id="bladeGrad1" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stop-color="#38bdf8"/>
                  <stop offset="100%" stop-color="#0284c7"/>
                </linearGradient>
                <linearGradient id="bladeGrad2" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stop-color="#0ea5e9"/>
                  <stop offset="100%" stop-color="#0369a1"/>
                </linearGradient>
              </defs>
            </svg>
          </div>

          <!-- Peringatan Batasan Kejujuran Tampilan -->
          <span class="mt-2 text-[11px] font-semibold tracking-wide uppercase px-2 py-0.5 rounded bg-slate-900/90 text-sky-400 border border-slate-800">
            Ilustrasi Perintah PWM
          </span>
          <span class="text-[10px] text-slate-500 mt-0.5">(Tanpa sensor RPM fisik / Open-Loop)</span>
        </div>

        <!-- Metrics Display -->
        <div class="space-y-4 text-center sm:text-left">
          <!-- PWM Duty Cycle Value -->
          <div>
            <span class="text-xs text-slate-400 uppercase tracking-wider block">Perintah Duty Cycle PWM</span>
            <div class="flex items-baseline gap-1 justify-center sm:justify-start">
              <span class="font-mono font-extrabold text-4xl text-white">
                ${pwmPercent.toFixed(1)}
              </span>
              <span class="text-xl font-bold text-sky-400">%</span>
            </div>
            <!-- Progress Bar -->
            <div class="w-48 h-2 rounded-full bg-slate-800 mt-2 overflow-hidden">
              <div class="h-full bg-gradient-to-r from-sky-500 to-cyan-400 rounded-full transition-all duration-300" style="width: ${pwmPercent}%"></div>
            </div>
          </div>

          <!-- Ringkasan Nilai Zona -->
          <div class="grid grid-cols-2 gap-3 text-left pt-2 border-t border-slate-800">
            <div>
              <span class="text-[11px] text-slate-400 block">Tingkat Kendali Zona</span>
              <span class="font-mono font-bold text-sm text-sky-300">${uZona}</span>
            </div>
            <div>
              <span class="text-[11px] text-slate-400 block">Node Penentu</span>
              <span class="font-mono font-bold text-sm text-amber-300">${determiningNode}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Footer Info -->
      <div class="text-[11px] text-slate-500 border-t border-slate-800/80 pt-3 flex items-center justify-between">
        <span>Batas fan mati: 15 • Daya awal aktif: 30%</span>
        <span>Toleransi perubahan: 5%</span>
      </div>
    </div>
  `;

  // Jalankan animasi baling-baling menggunakan requestAnimationFrame
  startFanAnimation(pwmPercent);
}

function startFanAnimation(pwmPercent) {
  if (animationFrameId) {
    cancelAnimationFrame(animationFrameId);
  }

  // Rotasi derajat per detik proporsional dengan PWM (100% -> 720 deg/s / 2 putaran per detik)
  const targetSpeed = pwmPercent > 0 ? (pwmPercent / 100.0) * 720.0 : 0.0;
  let currentSpeed = targetSpeed;
  lastTimestamp = 0;

  function animate(timestamp) {
    if (!lastTimestamp) lastTimestamp = timestamp;
    const deltaSeconds = (timestamp - lastTimestamp) / 1000.0;
    lastTimestamp = timestamp;

    if (currentSpeed > 0) {
      currentRotation = (currentRotation + currentSpeed * deltaSeconds) % 360;
      const bladeGroup = document.getElementById('fan-blades-group');
      if (bladeGroup) {
        bladeGroup.setAttribute('transform', `rotate(${currentRotation} 100 100)`);
      }
      animationFrameId = requestAnimationFrame(animate);
    } else {
      animationFrameId = null;
    }
  }

  if (targetSpeed > 0) {
    animationFrameId = requestAnimationFrame(animate);
  }
}
