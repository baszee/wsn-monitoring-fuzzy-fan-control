"""Kontrak adaptor sumber sensor mock dan node_readings M2."""

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
from app.models import ControlConfig, FuzzyResult, ZoneNode
from app.services.fuzzy import DEFAULT_MEMBERSHIP_PARAMS, DEFAULT_RULE_BASE
from app.services.worker import (
    _apply_auto_failsafe,
    control_state,
    global_fan_controller,
    reset_control_state,
    run_processing_cycle,
)
from app.sources import get_sensor_source
from app.sources.node_readings import NodeReading, SourceBase, display_node_id, source_node_id


def _db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    SourceBase.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    db.add(ControlConfig(
        config_version="source-test",
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
    db.add(ZoneNode(zone_id="ZONA-1", node_id="NODE-01", is_active=True))
    db.commit()
    return db


def _reading(**overrides):
    values = dict(
        received_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        node_id=1,
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
    return NodeReading(**values)


@pytest.fixture(autouse=True)
def node_source(monkeypatch):
    monkeypatch.setattr(ops, "SENSOR_SOURCE", "node_readings")
    monkeypatch.setattr(ops, "FRESHNESS_SECONDS", 30)


def test_node_label_mapping_is_local_to_adapter():
    assert source_node_id("NODE-01") == 1
    assert source_node_id("1") == 1
    assert source_node_id("ruang-a") is None
    assert display_node_id(3) == "NODE-03"


def test_persisted_packet_is_valid_but_can_be_incomplete():
    db = _db()
    db.add(_reading(temperature=None))
    db.commit()
    row = get_sensor_source().latest(db, "NODE-01")
    assert row.status_valid is True
    assert row.inputs_complete is False


def test_worker_reads_node_readings_without_changing_m2_table():
    db = _db()
    db.add(_reading())
    db.commit()
    result = run_processing_cycle(db)
    assert result["nodes_evaluated"] == 1
    assert db.query(FuzzyResult).count() == 1
    assert db.query(NodeReading).count() == 1


def test_fuzzy_detail_returns_422_for_incomplete_inputs():
    db = _db()
    db.add(_reading(humidity=None))
    db.commit()
    with pytest.raises(HTTPException) as exc:
        get_fuzzy_node_detail("NODE-01", db)
    assert exc.value.status_code == 422


def test_status_reports_source_and_latest_metadata():
    db = _db()
    db.add(_reading())
    db.commit()
    status = get_integration_status(db)
    assert status["database"]["connected"] is True
    assert status["source"]["mode"] == "node_readings"
    assert status["source"]["last_node_id"] == "NODE-01"
    assert status["nodes"][0]["rssi"] == -80


def test_status_distinguishes_database_from_missing_source_table():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    status = get_integration_status(db)
    assert status["database"]["connected"] is True
    assert status["source"]["available"] is False


def test_database_failure_stops_auto_but_not_manual():
    reset_control_state()
    global_fan_controller.driver.set_duty_cycle(70)
    control_state.update(mode="auto", applied_pwm=70.0)
    _apply_auto_failsafe(RuntimeError("database unavailable"))
    assert global_fan_controller.driver.get_duty_cycle() == 0.0

    global_fan_controller.driver.set_duty_cycle(35)
    control_state.update(mode="manual", manual_pwm=35.0, applied_pwm=35.0)
    _apply_auto_failsafe(RuntimeError("database unavailable"))
    assert global_fan_controller.driver.get_duty_cycle() == 35.0
    reset_control_state()

