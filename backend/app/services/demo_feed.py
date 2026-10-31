"""Generator data tiruan opsional untuk deployment demo satu layanan."""

import asyncio
import logging
from datetime import datetime, timezone

from dummy_profile import PROFILE, Generator

from app.core.database import SessionLocal
from app.models import MockReceiverValidData

logger = logging.getLogger("wsn.demo_feed")


async def demo_feed_loop(interval_seconds: float, stop_event: asyncio.Event) -> None:
    """Kirim pembacaan baru sampai aplikasi dimatikan."""
    interval = max(float(interval_seconds), 1.0)
    generator = Generator()

    while not stop_event.is_set():
        now = datetime.now(timezone.utc)
        local = now.astimezone()
        hour = local.hour + local.minute / 60 + local.second / 3600
        db = SessionLocal()
        try:
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
