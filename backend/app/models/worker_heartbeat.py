from sqlalchemy import Column, DateTime, Integer, String, func

from app.core.database import Base


class WorkerHeartbeat(Base):
    """Detak worker pengendali, agar instance tampilan (mis. Vercel) tahu
    bahwa perangkat pengendali (laptop/Orange Pi) masih memproses data."""

    __tablename__ = "worker_heartbeats"

    worker_id = Column(String(32), primary_key=True)
    last_cycle_at = Column(DateTime(timezone=True), nullable=True)
    last_source_time = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(String(128), nullable=True)
    last_error_at = Column(DateTime(timezone=True), nullable=True)
    interval_seconds = Column(Integer, nullable=False, default=1)
    source_mode = Column(String(32), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
