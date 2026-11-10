"""Satu aturan kesegaran data untuk worker dan API."""
from datetime import datetime, timezone
from typing import Optional

from app import settings as ops


def as_utc(ts: datetime) -> datetime:
    # SQLite mengembalikan datetime tanpa zona waktu; anggap UTC.
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def age_seconds(ts: datetime, now: Optional[datetime] = None) -> float:
    now = now or datetime.now(timezone.utc)
    return (now - as_utc(ts)).total_seconds()


def is_fresh(ts: datetime, now: Optional[datetime] = None) -> bool:
    """Data cukup baru untuk disebut "Terbaru" di dashboard."""
    return age_seconds(ts, now) <= ops.FRESHNESS_SECONDS


def is_usable_for_control(ts: datetime, now: Optional[datetime] = None) -> bool:
    """Data masih boleh dipakai mengendalikan fan (boleh lebih tua dari is_fresh)."""
    return age_seconds(ts, now) <= max(ops.CONTROL_HOLD_SECONDS, ops.FRESHNESS_SECONDS)
