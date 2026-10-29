/**
 * Komponen Header & Status Bar.
 */

export function renderHeader(container, { controlData, lastUpdated, isOnline, onRefresh }) {
  const statusColor = isOnline ? 'bg-emerald-500' : 'bg-rose-500';
  const statusText = isOnline ? 'Backend Terhubung' : 'Terputus';
  
  const zoneStatus = controlData?.control_status || 'Memuat...';
  let zoneBadgeClass = 'bg-slate-700 text-slate-300';
  if (zoneStatus === 'Aktif') zoneBadgeClass = 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40';
  else if (zoneStatus === 'Mati') zoneBadgeClass = 'bg-slate-700/50 text-slate-400 border border-slate-600';
  else if (zoneStatus === 'Kendali tidak tersedia') zoneBadgeClass = 'bg-amber-500/20 text-amber-400 border border-amber-500/40';

  const formattedTime = lastUpdated
    ? new Date(lastUpdated).toLocaleTimeString('id-ID', { hour12: false })
    : '--:--:--';

  container.innerHTML = `
    <header class="glass-panel sticky top-0 z-50 px-6 py-4 border-b border-slate-800">
      <div class="max-w-7xl mx-auto flex flex-col md:flex-row md:items-center justify-between gap-4">
        <!-- Title & Identitas -->
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-sky-600 to-cyan-400 flex items-center justify-center text-white shadow-lg shadow-sky-500/25">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/>
            </svg>
          </div>
          <div>
            <h1 class="text-xl font-bold bg-gradient-to-r from-white via-slate-100 to-slate-400 bg-clip-text text-transparent">
              WSN Environmental Monitoring & Fuzzy Fan Control
            </h1>
            <p class="text-xs text-slate-400">
              Subsistem Mahasiswa 3 • Teknik Komputer UNNES • Open-Loop DC 12V
            </p>
          </div>
        </div>

        <!-- Status Bar Controls -->
        <div class="flex flex-wrap items-center gap-3">
          <!-- Status Koneksi -->
          <div class="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900/80 border border-slate-800 text-xs">
            <span class="w-2 h-2 rounded-full ${statusColor} animate-pulse"></span>
            <span class="text-slate-300 font-medium">${statusText}</span>
          </div>

          <!-- Zona & Status Kendali -->
          <div class="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900/80 border border-slate-800 text-xs">
            <span class="text-slate-400">Zona:</span>
            <span class="font-semibold text-sky-400">${controlData?.zone_id || 'ZONA-1'}</span>
            <span class="px-2 py-0.5 rounded text-[11px] font-semibold ${zoneBadgeClass}">
              ${zoneStatus}
            </span>
          </div>

          <!-- Waktu Terakhir & Tombol Refresh -->
          <div class="flex items-center gap-2">
            <span class="text-xs text-slate-400">Pembaruan: <span class="text-slate-200 font-mono">${formattedTime}</span></span>
            <button id="btn-manual-refresh" class="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition" title="Picukan Siklus Segera">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
              </svg>
            </button>
          </div>
        </div>
      </div>
    </header>
  `;

  const refreshBtn = container.querySelector('#btn-manual-refresh');
  if (refreshBtn && onRefresh) {
    refreshBtn.addEventListener('click', onRefresh);
  }
}
