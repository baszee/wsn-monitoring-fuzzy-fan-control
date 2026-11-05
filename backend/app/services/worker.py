"""
Worker Siklus Pemrosesan & Penyimpanan Terintegrasi (backend/app/services/worker.py).

Menjalankan pipeline otomatis secara periodik:
1. Membaca konfigurasi aktif dari tabel `control_config`.
2. Mengambil data sensor terbaru melalui adaptor sumber (`mock` atau `node_readings`).
3. Memvalidasi kelengkapan 3 parameter (suhu, kelembapan relatif / RH, debu).
4. Menjalankan inferensi Fuzzy Mamdani (NumPy) per node valid dan menyimpannya ke `fuzzy_results`.
5. Melakukan agregasi zona (worst-case u_zona & penentuan node i* deterministik via `zone.py`).
6. Memetakan ke sinyal PWM dengan histeresis via `pwm.py`.
7. Menyimpan keputusan zona dan perintah PWM ke `zone_controls` dengan keterlacakan penuh.
"""

import asyncio
import logging
import threading
import time
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app import settings as ops
from app.services.freshness import age_seconds, is_fresh
from app.core.database import SessionLocal
from app.models import (
    ControlConfig,
    ZoneNode,
    FuzzyResult,
    ZoneControl,
)
from app.services.fuzzy import FuzzyMamdaniEngine, evaluate_fuzzy, normalize_dust
from app.services.zone import aggregate_zone
from app.services.pwm import FanPWMController, MockPWMDriver
from app.sources import get_sensor_source

logger = logging.getLogger("wsn.worker")

# Controller PWM global yang mempertahankan status d_prev selama aplikasi berjalan
global_fan_controller = FanPWMController(
    driver=MockPWMDriver(initial_pwm=0.0),
    u_off=15.0,
    u_max=88.33,
    d_min=30.0,
    delta_d_update=5.0
)

# Detak worker. Tabel zone_controls hanya ditulis saat ada perubahan,
# jadi waktu evaluasi terakhir disimpan di sini.
worker_status: Dict[str, Any] = {
    "last_cycle_at": None,
    "last_source_time": None,
    "last_error": None,
    "last_error_at": None,
    "source_mode": ops.SENSOR_SOURCE,
}

# Mode kendali. Selalu mulai Otomatis dengan PWM 0%; tidak dipulihkan setelah restart.
control_lock = threading.RLock()
control_state: Dict[str, Any] = {"mode": "auto", "manual_pwm": 0.0, "applied_pwm": 0.0}
last_auto: Dict[str, Any] = {}   # hasil jalur Otomatis terbaru (juga saat Manual)


