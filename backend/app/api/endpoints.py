"""
Router REST API Monitoring, Klasifikasi Kondisi, dan Kontrol Fan (backend/app/api/endpoints.py).

Menyediakan endpoints:
- GET  /api/nodes/latest       : Data pengukuran dan status node
- GET  /api/control/latest     : u_zona, node penentu, perintah PWM, dan status fan
- GET  /api/fuzzy/{node_id}/detail : Transparansi perhitungan fuzzy per node (derajat MF & aturan aktif)
- POST /api/fuzzy/simulate     : Simulasi hipotetis What-If (tanpa efek ke fan fisik/mock)
"""

from typing import List, Optional
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app import settings as ops
from app.core.database import get_db
from app.models import (
    ZoneNode,
    MockReceiverValidData,
    FuzzyResult,
    ZoneControl,
    ControlConfig
)
from app.schemas import (
    NodeMeasurementResponse,
    ZoneControlResponse,
    FuzzyDetailResponse,
    FuzzySimulateRequest,
    FuzzySimulateResponse,
)
from app.services.fuzzy import (
    evaluate_fuzzy,
    FuzzyMamdaniEngine,
    normalize_dust,
    DEFAULT_MEMBERSHIP_PARAMS,
    DEFAULT_RULE_BASE
)
from app.services.pwm import calculate_candidate_pwm
from app.core.ratelimit import rate_limit
from app.core.security import require_admin
from app.services.freshness import age_seconds, is_fresh
from app.services.worker import apply_auto, apply_manual, global_fan_controller, worker_status

router = APIRouter()


def _worker_alive() -> bool:
    last = worker_status["last_cycle_at"]
    return last is not None and age_seconds(last) <= 3 * ops.WORKER_INTERVAL_SECONDS


@router.get(
    "/nodes/latest",
    response_model=List[NodeMeasurementResponse],
    summary="Ambil data pengukuran dan status seluruh node sensor terbaru"
)
def get_latest_nodes(db: Session = Depends(get_db)):
    """Mengambil rekaman sensor terkini, hasil fuzzy, dan status penentu per node."""
    active_nodes = db.query(ZoneNode).filter(ZoneNode.is_active == True).all()

    # Dapatkan node penentu terakhir dari tabel zone_controls
    latest_control = (
        db.query(ZoneControl)
        .order_by(ZoneControl.created_at.desc(), ZoneControl.zone_control_id.desc())
        .first()
    )
    determining_node_id = latest_control.control_node_id if latest_control else None

    results = []
    for node in active_nodes:
        # Ambil data sensor terbaru dari mock receiver
        sensor_data = (
            db.query(MockReceiverValidData)
            .filter(MockReceiverValidData.node_id == node.node_id)
            .order_by(MockReceiverValidData.timestamp.desc())
            .first()
        )

        if not sensor_data:
            data_status, age, fresh = "Tidak ada data", None, False
        else:
            age = age_seconds(sensor_data.timestamp)
            fresh = is_fresh(sensor_data.timestamp)
            if not sensor_data.status_valid:
                data_status = "Tidak valid"
            elif not fresh:
                data_status = "Data lama"
            else:
                data_status = "Valid"

        is_determining = bool(determining_node_id) and determining_node_id == node.node_id and fresh

        # Pasangkan hasil fuzzy dengan rekaman sensor yang sama. Jangan mencampur
        # pembacaan terbaru dengan hasil dari siklus yang berbeda.
        fuzzy_data = None
        shown = sensor_data
        if sensor_data:
            fuzzy_data = (
                db.query(FuzzyResult)
                .filter(
                    FuzzyResult.zone_node_id == node.zone_node_id,
                    FuzzyResult.source_record_id == sensor_data.id,
                )
                .order_by(FuzzyResult.processed_at.desc())
                .first()
            )
            if fuzzy_data is None and fresh:
                # Rekaman terbaru belum selesai diproses (selisih satu siklus worker).
                # Tampilkan rekaman terproses sebelumnya secara utuh, bukan campuran.
                prev = (
                    db.query(FuzzyResult)
                    .filter(FuzzyResult.zone_node_id == node.zone_node_id)
                    .order_by(FuzzyResult.source_timestamp.desc())
                    .first()
                )
                if prev is not None and prev.temperature is not None \
                        and age_seconds(prev.source_timestamp) <= 3 * ops.FRESHNESS_SECONDS:
                    fuzzy_data = prev
                    shown = None  # nilai ukur diambil dari snapshot hasil fuzzy

        if shown is None and fuzzy_data is not None:
            temp_v, hum_v, volt_v, ts_v = (fuzzy_data.temperature, fuzzy_data.humidity,
                                           fuzzy_data.dust_raw_voltage, fuzzy_data.source_timestamp)
        else:
            temp_v = sensor_data.temperature if sensor_data else None
            hum_v = sensor_data.humidity if sensor_data else None
            volt_v = sensor_data.dust_raw_voltage if sensor_data else None
            ts_v = sensor_data.timestamp if sensor_data else None

        item = NodeMeasurementResponse(
            node_id=node.node_id,
            zone_id=node.zone_id,
            is_active=node.is_active,
            temperature=temp_v,
            humidity=hum_v,
            dust_raw_voltage=volt_v,
            dust_index=fuzzy_data.dust_index if fuzzy_data else None,
            condition_score=fuzzy_data.condition_score if fuzzy_data else None,
            condition_class=fuzzy_data.condition_class if fuzzy_data else None,
            control_level=fuzzy_data.control_level if fuzzy_data else None,
            source_timestamp=ts_v,
            status_valid=sensor_data.status_valid if sensor_data else False,
            is_determining_node=is_determining,
            data_age_seconds=age,
            is_fresh=fresh,
            data_status=data_status,
        )
        results.append(item)

    return results


