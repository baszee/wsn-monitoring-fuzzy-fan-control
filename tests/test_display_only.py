"""Instance tampilan (Vercel): tidak mengubah kipas, status worker dari detak DB."""

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
from app.api import endpoints
from app.core.database import Base
from app.models import WorkerHeartbeat
from app.services import worker


@pytest.fixture()
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine)
    session = factory()
    yield session, factory
    session.close()


def test_display_only_rejects_mode_changes(monkeypatch):
    monkeypatch.setattr(ops, "DISPLAY_ONLY", True)
    with pytest.raises(HTTPException) as exc:
        endpoints._require_control_instance()
    assert exc.value.status_code == 409


def test_controller_instance_allows_mode_changes(monkeypatch):
    monkeypatch.setattr(ops, "DISPLAY_ONLY", False)
    endpoints._require_control_instance()


def test_heartbeat_is_written_and_read_by_display_instance(db, monkeypatch):
    session, factory = db
    monkeypatch.setattr(worker, "SessionLocal", factory)
    monkeypatch.setitem(worker.worker_status, "last_cycle_at", datetime.now(timezone.utc))
    monkeypatch.setitem(worker.worker_status, "last_error", None)
    worker.write_heartbeat(interval_seconds=3, force=True)

    monkeypatch.setattr(ops, "DISPLAY_ONLY", True)
    view = endpoints._worker_view(session)
    assert view["remote"] is True and view["alive"] is True
    assert session.get(WorkerHeartbeat, "main").interval_seconds == 3


def test_old_heartbeat_means_controller_is_down(db, monkeypatch):
    session, _ = db
    session.add(WorkerHeartbeat(worker_id="main", interval_seconds=3,
                                updated_at=datetime.now(timezone.utc) - timedelta(minutes=5)))
    session.commit()
    monkeypatch.setattr(ops, "DISPLAY_ONLY", True)
    assert endpoints._worker_view(session)["alive"] is False


def test_missing_heartbeat_table_is_not_fatal(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    session = sessionmaker(bind=engine)()
    monkeypatch.setattr(ops, "DISPLAY_ONLY", True)
    assert endpoints._worker_view(session)["alive"] is False
