"""Pengujian login admin, mode Manual, dan batas permintaan (PRD 19.5 dan 18)."""
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import settings as ops
from app.core.config import settings
from app.core.database import Base, get_db
from app.core.ratelimit import reset_rate_limits
from app.core.security import hash_password, login_limiter, sessions
from app.main import app
from app.models import ControlConfig, FuzzyResult, MockReceiverValidData, ZoneControl, ZoneNode
from app.services.fuzzy import DEFAULT_MEMBERSHIP_PARAMS, DEFAULT_RULE_BASE
from app.services.pwm import FanPWMController, MockPWMDriver
from app.services.worker import (
    apply_auto, apply_manual, control_state, global_fan_controller, reset_control_state, run_processing_cycle,
)

USER, PASSWORD = "wsnova", "11november"
HASH = hash_password(PASSWORD)


def _make_db():
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


def _record(db, age_s=1):
    db.add(MockReceiverValidData(
        node_id="NODE-01", temperature=34.0, humidity=30.0, dust_raw_voltage=3.0,
        timestamp=datetime.now(timezone.utc) - timedelta(seconds=age_s), status_valid=True))
    db.commit()


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    ops.FRESHNESS_SECONDS = 10
    monkeypatch.setattr(settings, "ADMIN_USERNAME", USER)
    monkeypatch.setattr(settings, "ADMIN_PASSWORD_HASH", HASH)
    monkeypatch.setattr(settings, "COOKIE_SECURE", False)
    sessions.clear(); login_limiter.clear(); reset_rate_limits(); reset_control_state()
    yield
    app.dependency_overrides.clear()
    sessions.clear(); login_limiter.clear(); reset_rate_limits(); reset_control_state()


@pytest.fixture
def db():
    d = _make_db()
    app.dependency_overrides[get_db] = lambda: d
    return d


@pytest.fixture
def client(db):
    return TestClient(app)


