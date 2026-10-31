import sys
import os
from datetime import datetime, timedelta, timezone

# Pastikan backend/ ada di sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import settings as ops
from app.core.database import Base
from app.models import ControlConfig, ZoneNode, FuzzyResult, ZoneControl, MockReceiverValidData
from app.services.fuzzy import DEFAULT_MEMBERSHIP_PARAMS, DEFAULT_RULE_BASE
from app.services.pwm import FanPWMController, MockPWMDriver
from app.services.worker import run_processing_cycle


def _db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    db.add(ControlConfig(
        config_version="t1", membership_params=DEFAULT_MEMBERSHIP_PARAMS, rule_base=DEFAULT_RULE_BASE,
        dust_low_reference=0.05, dust_high_reference=3.50,
        u_off=15.0, u_max=88.33, d_min=30.0, delta_d_update=5.0, is_active=True))
    db.add(ZoneNode(zone_id="ZONA-1", node_id="NODE-01", is_active=True))
    db.commit()
    return db


def _record(db, age_s):
    db.add(MockReceiverValidData(
        node_id="NODE-01", temperature=34.0, humidity=30.0, dust_raw_voltage=3.0,
        timestamp=datetime.now(timezone.utc) - timedelta(seconds=age_s), status_valid=True))
    db.commit()


def _ctrl():
    return FanPWMController(driver=MockPWMDriver(initial_pwm=0.0))


def test_same_record_is_processed_once():
    ops.FRESHNESS_SECONDS = 10
    db, ctrl = _db(), _ctrl()
    _record(db, 1)
    for _ in range(5):
        run_processing_cycle(db, controller=ctrl)
    assert db.query(FuzzyResult).count() == 1
    assert db.query(ZoneControl).count() == 1


def test_new_record_creates_new_row():
    ops.FRESHNESS_SECONDS = 10
    db, ctrl = _db(), _ctrl()
    _record(db, 2)
    run_processing_cycle(db, controller=ctrl)
    _record(db, 1)
    run_processing_cycle(db, controller=ctrl)
    assert db.query(FuzzyResult).count() == 2


def test_stale_data_turns_fan_off_and_is_unavailable():
    ops.FRESHNESS_SECONDS = 10
    db, ctrl = _db(), _ctrl()
    _record(db, 60)
    r = run_processing_cycle(db, controller=ctrl)
    assert r["nodes_evaluated"] == 0
    assert r["pwm_decision"]["final_pwm"] == 0.0
    assert r["pwm_decision"]["fan_command_status"] == "Kendali tidak tersedia"
    assert db.query(FuzzyResult).count() == 0


def test_previous_pwm_is_old_value():
    ops.FRESHNESS_SECONDS = 10
    db, ctrl = _db(), _ctrl()
    _record(db, 1)
    first = run_processing_cycle(db, controller=ctrl)["pwm_decision"]
    second = run_processing_cycle(db, controller=ctrl)["pwm_decision"]
    assert first["previous_pwm"] == 0.0
    assert second["previous_pwm"] == first["final_pwm"]


def test_simulate_uses_active_config_and_returns_pwm():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.database import get_db
    db = _db()
    app.dependency_overrides[get_db] = lambda: db
    try:
        r = TestClient(app).post("/api/fuzzy/simulate", json={"temperature": 40, "humidity": 20, "dust_index": 1.0})
    finally:
        app.dependency_overrides.clear()
    body = r.json()
    assert r.status_code == 200
    assert body["config_version"] == "t1"
    assert body["candidate_pwm_percent"] > 90.0