def _run_processing_cycle(
    db: Session,
    controller: Optional[FanPWMController] = None,
    zone_id: str = "ZONA-1"
) -> Dict[str, Any]:
    """Ambil Data -> Validasi -> Kesegaran -> Fuzzy -> Zona -> PWM -> Simpan (hanya jika baru/berubah)."""
    fan_ctrl = controller or global_fan_controller
    source = get_sensor_source()
    now = source.db_now(db)
    cycle_id = f"CYC-{int(time.time())}-{uuid.uuid4().hex[:6]}"

    config = (
        db.query(ControlConfig)
        .filter(ControlConfig.is_active == True)
        .order_by(ControlConfig.created_at.desc())
        .first()
    )

    if not config:
        config_version = "v1.0.0-fallback"
        dust_low_ref, dust_high_ref, u_off = 0.05, 3.50, 15.0
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
        fan_ctrl.u_off = config.u_off
        fan_ctrl.u_max = config.u_max
        fan_ctrl.d_min = config.d_min
        fan_ctrl.delta_d_update = config.delta_d_update

    active_nodes = (
        db.query(ZoneNode)
        .filter(ZoneNode.zone_id == zone_id, ZoneNode.is_active == True)
        .all()
    )

    candidates: List[Dict[str, Any]] = []
    new_results = 0

    for z_node in active_nodes:
        rec = source.latest(db, z_node.node_id)
        if not rec:
            continue

        if not rec.status_valid or not rec.inputs_complete:
            continue

        # Kebijakan kesegaran: sama dengan yang ditampilkan dashboard
        if not is_fresh(rec.timestamp, now):
            continue

        fuzzy_res_obj = None
        if config:
            fuzzy_res_obj = (
                db.query(FuzzyResult)
                .filter(
                    FuzzyResult.zone_node_id == z_node.zone_node_id,
                    FuzzyResult.source_record_id == rec.id,
                    FuzzyResult.config_version == config_version,
                )
                .first()
            )

        if fuzzy_res_obj is not None:
            # Rekaman ini sudah pernah diproses: pakai hasil tersimpan.
            s_i = fuzzy_res_obj.condition_score
            k_i = fuzzy_res_obj.condition_class
            u_i = fuzzy_res_obj.control_level
        else:
            d_idx = normalize_dust(rec.dust_raw_voltage, c_0=dust_low_ref, c_h=dust_high_ref)
            outputs = fuzzy_engine.evaluate(
                temperature=rec.temperature,
                humidity=rec.humidity,
                dust_index=d_idx,
            )["outputs"]
            s_i = outputs["condition_score"]
            k_i = outputs["condition_class"]
            u_i = outputs["control_level"]

            if config:
                fuzzy_res_obj = FuzzyResult(
                    zone_node_id=z_node.zone_node_id,
                    config_version=config_version,
                    processing_cycle_id=cycle_id,
                    source_record_id=rec.id,
                    source_timestamp=rec.timestamp,
                    temperature=rec.temperature,
                    humidity=rec.humidity,
                    dust_raw_voltage=rec.dust_raw_voltage,
                    dust_index=d_idx,
                    condition_score=s_i,
                    condition_class=k_i,
                    control_level=u_i,
                )
                db.add(fuzzy_res_obj)
                new_results += 1

        candidates.append({
            "node_id": z_node.node_id,
            "zone_node_id": z_node.zone_node_id,
            "control_level": u_i,
            "condition_score": s_i,
            "condition_class": k_i,
            "source_timestamp": rec.timestamp,
            "source_record_id": rec.id,
            "fuzzy_result_obj": fuzzy_res_obj,
        })

    if config:
        db.flush()  # dapatkan fuzzy_result_id untuk baris baru

    zone_decision = aggregate_zone(node_results=candidates, zone_id=zone_id, u_off=u_off)
    u_zona = zone_decision["zone_control_level"]
    mode = control_state["mode"]
    pwm_decision = fan_ctrl.compute_and_apply(
        u_zona=u_zona,
        has_valid_data=zone_decision["has_valid_data"],
        apply_output=(mode == "auto"),
    )
    if mode == "manual":
        applied_pwm = control_state["manual_pwm"]
        fan_status = "Aktif" if applied_pwm > 0 else "Mati"
    else:
        applied_pwm = pwm_decision["final_pwm"]
        fan_status = pwm_decision["fan_command_status"]
    control_state["applied_pwm"] = applied_pwm

    determining_fuzzy_id = None
    if zone_decision.get("determining_result"):
        det_obj = zone_decision["determining_result"].get("fuzzy_result_obj")
        if det_obj:
            determining_fuzzy_id = det_obj.fuzzy_result_id

    last_auto.update({
        "at": now,
        "zone_control_level": u_zona,
        "determining_node_id": zone_decision["determining_node_id"],
        "determining_fuzzy_id": determining_fuzzy_id,
        "control_status": zone_decision["control_status"],
        "has_valid_data": zone_decision["has_valid_data"],
        "candidate": pwm_decision["candidate_pwm"],
        "final": pwm_decision["final_pwm"],
    })

    # Tulis keputusan zona hanya bila ada pengukuran baru atau keputusan berubah
    wrote_control = False
    if config:
        signature = (
            zone_decision["determining_node_id"],
            None if u_zona is None else round(u_zona, 2),
            applied_pwm,
            zone_decision["control_status"],
            fan_status,
            mode,
            pwm_decision["final_pwm"],
        )
        last = (
            db.query(ZoneControl)
            .filter(ZoneControl.zone_id == zone_id)
            .order_by(ZoneControl.created_at.desc(), ZoneControl.zone_control_id.desc())
            .first()
        )
        last_sig = None
        if last:
            last_sig = (
                last.control_node_id,
                None if last.zone_control_level is None else round(last.zone_control_level, 2),
                last.pwm_command_percent,
                last.control_status,
                last.fan_command_status,
                last.control_mode,
                last.auto_pwm_percent,
            )

        if new_results > 0 or signature != last_sig:
            db.add(ZoneControl(
                config_version=config_version,
                processing_cycle_id=cycle_id,
                zone_id=zone_id,
                control_fuzzy_result_id=determining_fuzzy_id,
                control_node_id=zone_decision["determining_node_id"],
                zone_control_level=u_zona,
                pwm_command_percent=applied_pwm,
                candidate_pwm_percent=pwm_decision["candidate_pwm"],
                previous_pwm_percent=pwm_decision["previous_pwm"],
                auto_pwm_percent=pwm_decision["final_pwm"],
                hysteresis_held=pwm_decision["final_pwm"] != pwm_decision["candidate_pwm"],
                control_status=zone_decision["control_status"],
                fan_command_status=fan_status,
                control_mode=mode,
            ))
            wrote_control = True
        db.commit()

    worker_status.update(
        last_cycle_at=datetime.now(timezone.utc),
        last_source_time=now,
        last_error=None,
        last_error_at=None,
        source_mode=source.name,
    )

    return {
        "processing_cycle_id": cycle_id,
        "config_version": config_version,
        "nodes_evaluated": len(candidates),
        "new_results": new_results,
        "wrote_control": wrote_control,
        "zone_decision": zone_decision,
        "pwm_decision": pwm_decision,
        "control_mode": mode,
        "applied_pwm": applied_pwm,
    }