def _login(client):
    r = client.post("/api/auth/login", json={"username": USER, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"X-CSRF-Token": r.json()["csrf_token"]}


def _driver_pwm():
    return global_fan_controller.driver.get_duty_cycle()


# ── Login ────────────────────────────────────────────────────────────────────
def test_login_ok_sets_httponly_strict_cookie(client):
    r = client.post("/api/auth/login", json={"username": USER, "password": PASSWORD})
    cookie = r.headers["set-cookie"].lower()
    assert r.status_code == 200 and r.json()["authenticated"] is True
    assert "httponly" in cookie and "samesite=strict" in cookie
    assert client.get("/api/auth/session").json()["authenticated"] is True


def test_session_is_public_and_anonymous_by_default(client):
    body = client.get("/api/auth/session").json()
    assert body == {"authenticated": False, "username": None, "csrf_token": None}


def test_login_wrong_password_rejected(client):
    r = client.post("/api/auth/login", json={"username": USER, "password": "salah"})
    assert r.status_code == 401
    assert client.get("/api/auth/session").json()["authenticated"] is False


def test_login_locked_after_five_failures_even_with_right_password(client):
    for _ in range(5):
        assert client.post("/api/auth/login", json={"username": USER, "password": "salah"}).status_code == 401
    r = client.post("/api/auth/login", json={"username": USER, "password": PASSWORD})
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0


def test_logout_revokes_session(client):
    csrf = _login(client)
    assert client.post("/api/auth/logout", headers=csrf).status_code == 200
    assert client.get("/api/auth/session").json()["authenticated"] is False


# ── Otorisasi ────────────────────────────────────────────────────────────────
def test_control_requests_without_login_are_rejected(client):
    assert client.post("/api/control/manual", json={"pwm_percent": 50}).status_code == 401
    assert client.post("/api/control/auto").status_code == 401
    assert _driver_pwm() == 0.0


def test_control_request_without_csrf_token_is_rejected(client):
    _login(client)
    assert client.post("/api/control/manual", json={"pwm_percent": 50}).status_code == 403
    assert _driver_pwm() == 0.0


# ── Validasi dan penerapan Manual ────────────────────────────────────────────
@pytest.mark.parametrize("value", [0, 50, 100, 33.5])
def test_manual_accepts_valid_values(client, value):
    csrf = _login(client)
    r = client.post("/api/control/manual", json={"pwm_percent": value}, headers=csrf)
    assert r.status_code == 200, r.text
    assert r.json()["pwm_command_percent"] == value and r.json()["control_mode"] == "manual"
    assert _driver_pwm() == value


@pytest.mark.parametrize("payload", [{"pwm_percent": -1}, {"pwm_percent": 100.5}, {"pwm_percent": 101},
                                     {"pwm_percent": "abc"}, {"pwm_percent": "50"}, {"pwm_percent": None},
                                     {"pwm_percent": True}, {}])
def test_manual_rejects_invalid_values(client, payload):
    csrf = _login(client)
    assert client.post("/api/control/manual", json=payload, headers=csrf).status_code == 422
    assert _driver_pwm() == 0.0 and control_state["mode"] == "auto"


def test_manual_rejects_nan(client):
    csrf = _login(client)
    r = client.post("/api/control/manual", content='{"pwm_percent": NaN}',
                    headers={**csrf, "Content-Type": "application/json"})
    assert r.status_code == 422


def test_manual_applies_immediately_and_writes_new_row(client, db):
    csrf = _login(client)
    before = db.query(ZoneControl).count()
    client.post("/api/control/manual", json={"pwm_percent": 50}, headers=csrf)
    rows = db.query(ZoneControl).order_by(ZoneControl.zone_control_id).all()
    assert len(rows) == before + 1
    last = rows[-1]
    assert last.control_mode == "manual" and last.pwm_command_percent == 50.0
    assert last.processing_cycle_id.startswith("MAN-")
    assert _driver_pwm() == 50.0


def test_manual_without_auto_data_marks_control_unavailable(client, db):
    csrf = _login(client)
    client.post("/api/control/manual", json={"pwm_percent": 55}, headers=csrf)
    last = db.query(ZoneControl).order_by(ZoneControl.zone_control_id.desc()).first()
    assert last.control_status == "Kendali tidak tersedia"
    assert last.auto_pwm_percent == 0.0 and last.pwm_command_percent == 55.0
    assert last.control_node_id is None and last.control_fuzzy_result_id is None


def test_manual_row_copies_latest_auto_result_as_comparison(client, db):
    _record(db)
    run_processing_cycle(db)
    auto_pwm = _driver_pwm()
    assert auto_pwm > 40
    csrf = _login(client)
    client.post("/api/control/manual", json={"pwm_percent": 20}, headers=csrf)
    last = db.query(ZoneControl).order_by(ZoneControl.zone_control_id.desc()).first()
    assert last.pwm_command_percent == 20.0
    assert last.auto_pwm_percent == pytest.approx(auto_pwm)
    assert last.control_node_id == "NODE-01" and last.control_fuzzy_result_id is not None


def test_fuzzy_and_auto_pwm_keep_updating_during_manual(client, db):
    _record(db, 3)
    run_processing_cycle(db)
    csrf = _login(client)
    client.post("/api/control/manual", json={"pwm_percent": 20}, headers=csrf)
    fuzzy_before = db.query(FuzzyResult).count()
    _record(db, 1)
    result = run_processing_cycle(db)
    assert db.query(FuzzyResult).count() == fuzzy_before + 1        # fuzzy tetap dihitung dan disimpan
    assert _driver_pwm() == 20.0                                    # fisik mengikuti Manual
    last = db.query(ZoneControl).order_by(ZoneControl.zone_control_id.desc()).first()
    assert last.control_mode == "manual" and last.pwm_command_percent == 20.0
    assert last.auto_pwm_percent > 40                               # pembanding otomatis tetap diperbarui
    assert result["control_mode"] == "manual"


def test_manual_pwm_is_resent_each_worker_cycle_for_hardware_watchdog(db):
    """Regresi: Manual tidak boleh timeout setelah satu perintah awal."""
    controller = FanPWMController(driver=MockPWMDriver())
    _record(db)
    apply_manual(db, 73, controller=controller)
    commands_after_click = len(controller.driver.history)

    run_processing_cycle(db, controller=controller)

    assert len(controller.driver.history) == commands_after_click + 1
    assert controller.driver.history[-1]["pwm_percent"] == 73.0
    assert controller.driver.get_duty_cycle() == 73.0


def test_back_to_auto_resets_hysteresis_and_follows_latest_auto(client, db):
    _record(db)
    run_processing_cycle(db)
    csrf = _login(client)
    client.post("/api/control/manual", json={"pwm_percent": 10}, headers=csrf)
    assert _driver_pwm() == 10.0
    r = client.post("/api/control/auto", headers=csrf)
    assert r.status_code == 200 and r.json()["control_mode"] == "auto"
    assert _driver_pwm() > 40                                       # langsung mengikuti hasil otomatis
    last = db.query(ZoneControl).order_by(ZoneControl.zone_control_id.desc()).first()
    assert last.control_mode == "auto" and last.previous_pwm_percent == 0.0
    assert last.pwm_command_percent == last.auto_pwm_percent


def test_app_starts_in_auto_with_zero_pwm():
    apply_manual(_make_db(), 80)
    reset_control_state()                       # keadaan yang sama dengan proses yang baru dijalankan
    assert control_state["mode"] == "auto" and control_state["applied_pwm"] == 0.0
    assert _driver_pwm() == 0.0


# ── Batas permintaan ─────────────────────────────────────────────────────────
def test_history_is_rate_limited(client):
    codes = [client.get("/api/control/history?range=1h").status_code for _ in range(62)]
    assert codes[:60] == [200] * 60 and codes[60] == 429
