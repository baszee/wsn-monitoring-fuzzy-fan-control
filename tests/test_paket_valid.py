"""Kontrak adaptor sumber paket_valid (schema.sql penerima M2 terbaru)."""

from datetime import datetime, timedelta, timezone
import os
import sys

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app import settings as ops
from app.api.endpoints import get_fuzzy_node_detail, get_integration_status
from app.core.database import Base
from app.models import ControlConfig, FuzzyResult, ZoneControl, ZoneNode
from app.services.fuzzy import DEFAULT_MEMBERSHIP_PARAMS, DEFAULT_RULE_BASE
from app.services.worker import reset_control_state, run_processing_cycle
from app.sources import get_sensor_source
from app.sources.base import SourceBase
from app.sources.paket_valid import PaketValid, SesiUji, session_modes


def _db(nodes=("NODE-01",)):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    SourceBase.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    db.add(ControlConfig(
        config_version="paket-valid-test",
        membership_params=DEFAULT_MEMBERSHIP_PARAMS,
        rule_base=DEFAULT_RULE_BASE,
        dust_low_reference=0.05,
        dust_high_reference=3.50,
        u_off=15.0,
        u_max=88.33,
        d_min=30.0,
        delta_d_update=5.0,
        is_active=True,
    ))
    for node_id in nodes:
        db.add(ZoneNode(zone_id="ZONA-1", node_id=node_id, is_active=True))
    db.commit()
    return db


def _sesi(db, mode="sensor", label="uji adaptor"):
    row = SesiUji(
        mulai=datetime.now(timezone.utc) - timedelta(minutes=5),
        mode=mode,
        label=label,
        freq_hz=433_000_000,
        sf=9,
        bw_hz=125_000,
        cr_denom=5,
        tx_power_dbm=17,
        versi_paket=1,
    )
    db.add(row)
    db.commit()
    return row


def _paket(sesi, **overrides):
    values = dict(
        sesi_uji_id=sesi.id,
        received_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        node_id=1,
        sesi=4242,
        seq=7,
        adc=1000,
        vpin=0.8,
        v0=1.2,
        dust_ugm3=120.0,
        temperature=28.0,
        humidity=52.0,
        pressure_hpa=1008.0,
        rssi=-80,
        snr=7.5,
        payload_raw=b"sample",
    )
    values.update(overrides)
    return PaketValid(**values)


@pytest.fixture(autouse=True)
def paket_source(monkeypatch):
    monkeypatch.setattr(ops, "SENSOR_SOURCE", "paket_valid")
    monkeypatch.setattr(ops, "PAKET_VALID_SESSION_MODES", "")
    monkeypatch.setattr(ops, "FRESHNESS_SECONDS", 30)
    reset_control_state()
    yield
    reset_control_state()


def test_selector_returns_paket_valid_source():
    assert get_sensor_source().name == "paket_valid"


def test_unknown_source_is_rejected_instead_of_falling_back_to_mock(monkeypatch):
    monkeypatch.setattr(ops, "SENSOR_SOURCE", "paket-valid")
    with pytest.raises(ValueError, match="tidak dikenal"):
        get_sensor_source()


def test_row_maps_to_sensor_reading_contract():
    db = _db()
    sesi = _sesi(db)
    db.add(_paket(sesi, node_id=2, v0=1.75, rssi=-91, snr=4.25, seq=99))
    db.commit()
    row = get_sensor_source().latest(db, "NODE-02")
    assert row.node_id == "NODE-02"
    assert row.dust_raw_voltage == pytest.approx(1.75)   # v0, bukan dust_ugm3
    assert row.status_valid is True
    assert row.inputs_complete is True
    assert (row.rssi, row.snr, row.seq) == (-91, 4.25, 99)


def test_latest_uses_received_at_then_id():
    db = _db()
    sesi = _sesi(db)
    t = datetime.now(timezone.utc) - timedelta(seconds=2)
    db.add_all([
        _paket(sesi, received_at=t - timedelta(seconds=5), temperature=20.0),
        _paket(sesi, received_at=t, temperature=21.0),
        _paket(sesi, received_at=t, temperature=22.0),   # timestamp sama, id lebih besar
    ])
    db.commit()
    assert get_sensor_source().latest(db, "NODE-01").temperature == 22.0
    assert get_sensor_source().latest_any(db).temperature == 22.0


def test_history_is_ascending_and_respects_cutoff():
    db = _db()
    sesi = _sesi(db)
    now = datetime.now(timezone.utc)
    db.add_all([
        _paket(sesi, received_at=now - timedelta(hours=2), seq=1),
        _paket(sesi, received_at=now - timedelta(minutes=2), seq=2),
        _paket(sesi, received_at=now - timedelta(minutes=1), seq=3),
    ])
    db.commit()
    rows = get_sensor_source().history(db, "NODE-01", now - timedelta(hours=1))
    assert [r.seq for r in rows] == [2, 3]


