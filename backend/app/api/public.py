"""
Ringkasan publik untuk landing page (backend/app/api/public.py).

GET /api/public/summary hanya membaca dan menyederhanakan data yang sudah ada
(GET /api/nodes/latest dan GET /api/control/latest). Endpoint ini tidak memuat
tegangan mentah, skor, versi konfigurasi, atau apa pun yang berkaitan dengan
kendali. Tidak ada logika fuzzy atau kendali yang diubah.
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.ratelimit import rate_limit
from app.services.freshness import as_utc
from app.api.endpoints import get_latest_nodes, get_latest_control

router = APIRouter(prefix="/public", tags=["Publik"])

_limit_public = rate_limit(120)  # per menit per IP


def _round(v: Optional[float], digits: int) -> Optional[float]:
    return None if v is None else round(float(v), digits)


@router.get(
    "/summary",
    summary="Ringkasan publik kondisi node dan status perintah fan",
    dependencies=[Depends(_limit_public)],
)
def get_public_summary(response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"

    raw_nodes = get_latest_nodes(db=db)
    ctrl = get_latest_control(db=db)

    nodes = []
    for n in sorted(raw_nodes, key=lambda x: x.node_id):
        usable = n.data_status == "Valid" and n.condition_class is not None
        ts = as_utc(n.source_timestamp).isoformat() if n.source_timestamp else None
        nodes.append({
            "node_id": n.node_id,
            "temperature": _round(n.temperature, 1),
            "humidity": _round(n.humidity, 1),
            "pressure_hpa": _round(n.pressure_hpa, 1),
            "dust_index": _round(n.dust_index, 2),
            "condition_class": n.condition_class if usable else None,
            "data_status": n.data_status,
            "updated_at": ts,
            "age_seconds": _round(n.data_age_seconds, 0),
            "is_determining": bool(n.is_determining_node) and usable,
        })

    available = any(n["condition_class"] is not None for n in nodes)

    mode = ctrl.control_mode
    if available or mode == "manual":
        control = {
            "mode": mode,
            "pwm_percent": _round(ctrl.pwm_command_percent, 0),
            "determining_node_id": ctrl.determining_node_id if available else None,
            "control_status": ctrl.control_status,
            "fan_command_status": ctrl.fan_command_status,
        }
    else:
        # Tidak ada data yang dapat digunakan pada mode Otomatis.
        control = {
            "mode": mode,
            "pwm_percent": 0,
            "determining_node_id": None,
            "control_status": "Kendali tidak tersedia",
            "fan_command_status": "Kendali tidak tersedia",
        }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "available": available,
        "node_count": len(nodes),
        "nodes": nodes,
        "control": control,
    }