@router.get(
    "/nodes/{node_id}/history",
    summary="Ambil riwayat parameter lingkungan untuk satu node"
)
def get_node_history(
    node_id: str,
    range: str = Query(default="1h", pattern="^(1h|6h|24h)$"),
    db: Session = Depends(get_db),
):
    """Riwayat ringkas untuk grafik dashboard tanpa menambah data perkiraan."""
    range_hours = {"1h": 1, "6h": 6, "24h": 24}
    cutoff = datetime.now(timezone.utc) - timedelta(hours=range_hours[range])

    rows = (
        db.query(MockReceiverValidData)
        .filter(
            MockReceiverValidData.node_id == node_id,
            MockReceiverValidData.timestamp >= cutoff,
        )
        .order_by(MockReceiverValidData.timestamp.asc())
        .all()
    )

    config = (
        db.query(ControlConfig)
        .filter(ControlConfig.is_active == True)
        .order_by(ControlConfig.created_at.desc())
        .first()
    )
    c_0 = config.dust_low_reference if config else 0.05
    c_h = config.dust_high_reference if config else 3.50

    return [
        {
            "node_id": row.node_id,
            "timestamp": row.timestamp,
            "temperature": row.temperature,
            "humidity": row.humidity,
            "dust_raw_voltage": row.dust_raw_voltage,
            "dust_index": normalize_dust(row.dust_raw_voltage, c_0=c_0, c_h=c_h),
            "status_valid": row.status_valid,
        }
        for row in rows
    ]


def _control_response(latest_ctrl: ZoneControl) -> ZoneControlResponse:
    return ZoneControlResponse(
        zone_id=latest_ctrl.zone_id,
        zone_control_level=latest_ctrl.zone_control_level,
        determining_node_id=latest_ctrl.control_node_id,
        pwm_command_percent=latest_ctrl.pwm_command_percent,
        candidate_pwm_percent=latest_ctrl.candidate_pwm_percent,
        previous_pwm_percent=latest_ctrl.previous_pwm_percent,
        auto_pwm_percent=latest_ctrl.auto_pwm_percent,
        hysteresis_held=latest_ctrl.hysteresis_held,
        freshness_seconds=ops.FRESHNESS_SECONDS,
        last_evaluated_at=worker_status["last_cycle_at"],
        worker_alive=_worker_alive(),
        control_status=latest_ctrl.control_status,
        fan_command_status=latest_ctrl.fan_command_status,
        control_mode=latest_ctrl.control_mode,
        config_version=latest_ctrl.config_version,
        processing_cycle_id=latest_ctrl.processing_cycle_id,
        created_at=latest_ctrl.created_at,
    )


