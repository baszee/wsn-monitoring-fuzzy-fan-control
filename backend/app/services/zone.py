"""
Layanan Agregasi Zona Kendali WSN (backend/app/services/zone.py).

Menggabungkan hasil inferensi fuzzy tingkat kendali u_i dari himpunan node valid V(t):
1. Menghitung u_zona = max_{i in V} u_i
2. Menentukan node penentu i* = argmax_{i in V} u_i dengan aturan tie-break:
   - Prioritas 1: Tingkat kendali u_i terbesar
   - Prioritas 2: Waktu data sumber terbaru (source_timestamp)
   - Prioritas 3: Identitas node terkecil secara alfabetis (node_id)
3. Menangani kasus himpunan kosong V(t) = kosong (tidak ada data valid / lengkap):
   - u_zona = None
   - i* = None
   - control_status = "Kendali tidak tersedia"
   - fan_command_status = "Kendali tidak tersedia"
"""

from typing import List, Dict, Any, Optional, Tuple, Union
from datetime import datetime, timezone


def _parse_timestamp(ts: Union[datetime, str, float, int]) -> float:
    """Konversi berbagai format timestamp ke epoch float (detik) untuk perbandingan deterministik."""
    if isinstance(ts, (int, float)):
        return float(ts)
    elif isinstance(ts, datetime):
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts.timestamp()
    elif isinstance(ts, str):
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except Exception:
            return 0.0
    return 0.0


def aggregate_zone(
    node_results: List[Dict[str, Any]],
    zone_id: str = "ZONA-1",
    u_off: float = 15.0
) -> Dict[str, Any]:
    """
    Melakukan agregasi tingkat kendali multi-node pada suatu zona pemantauan.

    Parameter:
        node_results: List dictionary hasil evaluasi node valid. Setiap elemen minimal memiliki:
            - 'node_id': str (misal 'NODE-01')
            - 'control_level': float (u_i, 0 - 100)
            - 'source_timestamp': datetime / float / iso str
            - opsional: 'condition_score' (s_i), 'condition_class', 'fuzzy_result_id', dll.
        zone_id: Identifier zona (default 'ZONA-1')
        u_off: Ambang batas minimum fan menyala (default 15.0)

    Mengembalikan:
        Dictionary keputusan zona lengkap dengan node penentu i* dan status kendali.
    """
    # Kasus 1: Himpunan node valid V(t) kosong
    if not node_results:
        return {
            "zone_id": zone_id,
            "has_valid_data": False,
            "zone_control_level": None,
            "determining_node_id": None,
            "determining_result": None,
            "control_status": "Kendali tidak tersedia",
            "fan_command_status": "Kendali tidak tersedia",
            "total_nodes_evaluated": 0,
            "evaluated_nodes": []
        }

    # Kasus 2: Ada node valid, lakukan pemilihan deterministik
    # Kriteria pengurutan prioritas:
    # 1. u_i terbesar (descending) -> gunakan -control_level
    # 2. source_timestamp terbaru (descending) -> gunakan -epoch
    # 3. node_id terkecil (ascending) -> gunakan node_id
    def tie_break_key(item: Dict[str, Any]) -> Tuple[float, float, str]:
        u_i = float(item.get("control_level", 0.0))
        ts_epoch = _parse_timestamp(item.get("source_timestamp", 0.0))
        node_id = str(item.get("node_id", ""))
        return (-u_i, -ts_epoch, node_id)

    # Urutkan seluruh kandidat berdasarkan kriteria tie-break di atas
    sorted_candidates = sorted(node_results, key=tie_break_key)
    winner = sorted_candidates[0]

    u_zona = float(winner.get("control_level", 0.0))
    determining_node_id = str(winner.get("node_id", ""))

    # Tentukan status perintah fan berdasarkan u_off
    if u_zona > u_off:
        control_status = "Aktif"
        fan_status = "Aktif"
    else:
        control_status = "Mati"
        fan_status = "Mati"

    return {
        "zone_id": zone_id,
        "has_valid_data": True,
        "zone_control_level": round(u_zona, 2),
        "determining_node_id": determining_node_id,
        "determining_result": winner,
        "control_status": control_status,
        "fan_command_status": fan_status,
        "total_nodes_evaluated": len(node_results),
        "evaluated_nodes": sorted_candidates
    }
