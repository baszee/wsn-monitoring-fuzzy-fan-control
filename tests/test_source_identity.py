"""Identitas sumber mencegah benturan ID rekaman lintas adaptor."""

from datetime import datetime, timezone
import os
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.core.database import Base
from app.models import ControlConfig, FuzzyResult, ZoneNode
from app.services.fuzzy import DEFAULT_MEMBERSHIP_PARAMS, DEFAULT_RULE_BASE


def _result(source_name: str) -> FuzzyResult:
    return FuzzyResult(
        zone_node_id=1,
        config_version="source-id-test",
        processing_cycle_id=f"CYC-{source_name}",
        source_name=source_name,
        source_record_id=1,
        source_timestamp=datetime.now(timezone.utc),
        temperature=25,
        humidity=50,
        dust_raw_voltage=0.5,
        dust_index=0.2,
        condition_score=20,
        condition_class="Baik",
        control_level=10,
    )


def _db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add(ControlConfig(
        config_version="source-id-test",
        membership_params=DEFAULT_MEMBERSHIP_PARAMS,
        rule_base=DEFAULT_RULE_BASE,
        dust_low_reference=0.05,
        dust_high_reference=3.5,
        u_off=15,
        u_max=88.33,
        d_min=30,
        delta_d_update=5,
        is_active=True,
    ))
    db.add(ZoneNode(zone_node_id=1, zone_id="ZONA-1", node_id="NODE-01", is_active=True))
    db.commit()
    return db


def test_same_record_id_is_allowed_for_different_sources():
    db = _db()
    db.add_all([_result("mock"), _result("paket_valid")])
    db.commit()
    assert db.query(FuzzyResult).count() == 2


def test_duplicate_within_same_source_is_rejected():
    db = _db()
    db.add(_result("paket_valid"))
    db.commit()
    db.add(_result("paket_valid"))
    with pytest.raises(IntegrityError):
        db.commit()