def test_unknown_node_label_returns_nothing():
    db = _db()
    assert get_sensor_source().latest(db, "ruang-a") is None
    assert get_sensor_source().history(db, "ruang-a", datetime.now(timezone.utc)) == []


def test_session_mode_filter_is_optional(monkeypatch):
    db = _db()
    sensor = _sesi(db, mode="sensor")
    uji = _sesi(db, mode="uji", label="50 m")
    now = datetime.now(timezone.utc)
    db.add_all([
        _paket(sensor, received_at=now - timedelta(seconds=5), temperature=25.0),
        _paket(uji, received_at=now - timedelta(seconds=1), temperature=35.0),
    ])
    db.commit()

    # Default: semua sesi dipakai, baris terbaru berasal dari sesi uji.
    assert session_modes() == ()
    assert get_sensor_source().latest(db, "NODE-01").temperature == 35.0

    monkeypatch.setattr(ops, "PAKET_VALID_SESSION_MODES", " Sensor ")
    assert session_modes() == ("sensor",)
    assert get_sensor_source().latest(db, "NODE-01").temperature == 25.0
    assert get_sensor_source().latest_any(db).temperature == 25.0


def test_incomplete_packet_is_valid_but_not_processed():
    db = _db()
    sesi = _sesi(db)
    db.add(_paket(sesi, temperature=None))
    db.commit()
    row = get_sensor_source().latest(db, "NODE-01")
    assert row.status_valid is True and row.inputs_complete is False
    result = run_processing_cycle(db)
    assert result["nodes_evaluated"] == 0
    assert db.query(FuzzyResult).count() == 0
    with pytest.raises(HTTPException) as exc:
        get_fuzzy_node_detail("NODE-01", db)
    assert exc.value.status_code == 422


def test_worker_processes_fresh_packet_without_touching_source_tables():
    db = _db(nodes=("NODE-01", "NODE-02"))
    sesi = _sesi(db)
    db.add_all([
        _paket(sesi, node_id=1, v0=0.3),
        _paket(sesi, node_id=2, v0=3.2, temperature=33.0, humidity=70.0),
    ])
    db.commit()
    before = [(p.id, p.received_at, p.v0) for p in db.query(PaketValid).order_by(PaketValid.id)]

    result = run_processing_cycle(db)
    assert result["nodes_evaluated"] == 2
    assert result["zone_decision"]["determining_node_id"] == "NODE-02"
    assert result["applied_pwm"] > 0
    assert db.query(FuzzyResult).count() == 2
    stored = db.query(FuzzyResult).order_by(FuzzyResult.fuzzy_result_id).all()
    assert {r.source_record_id for r in stored} == {b[0] for b in before}

    # Siklus kedua memakai hasil tersimpan, tidak menghitung ulang.
    again = run_processing_cycle(db)
    assert again["new_results"] == 0
    after = [(p.id, p.received_at, p.v0) for p in db.query(PaketValid).order_by(PaketValid.id)]
    assert after == before
    assert db.query(SesiUji).count() == 1


def test_stale_packet_produces_no_control():
    db = _db()
    sesi = _sesi(db)
    db.add(_paket(sesi, received_at=datetime.now(timezone.utc) - timedelta(seconds=120)))
    db.commit()
    result = run_processing_cycle(db)
    assert result["nodes_evaluated"] == 0
    assert result["applied_pwm"] == 0.0
    last = db.query(ZoneControl).order_by(ZoneControl.zone_control_id.desc()).first()
    assert last.control_node_id is None


def test_status_reports_paket_valid_metadata():
    db = _db()
    sesi = _sesi(db)
    db.add(_paket(sesi))
    db.commit()
    status = get_integration_status(db)
    assert status["source"]["mode"] == "paket_valid"
    assert status["source"]["available"] is True
    assert status["source"]["last_node_id"] == "NODE-01"
    assert status["nodes"][0]["snr"] == 7.5


def test_status_flags_missing_paket_valid_table():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    db.add(ZoneNode(zone_id="ZONA-1", node_id="NODE-01", is_active=True))
    db.commit()
    status = get_integration_status(db)
    assert status["database"]["connected"] is True
    assert status["source"]["available"] is False


def _import_settings_with(env):
    import subprocess
    backend = os.path.join(os.path.dirname(__file__), "..", "backend")
    full_env = {**os.environ, **env}
    return subprocess.run(
        [sys.executable, "-c", "import app.settings, app.core.config"],
        cwd=backend, env=full_env, capture_output=True, text=True,
    )


def test_invalid_sensor_source_env_stops_startup():
    proc = _import_settings_with({"SENSOR_SOURCE": "paketvalid"})
    assert proc.returncode != 0
    assert "tidak dikenal" in proc.stderr


def test_invalid_schema_name_env_stops_startup():
    proc = _import_settings_with({"SENSOR_SOURCE": "mock", "APP_DB_SCHEMA": "wsnova; drop"})
    assert proc.returncode != 0
    assert "APP_DB_SCHEMA" in proc.stderr
