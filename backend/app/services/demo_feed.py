"""Generator data tiruan opsional untuk deployment demo satu layanan."""

import asyncio
import logging
from datetime import datetime, timezone

from dummy_profile import PROFILE, Generator
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models import MockReceiverValidData
from app.services.freshness import age_seconds

logger = logging.getLogger("wsn.demo_feed")
generator = Generator()


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

    local = now.astimezone()
    hour = local.hour + local.minute / 60 + local.second / 3600
    for node_id in PROFILE:
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
