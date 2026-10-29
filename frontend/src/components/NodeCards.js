/**
 * Komponen Kartu Parameter & Tabel Node Sensor.
 */

export function renderNodeCards(container, { nodes, selectedNodeId, onSelectNode }) {
  if (!nodes || nodes.length === 0) {
    container.innerHTML = `
      <div class="glass-card rounded-2xl p-6 text-center text-slate-400">
        <p>Tidak ada node sensor yang terdaftar atau data belum tersedia.</p>
      </div>
    `;
    return;
  }

  const cardsHtml = nodes.map(node => {
    const isDetermining = node.is_determining_node;
    const isSelected = node.node_id === selectedNodeId;

    // Kelas Kondisi Color Badge
    let classBadge = 'bg-slate-700 text-slate-300';
    let borderHighlight = isSelected ? 'border-sky-500 ring-2 ring-sky-500/30' : 'border-slate-800';
    
    if (node.condition_class === 'Baik') {
      classBadge = 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40';
    } else if (node.condition_class === 'Perlu Perhatian') {
      classBadge = 'bg-amber-500/20 text-amber-400 border border-amber-500/40';
    } else if (node.condition_class === 'Buruk') {
      classBadge = 'bg-rose-500/20 text-rose-400 border border-rose-500/40';
    }

    if (isDetermining) {
      borderHighlight = 'border-amber-400/80 shadow-lg shadow-amber-500/10 ring-2 ring-amber-400/40';
    }

    const tempStr = node.temperature !== null ? `${node.temperature.toFixed(1)} °C` : '--';
    const rhStr = node.humidity !== null ? `${node.humidity.toFixed(1)} %` : '--';
    const dustVStr = node.dust_raw_voltage !== null ? `${node.dust_raw_voltage.toFixed(2)} V` : '--';
    const dustIdxStr = node.dust_index !== null ? node.dust_index.toFixed(3) : '--';
    const scoreStr = node.condition_score !== null ? node.condition_score.toFixed(1) : '--';
    const ctrlStr = node.control_level !== null ? node.control_level.toFixed(1) : '--';

    return `
      <div 
        data-node-id="${node.node_id}"
        class="glass-card rounded-2xl p-5 cursor-pointer transition-all duration-200 hover:-translate-y-0.5 hover:border-slate-700 relative overflow-hidden ${borderHighlight}"
      >
        <!-- Determining Node Banner -->
        ${isDetermining ? `
          <div class="absolute top-0 right-0 bg-gradient-to-l from-amber-500 to-amber-600 text-slate-950 font-bold text-[10px] uppercase tracking-wider px-3 py-0.5 rounded-bl-lg shadow-sm">
            Node Penentu
          </div>
        ` : ''}

        <!-- Header Card -->
        <div class="flex items-center justify-between mb-4">
          <div class="flex items-center gap-2">
            <span class="w-2.5 h-2.5 rounded-full ${node.status_valid ? 'bg-emerald-400' : 'bg-slate-500'}"></span>
            <h3 class="font-bold text-lg text-white">${node.node_id}</h3>
          </div>
          <span class="px-2.5 py-1 rounded-full text-xs font-semibold ${classBadge}">
            ${node.condition_class || 'Tidak Diketahui'}
          </span>
        </div>

        <!-- Sensor Parameter Grid -->
        <div class="grid grid-cols-3 gap-2 py-3 border-y border-slate-800/80 mb-3 text-center">
          <div class="bg-slate-900/60 rounded-xl p-2.5">
            <span class="text-[11px] text-slate-400 block">Suhu</span>
            <span class="font-mono font-bold text-sm text-sky-300">${tempStr}</span>
          </div>
          <div class="bg-slate-900/60 rounded-xl p-2.5">
            <span class="text-[11px] text-slate-400 block">RH (Kelembapan)</span>
            <span class="font-mono font-bold text-sm text-cyan-300">${rhStr}</span>
          </div>
          <div class="bg-slate-900/60 rounded-xl p-2.5">
            <span class="text-[11px] text-slate-400 block">Debu (V / Indeks)</span>
            <span class="font-mono font-bold text-xs text-amber-300">${dustVStr}</span>
            <span class="text-[10px] text-slate-400 block">Idx: ${dustIdxStr}</span>
          </div>
        </div>

        <!-- Fuzzy Outputs per Node -->
        <div class="flex items-center justify-between text-xs pt-1">
          <div>
            <span class="text-slate-400 block">Skor Kondisi:</span>
            <span class="font-mono font-semibold text-white">${scoreStr} / 100</span>
          </div>
          <div class="text-right">
            <span class="text-slate-400 block">Tingkat Kendali:</span>
            <span class="font-mono font-bold text-sky-400">${ctrlStr}</span>
          </div>
        </div>
      </div>
    `;
  }).join('');

  container.innerHTML = `
    <section class="space-y-4">
      <div class="flex items-center justify-between">
        <h2 class="text-lg font-bold text-slate-200 flex items-center gap-2">
          <span>Kondisi Lingkungan Multi-Node</span>
          <span class="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 font-normal">
            ${nodes.length} Node Aktif
          </span>
        </h2>
        <span class="text-xs text-slate-400">Klik kartu untuk inspeksi detail transparansi fuzzy</span>
      </div>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        ${cardsHtml}
      </div>
    </section>
  `;

  // Pasang event listener untuk klik kartu
  container.querySelectorAll('[data-node-id]').forEach(el => {
    el.addEventListener('click', () => {
      const nodeId = el.getAttribute('data-node-id');
      if (onSelectNode) onSelectNode(nodeId);
    });
  });
}
