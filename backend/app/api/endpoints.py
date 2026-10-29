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
from sqlalchemy.orm import Session

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
from app.services.worker import global_fan_controller

router = APIRouter()


@router.get(
    "/nodes/latest",
    response_model=List[NodeMeasurementResponse],
    summary="Ambil data pengukuran dan status seluruh node sensor terbaru"
)
def get_latest_nodes(db: Session = Depends(get_db)):
    """Mengambil rekaman sensor terkini, hasil fuzzy, dan status penentu per node."""
    active_nodes = db.query(ZoneNode).filter(ZoneNode.is_active == True).all()

    # Dapatkan node penentu terakhir dari tabel zone_controls
    latest_control = db.query(ZoneControl).order_by(ZoneControl.created_at.desc()).first()
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

        # Pasangkan hasil fuzzy dengan rekaman sensor yang sama. Jangan mencampur
        # pembacaan terbaru dengan hasil dari siklus yang berbeda.
        fuzzy_data = None
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

        is_determining = (determining_node_id == node.node_id) if determining_node_id else False

        item = NodeMeasurementResponse(
            node_id=node.node_id,
            zone_id=node.zone_id,
            is_active=node.is_active,
            temperature=sensor_data.temperature if sensor_data else None,
            humidity=sensor_data.humidity if sensor_data else None,
            dust_raw_voltage=sensor_data.dust_raw_voltage if sensor_data else None,
            dust_index=fuzzy_data.dust_index if fuzzy_data else None,
            condition_score=fuzzy_data.condition_score if fuzzy_data else None,
            condition_class=fuzzy_data.condition_class if fuzzy_data else None,
            control_level=fuzzy_data.control_level if fuzzy_data else None,
            source_timestamp=sensor_data.timestamp if sensor_data else None,
            status_valid=sensor_data.status_valid if sensor_data else False,
            is_determining_node=is_determining,
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


@router.get(
    "/control/latest",
    response_model=ZoneControlResponse,
    summary="Ambil keputusan kendali zona dan status sinyal PWM fan terbaru"
)
def get_latest_control(db: Session = Depends(get_db)):
    """Mengambil rekaman kendali zona terakhir (u_zona, i*, duty cycle PWM, status fan)."""
    latest_ctrl = db.query(ZoneControl).order_by(ZoneControl.created_at.desc()).first()

    if latest_ctrl:
        return ZoneControlResponse(
            zone_id=latest_ctrl.zone_id,
            zone_control_level=latest_ctrl.zone_control_level,
            determining_node_id=latest_ctrl.control_node_id,
            pwm_command_percent=latest_ctrl.pwm_command_percent,
            control_status=latest_ctrl.control_status,
            fan_command_status=latest_ctrl.fan_command_status,
            control_mode=latest_ctrl.control_mode,
            config_version=latest_ctrl.config_version,
            processing_cycle_id=latest_ctrl.processing_cycle_id,
            created_at=latest_ctrl.created_at,
        )

    # Fallback jika belum ada siklus tersimpan di basis data
    return ZoneControlResponse(
        zone_id="ZONA-1",
        zone_control_level=None,
        determining_node_id=None,
        pwm_command_percent=global_fan_controller.d_prev,
        control_status="Kendali tidak tersedia",
        fan_command_status="Mati" if global_fan_controller.d_prev == 0.0 else "Aktif",
        control_mode="auto",
        config_version="v1.0.0-initial",
        processing_cycle_id=None,
        created_at=None,
    )


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
    summary="Simulasi What-If fuzzy hipotetis (tidak mempengaruhi fan motor fisik)"
)
def simulate_fuzzy(req: FuzzySimulateRequest):
    """
    Menghitung inferensi fuzzy untuk masukan suhu, RH, dan debu yang ditentukan pengguna.
    Hanya mengembalikan hasil perhitungan dan tidak menyentuh aktuator fan maupun basis data.
    """
    eval_result = evaluate_fuzzy(
        temperature=req.temperature,
        humidity=req.humidity,
        dust_raw=req.dust_raw,
        dust_index=req.dust_index,
        include_curves=req.include_curves
    )

    return FuzzySimulateResponse(
        simulated_inputs=eval_result["inputs"],
        memberships=eval_result["memberships"],
        active_rules=eval_result["active_rules"],
        outputs=eval_result["outputs"],
        curves=eval_result.get("curves")
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

