"""Adaptor untuk sumber data tiruan yang sudah digunakan aplikasi."""

from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy.orm import Session

from app.models.receiver import MockReceiverValidData
from app.sources.base import SensorReading, database_now


def _reading(row: MockReceiverValidData) -> SensorReading:
    return SensorReading(
        id=row.id,
        node_id=row.node_id,
        temperature=row.temperature,
        humidity=row.humidity,
        dust_raw_voltage=row.dust_raw_voltage,
        timestamp=row.timestamp,
        status_valid=bool(row.status_valid),
    )


class MockSensorSource:
    name = "mock"

    def latest(self, db: Session, node_id: str) -> Optional[SensorReading]:
        row = (
            db.query(MockReceiverValidData)
            .filter(MockReceiverValidData.node_id == node_id)
            .order_by(MockReceiverValidData.timestamp.desc())
            .first()
        )
        return _reading(row) if row else None

    def history(
        self, db: Session, node_id: str, cutoff: datetime
    ) -> Sequence[SensorReading]:
        rows = (
            db.query(MockReceiverValidData)
            .filter(
                MockReceiverValidData.node_id == node_id,
                MockReceiverValidData.timestamp >= cutoff,
            )
            .order_by(MockReceiverValidData.timestamp.asc())
            .all()
        )
        return [_reading(row) for row in rows]

    def latest_any(self, db: Session) -> Optional[SensorReading]:
        row = (
            db.query(MockReceiverValidData)
            .order_by(MockReceiverValidData.timestamp.desc())
            .first()
        )
        return _reading(row) if row else None

    def db_now(self, db: Session) -> datetime:
        return database_now(db)

