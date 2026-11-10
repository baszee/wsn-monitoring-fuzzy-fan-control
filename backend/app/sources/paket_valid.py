"""Adaptor read-only untuk tabel ``paket_valid`` milik subsistem penerima M2.

Struktur mengikuti ``schema.sql`` penerima: setiap baris ``paket_valid`` adalah
paket sensor yang sudah lolos CRC aplikasi dan menjadi milik satu ``sesi_uji``.
WSNova hanya membaca kedua tabel ini; tidak ada INSERT, UPDATE, DELETE, atau DDL.
"""

from datetime import datetime
from typing import Optional, Sequence, Tuple

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    SmallInteger,
    Text,
)
from sqlalchemy.orm import Query, Session

from app import settings as ops
from app.core.database import SOURCE_SCHEMA
from app.sources.base import SensorReading, SourceBase, database_now
from app.sources.node_readings import display_node_id, source_node_id


def _qualified(table: str) -> str:
    return f"{SOURCE_SCHEMA}.{table}" if SOURCE_SCHEMA else table


class SesiUji(SourceBase):
    __tablename__ = "sesi_uji"
    __table_args__ = {"schema": SOURCE_SCHEMA}

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    mulai = Column(DateTime(timezone=True), nullable=False)
    selesai = Column(DateTime(timezone=True), nullable=True)
    mode = Column(Text, nullable=False)          # 'sensor' | 'uji'
    label = Column(Text, nullable=True)
    freq_hz = Column(Integer, nullable=False)
    sf = Column(SmallInteger, nullable=False)
    bw_hz = Column(Integer, nullable=False)
    cr_denom = Column(SmallInteger, nullable=False)
    tx_power_dbm = Column(SmallInteger, nullable=False)
    versi_paket = Column(SmallInteger, nullable=False)


class PaketValid(SourceBase):
    __tablename__ = "paket_valid"
    __table_args__ = {"schema": SOURCE_SCHEMA}

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    sesi_uji_id = Column(BigInteger, ForeignKey(f"{_qualified('sesi_uji')}.id"), nullable=False)
    received_at = Column(DateTime(timezone=True), nullable=False)
    node_id = Column(SmallInteger, nullable=False)
    sesi = Column(Integer, nullable=False)       # identitas sesi node (acak tiap node menyala)
    seq = Column(Integer, nullable=False)
    adc = Column(Integer, nullable=False)
    vpin = Column(Float, nullable=False)
    v0 = Column(Float, nullable=False)
    temperature = Column(Float, nullable=True)
    humidity = Column(Float, nullable=True)
    pressure_hpa = Column(Float, nullable=True)
    rssi = Column(SmallInteger, nullable=False)
    snr = Column(Float, nullable=False)
    payload_raw = Column(LargeBinary, nullable=False)


def session_modes() -> Tuple[str, ...]:
    """Mode ``sesi_uji`` yang boleh dipakai; kosong berarti semua sesi."""
    raw = getattr(ops, "PAKET_VALID_SESSION_MODES", "") or ""
    return tuple(m.strip().lower() for m in raw.split(",") if m.strip())


def _reading(row: PaketValid) -> SensorReading:
    return SensorReading(
        id=row.id,
        node_id=display_node_id(row.node_id),
        temperature=row.temperature,
        humidity=row.humidity,
        dust_raw_voltage=row.v0,
        timestamp=row.received_at,
        # paket_valid hanya berisi paket yang lolos CRC aplikasi. Kelengkapan
        # suhu/RH/debu diperiksa terpisah melalui SensorReading.inputs_complete.
        status_valid=True,
        pressure_hpa=row.pressure_hpa,
        rssi=row.rssi,
        snr=row.snr,
        seq=row.seq,
    )


class PaketValidSensorSource:
    name = "paket_valid"

    def _query(self, db: Session) -> Query:
        query = db.query(PaketValid)
        modes = session_modes()
        if modes:
            query = query.join(SesiUji, SesiUji.id == PaketValid.sesi_uji_id).filter(
                SesiUji.mode.in_(modes)
            )
        return query

    def latest(self, db: Session, node_id: str) -> Optional[SensorReading]:
        external_id = source_node_id(node_id)
        if external_id is None:
            return None
        row = (
            self._query(db)
            .filter(PaketValid.node_id == external_id)
            .order_by(PaketValid.received_at.desc(), PaketValid.id.desc())
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
            self._query(db)
            .filter(
                PaketValid.node_id == external_id,
                PaketValid.received_at >= cutoff,
            )
            .order_by(PaketValid.received_at.asc(), PaketValid.id.asc())
            .all()
        )
        return [_reading(row) for row in rows]

    def latest_any(self, db: Session) -> Optional[SensorReading]:
        row = (
            self._query(db)
            .order_by(PaketValid.received_at.desc(), PaketValid.id.desc())
            .first()
        )
        return _reading(row) if row else None

    def db_now(self, db: Session) -> datetime:
        return database_now(db)
