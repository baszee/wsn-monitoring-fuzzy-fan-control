"""Generator data tiruan opsional untuk deployment demo satu layanan."""

import asyncio
import logging
from datetime import datetime, timezone

from dummy_profile import PROFILE, Generator
from sqlalchemy.orm import Session

from app import settings as ops
from app.core.database import SessionLocal
from app.models import MockReceiverValidData
from app.services.freshness import age_seconds

logger = logging.getLogger("wsn.demo_feed")
generator = Generator()


def _virtual_hour(now: datetime, cycle_seconds: float) -> float:
    """Petakan satu siklus demo singkat ke profil lingkungan 24 jam.

    Generator tidak lagi mengikuti zona waktu server. Dengan demikian hasil
    demo konsisten di laptop, Vercel, maupun Orange Pi dan kondisi kendali
    tinggi dapat terlihat tanpa menunggu jam tertentu.
    """
    cycle = max(float(cycle_seconds), 60.0)
    return (now.timestamp() % cycle) / cycle * 24.0


def ensure_demo_snapshot(
    db: Session,
    interval_seconds: float,
    *,
    force: bool = False,
) -> bool:
    """Tambahkan satu snapshot per node bila snapshot terakhir sudah waktunya diperbarui."""
    interval = max(float(interval_seconds), 1.0)
    now = datetime.now(timezone.utc)

    if not force:
        latest = (
            db.query(MockReceiverValidData)
            .order_by(MockReceiverValidData.timestamp.desc())
            .first()
        )
        if latest is not None and age_seconds(latest.timestamp, now) < interval:
            return False

    hour = _virtual_hour(now, ops.DEMO_CYCLE_SECONDS)
    for node_id in [n for n in ops.ZONE_NODE_IDS if n in PROFILE]:
        temperature, humidity, dust = generator.sample(node_id, hour, interval)
        db.add(MockReceiverValidData(
            node_id=node_id,
            temperature=temperature,
            humidity=humidity,
            dust_raw_voltage=dust,
            timestamp=now,
            status_valid=True,
        ))
    return True


async def demo_feed_loop(interval_seconds: float, stop_event: asyncio.Event) -> None:
    """Kirim pembacaan baru sampai aplikasi dimatikan."""
    interval = max(float(interval_seconds), 1.0)
    while not stop_event.is_set():
        db = SessionLocal()
        try:
            ensure_demo_snapshot(db, interval, force=True)
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Gagal menambahkan data demo")
        finally:
            db.close()

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass
