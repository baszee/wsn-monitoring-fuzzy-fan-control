"""Kontrak pembacaan data sensor tanpa mengikat worker ke tabel tertentu."""

from dataclasses import dataclass
from datetime import datetime, timezone
import math
from typing import Optional, Protocol, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session, declarative_base


# Metadata tabel milik subsistem penerima, sengaja terpisah dari Base aplikasi.
# bootstrap/create_all WSNova tidak pernah membuat, mengubah, atau menghapus
# tabel ini; hanya tes dan simulator SQLite yang membuatnya secara eksplisit.
SourceBase = declarative_base()


def _as_datetime(value) -> datetime:
    """Normalisasi hasil CURRENT_TIMESTAMP SQLite/PostgreSQL menjadi datetime UTC."""
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace(" ", "T"))
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def database_now(db: Session) -> datetime:
    """Ambil jam dari basis data sumber, bukan jam komputer yang menjalankan API."""
    value = db.execute(select(func.current_timestamp())).scalar_one()
    return _as_datetime(value)


@dataclass(frozen=True)
class SensorReading:
    id: int
    node_id: str
    temperature: Optional[float]
    humidity: Optional[float]
    dust_raw_voltage: Optional[float]
    timestamp: datetime
    status_valid: bool
    pressure_hpa: Optional[float] = None
    rssi: Optional[int] = None
    snr: Optional[float] = None
    seq: Optional[int] = None

    @property
    def inputs_complete(self) -> bool:
        """Kelengkapan fuzzy terpisah dari validitas paket receiver."""
        values = (self.temperature, self.humidity, self.dust_raw_voltage)
        return all(value is not None and math.isfinite(float(value)) for value in values)


class SensorSource(Protocol):
    name: str

    def latest(self, db: Session, node_id: str) -> Optional[SensorReading]: ...

    def history(
        self, db: Session, node_id: str, cutoff: datetime
    ) -> Sequence[SensorReading]: ...

    def latest_any(self, db: Session) -> Optional[SensorReading]: ...

    def db_now(self, db: Session) -> datetime: ...