def run_processing_cycle(
    db: Session,
    controller: Optional[FanPWMController] = None,
    zone_id: str = "ZONA-1"
) -> Dict[str, Any]:
    """Satu siklus pemrosesan. Dikunci agar tidak berpapasan dengan perubahan mode dari admin."""
    with control_lock:
        return _run_processing_cycle(db, controller, zone_id)


def reset_control_state(controller: Optional[FanPWMController] = None) -> None:
    """Keadaan awal aplikasi: mode Otomatis, PWM 0%."""
    fan_ctrl = controller or global_fan_controller
    with control_lock:
        control_state.update(mode="auto", manual_pwm=0.0, applied_pwm=0.0)
        last_auto.clear()
        fan_ctrl.reset_hysteresis()
        fan_ctrl.driver.set_duty_cycle(0.0)


def _apply_auto_failsafe(error: Exception) -> None:
    """Pada kegagalan worker, hentikan keluaran Otomatis; Manual tidak diubah."""
    now = datetime.now(timezone.utc)
    with control_lock:
        if control_state["mode"] == "auto":
            global_fan_controller.driver.set_duty_cycle(0.0)
            global_fan_controller.reset_hysteresis()
            control_state["applied_pwm"] = 0.0
        worker_status.update(
            last_error=type(error).__name__,
            last_error_at=now,
            source_mode=ops.SENSOR_SOURCE,
        )


def apply_manual(
    db: Session,
    pwm_percent: float,
    controller: Optional[FanPWMController] = None,
    zone_id: str = "ZONA-1",
) -> Optional[ZoneControl]:
    """Memilih mode Manual: PWM langsung diterapkan dan satu baris baru langsung disimpan."""
    fan_ctrl = controller or global_fan_controller
    pwm = float(pwm_percent)
    with control_lock:
        previous = control_state["applied_pwm"]
        control_state.update(mode="manual", manual_pwm=pwm, applied_pwm=pwm)
        fan_ctrl.driver.set_duty_cycle(pwm)

        config = (
            db.query(ControlConfig)
            .filter(ControlConfig.is_active == True)
            .order_by(ControlConfig.created_at.desc())
            .first()
        )
        if not config:
            return None

        source_now = get_sensor_source().db_now(db)
        usable = bool(last_auto) and last_auto.get("has_valid_data") and (
            age_seconds(last_auto["at"], source_now) <= max(3 * ops.WORKER_INTERVAL_SECONDS, 5)
        )
        row = ZoneControl(
            config_version=config.config_version,
            processing_cycle_id=f"MAN-{int(time.time())}-{uuid.uuid4().hex[:6]}",
            zone_id=zone_id,
            control_fuzzy_result_id=last_auto["determining_fuzzy_id"] if usable else None,
            control_node_id=last_auto["determining_node_id"] if usable else None,
            zone_control_level=last_auto["zone_control_level"] if usable else None,
            pwm_command_percent=pwm,
            candidate_pwm_percent=last_auto["candidate"] if usable else None,
            previous_pwm_percent=previous,
            auto_pwm_percent=last_auto["final"] if usable else 0.0,
            hysteresis_held=False,
            control_status=last_auto["control_status"] if usable else "Kendali tidak tersedia",
            fan_command_status="Aktif" if pwm > 0 else "Mati",
            control_mode="manual",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row


def apply_auto(
    db: Session,
    controller: Optional[FanPWMController] = None,
    zone_id: str = "ZONA-1",
) -> Dict[str, Any]:
    """Kembali ke Otomatis: histeresis di-reset dan PWM langsung mengikuti hasil otomatis terbaru."""
    fan_ctrl = controller or global_fan_controller
    with control_lock:
        control_state["mode"] = "auto"
        fan_ctrl.reset_hysteresis()
        return _run_processing_cycle(db, fan_ctrl, zone_id)


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
            _apply_auto_failsafe(e)
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
