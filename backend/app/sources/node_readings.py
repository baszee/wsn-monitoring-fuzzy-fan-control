"""Adaptor read-only untuk tabel ``node_readings`` milik subsistem penerima M2."""

from datetime import datetime
import re
from typing import Optional, Sequence

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Float,
    Integer,
    LargeBinary,
    SmallInteger,
)
from sqlalchemy.orm import Session, declarative_base

from app.sources.base import SensorReading, database_now


# Metadata sengaja dipisahkan dari Base aplikasi. bootstrap/create_all milik Abbas
# tidak akan membuat, mengubah, atau menghapus tabel milik M2.
SourceBase = declarative_base()


class NodeReading(SourceBase):
    __tablename__ = "node_readings"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    received_at = Column(DateTime(timezone=True), nullable=False)
    node_id = Column(SmallInteger, nullable=False, index=True)
    seq = Column(Integer, nullable=False)
    adc = Column(Integer, nullable=False)
    vpin = Column(Float, nullable=False)
    v0 = Column(Float, nullable=False)
    dust_ugm3 = Column(Float, nullable=False)
    temperature = Column(Float, nullable=True)
    humidity = Column(Float, nullable=True)
    pressure_hpa = Column(Float, nullable=True)
    rssi = Column(SmallInteger, nullable=False)
    snr = Column(Float, nullable=False)
    payload_raw = Column(LargeBinary, nullable=False)


_NODE_LABEL = re.compile(r"^NODE-(\d+)$", re.IGNORECASE)


def source_node_id(label: str) -> Optional[int]:
    """Terjemahkan label UI ``NODE-01`` atau ``1`` menjadi ID numerik M2."""
    text = str(label).strip()
    match = _NODE_LABEL.fullmatch(text)
    if match:
        return int(match.group(1))
    return int(text) if text.isdigit() else None


def display_node_id(value: int) -> str:
    """Pertahankan kontrak label frontend tanpa mengubah tabel M2."""
    return f"NODE-{int(value):02d}"


def _reading(row: NodeReading) -> SensorReading:
    return SensorReading(
        id=row.id,
        node_id=display_node_id(row.node_id),
        temperature=row.temperature,
        humidity=row.humidity,
        dust_raw_voltage=row.v0,
        timestamp=row.received_at,
        # Receiver M2 hanya memasukkan paket yang lolos CRC/decode. Kelengkapan
        # suhu/RH/debu diperiksa terpisah melalui SensorReading.inputs_complete.
        status_valid=True,
        pressure_hpa=row.pressure_hpa,
        rssi=row.rssi,
        snr=row.snr,
        seq=row.seq,
    )


class NodeReadingsSensorSource:
    name = "node_readings"

    def latest(self, db: Session, node_id: str) -> Optional[SensorReading]:
        external_id = source_node_id(node_id)
        if external_id is None:
            return None
        row = (
            db.query(NodeReading)
            .filter(NodeReading.node_id == external_id)
            .order_by(NodeReading.received_at.desc(), NodeReading.id.desc())
            .first()
        )
        return _reading(row) if row else None

    def history(
        self, db: Session, node_id: str, cutoff: datetime
    ) -> Sequence[SensorReading]:
        external_id = source_node_id(node_id)
        if external_id is None:
            return []
        rows = (
            db.query(NodeReading)
            .filter(
                NodeReading.node_id == external_id,
                NodeReading.received_at >= cutoff,
            )
            .order_by(NodeReading.received_at.asc(), NodeReading.id.asc())
            .all()
        )
        return [_reading(row) for row in rows]

    def latest_any(self, db: Session) -> Optional[SensorReading]:
        row = (
            db.query(NodeReading)
            .order_by(NodeReading.received_at.desc(), NodeReading.id.desc())
            .first()
        )
        return _reading(row) if row else None

    def db_now(self, db: Session) -> datetime:
        return database_now(db)