@router.get(
    "/control/latest",
    response_model=ZoneControlResponse,
    summary="Ambil keputusan kendali zona dan status sinyal PWM fan terbaru"
)
def get_latest_control(db: Session = Depends(get_db)):
    """Mengambil rekaman kendali zona terakhir (u_zona, i*, duty cycle PWM, status fan)."""
    latest_ctrl = (
        db.query(ZoneControl)
        .order_by(ZoneControl.created_at.desc(), ZoneControl.zone_control_id.desc())
        .first()
    )

    if latest_ctrl:
        return _control_response(latest_ctrl)

    # Fallback jika belum ada siklus tersimpan di basis data
    return ZoneControlResponse(
        zone_id="ZONA-1",
        zone_control_level=None,
        determining_node_id=None,
        pwm_command_percent=global_fan_controller.d_prev,
        candidate_pwm_percent=0.0,
        previous_pwm_percent=global_fan_controller.d_prev,
        auto_pwm_percent=0.0,
        hysteresis_held=False,
        freshness_seconds=ops.FRESHNESS_SECONDS,
        last_evaluated_at=worker_status["last_cycle_at"],
        worker_alive=_worker_alive(),
        control_status="Kendali tidak tersedia",
        fan_command_status="Mati" if global_fan_controller.d_prev == 0.0 else "Aktif",
        control_mode="auto",
        config_version="v1.0.0-initial",
        processing_cycle_id=None,
        created_at=None,
    )


class ManualPwmRequest(BaseModel):
    """PWM Manual harus angka pada rentang 0-100; selain itu ditolak."""
    model_config = ConfigDict(strict=True)
    pwm_percent: float = Field(ge=0, le=100, allow_inf_nan=False)


@router.post("/control/manual", response_model=ZoneControlResponse,
             summary="Memilih Manual dan menerapkan PWM 0-100% (khusus admin)")
