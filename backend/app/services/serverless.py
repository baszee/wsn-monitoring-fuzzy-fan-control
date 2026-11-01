"""Pemicu siklus berbasis request untuk deployment function-as-a-service."""

from sqlalchemy import text
from sqlalchemy.orm import Session

from app import settings as ops
from app.services.demo_feed import ensure_demo_snapshot
from app.services.worker import run_processing_cycle


_ADVISORY_LOCK_KEY = 878_066_201


def run_request_cycle(db: Session) -> None:
    """Buat data demo bila perlu lalu jalankan satu siklus secara atomik.

    PostgreSQL advisory lock mencegah dua instance serverless memproses snapshot
    yang sama secara bersamaan. SQLite tetap bekerja tanpa lock untuk pengujian
    lokal.
    """
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(:key)"),
            {"key": _ADVISORY_LOCK_KEY},
        )

    if ops.DEMO_MODE:
        ensure_demo_snapshot(db, ops.DEMO_FEED_INTERVAL_SECONDS)

    run_processing_cycle(db=db)
