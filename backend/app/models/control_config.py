from sqlalchemy import Column, String, Float, Boolean, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base

class ControlConfig(Base):
    __tablename__ = "control_config"

    config_version = Column(String(50), primary_key=True)
    # Gunakan JSONB untuk PostgreSQL, fallback ke JSON generik
    membership_params = Column(JSONB().with_variant(JSON, "sqlite"), nullable=False)
    rule_base = Column(JSONB().with_variant(JSON, "sqlite"), nullable=False)
    
    dust_low_reference = Column(Float, nullable=False)
    dust_high_reference = Column(Float, nullable=False)
    u_off = Column(Float, nullable=False)
    u_max = Column(Float, nullable=False)
    d_min = Column(Float, nullable=False)
    delta_d_update = Column(Float, nullable=False)
    
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Relasi
    fuzzy_results = relationship("FuzzyResult", back_populates="config")
    zone_controls = relationship("ZoneControl", back_populates="config")

    def __repr__(self):
        return f"<ControlConfig(version='{self.config_version}', active={self.is_active})>"