def set_manual_control(
    req: ManualPwmRequest,
    _admin: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    apply_manual(db, req.pwm_percent)
    return get_latest_control(db)


@router.post("/control/auto", response_model=ZoneControlResponse,
             summary="Kembali ke mode Otomatis (khusus admin)")
def set_auto_control(
    _admin: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    apply_auto(db)
    return get_latest_control(db)


_limit_history = rate_limit(60)       # per menit per IP
_limit_simulate = rate_limit(600)     # per menit per IP


@router.get(
    "/control/history",
    summary="Riwayat keputusan kendali zona dan u_i tiap node",
    dependencies=[Depends(_limit_history)],
)
def get_control_history(
    range: str = Query(default="1h", pattern="^(1h|6h|24h)$"),
    zone_id: str = "ZONA-1",
    db: Session = Depends(get_db),
):
    hours = {"1h": 1, "6h": 6, "24h": 24}[range]
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    zone_rows = (
        db.query(ZoneControl)
        .filter(ZoneControl.zone_id == zone_id, ZoneControl.created_at >= cutoff)
        .order_by(ZoneControl.created_at.asc(), ZoneControl.zone_control_id.asc())
        .all()
    )
    node_rows = (
        db.query(FuzzyResult, ZoneNode.node_id)
        .join(ZoneNode, ZoneNode.zone_node_id == FuzzyResult.zone_node_id)
        .filter(ZoneNode.zone_id == zone_id, FuzzyResult.source_timestamp >= cutoff)
        .order_by(FuzzyResult.source_timestamp.asc())
        .all()
    )

    nodes: dict = {}
    for fr, node_id in node_rows:
        nodes.setdefault(node_id, []).append({
            "timestamp": fr.source_timestamp,
            "temperature": fr.temperature,
            "humidity": fr.humidity,
            "dust_index": fr.dust_index,
            "condition_score": fr.condition_score,
            "condition_class": fr.condition_class,
            "control_level": fr.control_level,
        })

    return {
        "range": range,
        "zone": [
            {
                "timestamp": r.created_at,
                "zone_control_level": r.zone_control_level,
                "determining_node_id": r.control_node_id,
                "pwm_command_percent": r.pwm_command_percent,
                "fan_command_status": r.fan_command_status,
                "control_mode": r.control_mode,
            }
            for r in zone_rows
        ],
        "nodes": nodes,
    }


@router.get(
    "/fuzzy/{node_id}/detail",
    response_model=FuzzyDetailResponse,
    summary="Ambil transparansi perhitungan fuzzy lengkap untuk node tertentu"
)
def get_fuzzy_node_detail(node_id: str, db: Session = Depends(get_db)):
    """Mengembalikan derajat keanggotaan, aturan aktif, alpha_r, dan kurva agregasi."""
    sensor_data = (
        db.query(MockReceiverValidData)
        .filter(MockReceiverValidData.node_id == node_id)
        .order_by(MockReceiverValidData.timestamp.desc())
        .first()
    )

    if not sensor_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tidak ditemukan rekaman data sensor untuk node: {node_id}"
        )

    # Ambil konfigurasi aktif untuk parameter MFs dan acuan debu
    config = (
        db.query(ControlConfig)
        .filter(ControlConfig.is_active == True)
        .order_by(ControlConfig.created_at.desc())
        .first()
    )

    c_0 = config.dust_low_reference if config else 0.05
    c_h = config.dust_high_reference if config else 3.50
    m_params = config.membership_params if config else DEFAULT_MEMBERSHIP_PARAMS
    r_base = config.rule_base if config else DEFAULT_RULE_BASE

    engine = FuzzyMamdaniEngine(membership_params=m_params, rule_base=r_base)
    d_idx = normalize_dust(sensor_data.dust_raw_voltage, c_0=c_0, c_h=c_h)

    eval_result = engine.evaluate(
        temperature=sensor_data.temperature,
        humidity=sensor_data.humidity,
        dust_index=d_idx,
        include_curves=True
    )

    return FuzzyDetailResponse(
        node_id=node_id,
        inputs=eval_result["inputs"],
        memberships=eval_result["memberships"],
        active_rules=eval_result["active_rules"],
        outputs=eval_result["outputs"],
        curves=eval_result.get("curves")
    )


@router.post(
    "/fuzzy/simulate",
    response_model=FuzzySimulateResponse,
    dependencies=[Depends(_limit_simulate)],
    summary="Simulasi What-If fuzzy hipotetis (tidak mempengaruhi fan motor fisik)"
)
def simulate_fuzzy(req: FuzzySimulateRequest, db: Session = Depends(get_db)):
    """Memakai konfigurasi aktif yang sama dengan worker. Tidak menyentuh fan maupun basis data."""
    config = (
        db.query(ControlConfig)
        .filter(ControlConfig.is_active == True)
        .order_by(ControlConfig.created_at.desc())
        .first()
    )
    if config:
        engine = FuzzyMamdaniEngine(membership_params=config.membership_params, rule_base=config.rule_base)
        c_0, c_h = config.dust_low_reference, config.dust_high_reference
        u_off, u_max, d_min = config.u_off, config.u_max, config.d_min
        version = config.config_version
    else:
        engine = FuzzyMamdaniEngine()
        c_0, c_h, u_off, u_max, d_min, version = 0.05, 3.50, 15.0, 88.33, 30.0, None

    if req.dust_index is not None:
        d_idx = req.dust_index
    elif req.dust_raw is not None:
        d_idx = normalize_dust(req.dust_raw, c_0=c_0, c_h=c_h)
    else:
        raise HTTPException(status_code=422, detail="Isi dust_index atau dust_raw.")

    eval_result = engine.evaluate(
        temperature=req.temperature,
        humidity=req.humidity,
        dust_index=d_idx,
        include_curves=req.include_curves,
    )
    u_i = eval_result["outputs"]["control_level"]
    candidate = calculate_candidate_pwm(
        u_zona=u_i if u_i > u_off else None, u_off=u_off, u_max=u_max, d_min=d_min
    )

    return FuzzySimulateResponse(
        simulated_inputs=eval_result["inputs"],
        memberships=eval_result["memberships"],
        active_rules=eval_result["active_rules"],
        outputs=eval_result["outputs"],
        curves=eval_result.get("curves"),
        candidate_pwm_percent=candidate,
        config_version=version,
    )


@router.get(
    "/config/active",
    summary="Ambil konfigurasi sistem & kendali fuzzy aktif saat ini"
)
def get_active_config(db: Session = Depends(get_db)):
    """Mengembalikan konfigurasi sistem yang sedang aktif dari tabel control_config."""
    config = (
        db.query(ControlConfig)
        .filter(ControlConfig.is_active == True)
        .order_by(ControlConfig.created_at.desc())
        .first()
    )
    if not config:
        return {
            "config_version": "v1.0.0-default",
            "dust_low_reference": 0.05,
            "dust_high_reference": 3.50,
            "u_off": 15.0,
            "u_max": 88.33,
            "d_min": 30.0,
            "delta_d_update": 5.0,
            "is_active": True,
            "membership_params": DEFAULT_MEMBERSHIP_PARAMS,
            "rule_base_count": len(DEFAULT_RULE_BASE),
            "created_at": None,
        }

    return {
        "config_version": config.config_version,
        "dust_low_reference": config.dust_low_reference,
        "dust_high_reference": config.dust_high_reference,
        "u_off": config.u_off,
        "u_max": config.u_max,
        "d_min": config.d_min,
        "delta_d_update": config.delta_d_update,
        "is_active": config.is_active,
        "membership_params": config.membership_params or DEFAULT_MEMBERSHIP_PARAMS,
        "rule_base_count": len(config.rule_base) if config.rule_base else len(DEFAULT_RULE_BASE),
        "created_at": config.created_at,
    }

