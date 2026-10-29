/**
 * API Client untuk berkomunikasi dengan Backend FastAPI.
 */

const API_BASE = '/api';

export async function fetchLatestNodes() {
  try {
    const res = await fetch(`${API_BASE}/nodes/latest`);
    if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
    return await res.json();
  } catch (err) {
    console.error('Gagal mengambil data nodes terbaru:', err);
    return null;
  }
}

export async function fetchLatestControl() {
  try {
    const res = await fetch(`${API_BASE}/control/latest`);
    if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
    return await res.json();
  } catch (err) {
    console.error('Gagal mengambil data kendali zona:', err);
    return null;
  }
}

export async function fetchFuzzyDetail(nodeId) {
  try {
    const res = await fetch(`${API_BASE}/fuzzy/${encodeURIComponent(nodeId)}/detail`);
    if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
    return await res.json();
  } catch (err) {
    console.error(`Gagal mengambil rincian fuzzy untuk node ${nodeId}:`, err);
    return null;
  }
}

export async function simulateFuzzy(payload) {
  try {
    const res = await fetch(`${API_BASE}/fuzzy/simulate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
    return await res.json();
  } catch (err) {
    console.error('Gagal menjalankan simulasi fuzzy:', err);
    return null;
  }
}

export async function triggerManualTick() {
  try {
    const res = await fetch(`${API_BASE}/worker/tick`, { method: 'POST' });
    if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
    return await res.json();
  } catch (err) {
    console.error('Gagal memicu manual tick:', err);
    return null;
  }
}
