"""
Worker Siklus Pemrosesan & Penyimpanan Terintegrasi (backend/app/services/worker.py).

Menjalankan pipeline otomatis secara periodik:
1. Membaca konfigurasi aktif dari tabel `control_config`.
2. Mengambil data sensor terbaru dari tabel `mock_receiver_valid_data` untuk setiap node aktif.
3. Memvalidasi kelengkapan 3 parameter (suhu, kelembapan relatif / RH, debu).
4. Menjalankan inferensi Fuzzy Mamdani (NumPy) per node valid dan menyimpannya ke `fuzzy_results`.
5. Melakukan agregasi zona (worst-case u_zona & penentuan node i* deterministik via `zone.py`).
6. Memetakan ke sinyal PWM dengan histeresis via `pwm.py`.
7. Menyimpan keputusan zona dan perintah PWM ke `zone_controls` dengan keterlacakan penuh.
"""

import asyncio
import logging
import time
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import numpy as np
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models import (
    ControlConfig,
    ZoneNode,
    FuzzyResult,
    ZoneControl,
    MockReceiverValidData,
)
from app.services.fuzzy import FuzzyMamdaniEngine, evaluate_fuzzy, normalize_dust
from app.services.zone import aggregate_zone
from app.services.pwm import FanPWMController, MockPWMDriver

logger = logging.getLogger("wsn.worker")

# Controller PWM global yang mempertahankan status d_prev selama aplikasi berjalan
global_fan_controller = FanPWMController(
    driver=MockPWMDriver(initial_pwm=0.0),
    u_off=15.0,
    u_max=88.33,
    d_min=30.0,
    delta_d_update=5.0
)


def run_processing_cycle(
    db: Session,
    controller: Optional[FanPWMController] = None,
    zone_id: str = "ZONA-1"
) -> Dict[str, Any]:
    """
    Mengeksekusi satu siklus pemrosesan lengkap:
    Ambil Data -> Validasi -> Fuzzy -> Zona -> PWM -> Simpan DB.
    """
    fan_ctrl = controller or global_fan_controller
    cycle_id = f"CYC-{int(time.time())}-{uuid.uuid4().hex[:6]}"

    # 1. Ambil konfigurasi aktif dari basis data
    config = (
        db.query(ControlConfig)
        .filter(ControlConfig.is_active == True)
        .order_by(ControlConfig.created_at.desc())
        .first()
    )

    if not config:
        # Fallback versi default jika database belum di-seed
        config_version = "v1.0.0-fallback"
        dust_low_ref = 0.05
        dust_high_ref = 3.50
        u_off = 15.0
        fuzzy_engine = FuzzyMamdaniEngine()
    else:
        config_version = config.config_version
        dust_low_ref = config.dust_low_reference
        dust_high_ref = config.dust_high_reference
        u_off = config.u_off
        fuzzy_engine = FuzzyMamdaniEngine(
            membership_params=config.membership_params,
            rule_base=config.rule_base
        )
        # Sinkronisasi parameter controller dengan config
        fan_ctrl.u_off = config.u_off
        fan_ctrl.u_max = config.u_max
        fan_ctrl.d_min = config.d_min
        fan_ctrl.delta_d_update = config.delta_d_update

    # 2. Ambil seluruh node aktif di zona ini
    active_nodes = (
        db.query(ZoneNode)
        .filter(ZoneNode.zone_id == zone_id, ZoneNode.is_active == True)
        .all()
    )

    valid_node_candidates: List[Dict[str, Any]] = []

    # 3. Proses inferensi fuzzy per node
    for z_node in active_nodes:
        # Ambil data sensor terbaru dari tabel penerima M2
        latest_sensor_data = (
            db.query(MockReceiverValidData)
            .filter(MockReceiverValidData.node_id == z_node.node_id)
            .order_by(MockReceiverValidData.timestamp.desc())
            .first()
        )

        if not latest_sensor_data:
            continue

        # Validasi status validitas & kelengkapan 3 parameter sensor
        is_complete = (
            latest_sensor_data.status_valid is True
            and latest_sensor_data.temperature is not None
            and latest_sensor_data.humidity is not None
            and latest_sensor_data.dust_raw_voltage is not None
            and not np.isnan(latest_sensor_data.temperature)
            and not np.isnan(latest_sensor_data.humidity)
            and not np.isnan(latest_sensor_data.dust_raw_voltage)
        )

        if not is_complete:
            # Data tidak lengkap atau tidak valid -> abaikan sesuai FR-03
            continue

        # Jalankan inferensi Fuzzy Mamdani
        d_idx = normalize_dust(
            latest_sensor_data.dust_raw_voltage,
            c_0=dust_low_ref,
            c_h=dust_high_ref
        )

        fuzzy_eval = fuzzy_engine.evaluate(
            temperature=latest_sensor_data.temperature,
            humidity=latest_sensor_data.humidity,
            dust_index=d_idx
        )

        outputs = fuzzy_eval["outputs"]
        s_i = outputs["condition_score"]
        k_i = outputs["condition_class"]
        u_i = outputs["control_level"]

        # Simpan hasil fuzzy per node ke basis data jika konfigurasi resmi tersedia
        fuzzy_res_obj = None
        if config:
            fuzzy_res_obj = FuzzyResult(
                zone_node_id=z_node.zone_node_id,
                config_version=config_version,
                processing_cycle_id=cycle_id,
                source_record_id=latest_sensor_data.id,
                source_timestamp=latest_sensor_data.timestamp,
                dust_index=d_idx,
                condition_score=s_i,
                condition_class=k_i,
                control_level=u_i
            )
            db.add(fuzzy_res_obj)

        valid_node_candidates.append({
            "node_id": z_node.node_id,
            "zone_node_id": z_node.zone_node_id,
            "control_level": u_i,
            "condition_score": s_i,
            "condition_class": k_i,
            "source_timestamp": latest_sensor_data.timestamp,
            "source_record_id": latest_sensor_data.id,
            "fuzzy_result_obj": fuzzy_res_obj
        })

    # Flush session untuk mendapatkan ID dari fuzzy_results yang baru di-insert
    if config:
        db.flush()

    # 4. Agregasi Tingkat Kendali Zona (u_zona = max u_i)
    zone_decision = aggregate_zone(
        node_results=valid_node_candidates,
        zone_id=zone_id,
        u_off=u_off
    )

    # 5. Pemetaan PWM & Histeresis
    u_zona = zone_decision["zone_control_level"]
    has_valid_data = zone_decision["has_valid_data"]
    pwm_decision = fan_ctrl.compute_and_apply(
        u_zona=u_zona,
        has_valid_data=has_valid_data
    )

    # Dapatkan FK control_fuzzy_result_id jika ada node penentu
    determining_fuzzy_id = None
    if zone_decision.get("determining_result"):
        det_obj = zone_decision["determining_result"].get("fuzzy_result_obj")
        if det_obj:
            determining_fuzzy_id = det_obj.fuzzy_result_id

    # 6. Simpan hasil keputusan kendali zona ke zone_controls
    zone_ctrl_record = None
    if config:
        zone_ctrl_record = ZoneControl(
            config_version=config_version,
            processing_cycle_id=cycle_id,
            zone_id=zone_id,
            control_fuzzy_result_id=determining_fuzzy_id,
            control_node_id=zone_decision["determining_node_id"],
            zone_control_level=u_zona,
            pwm_command_percent=pwm_decision["final_pwm"],
            control_status=zone_decision["control_status"],
            fan_command_status=pwm_decision["fan_command_status"],
            control_mode="auto"
        )
        db.add(zone_ctrl_record)
        db.commit()

    return {
        "processing_cycle_id": cycle_id,
        "config_version": config_version,
        "nodes_evaluated": len(valid_node_candidates),
        "zone_decision": zone_decision,
        "pwm_decision": pwm_decision
    }


async def background_worker_loop(
    interval_seconds: int = 5,
    stop_event: Optional[asyncio.Event] = None
):
    """
    Loop latar belakang asynchronous untuk menjalankan worker periodik.
    """
    logger.info(f"Background worker WSN dimulai (interval: {interval_seconds}s)")
    while stop_event is None or not stop_event.is_set():
        try:
            db = SessionLocal()
            try:
                result = run_processing_cycle(db=db)
                logger.debug(
                    f"Cycle {result['processing_cycle_id']} selesai. "
                    f"Nodes: {result['nodes_evaluated']}, "
                    f"u_zona: {result['zone_decision']['zone_control_level']}, "
                    f"PWM: {result['pwm_decision']['final_pwm']}%"
                )
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Kesalahan pada background worker cycle: {e}")

        try:
            if stop_event:
                await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
            else:
                await asyncio.sleep(interval_seconds)
        except asyncio.TimeoutError:
            pass
        except asyncio.CancelledError:
            break

    logger.info("Background worker WSN dihentikan.")
