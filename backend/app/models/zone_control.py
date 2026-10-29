from sqlalchemy import Column, BigInteger, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base

class ZoneControl(Base):
    __tablename__ = "zone_controls"

    zone_control_id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True, autoincrement=True)
    config_version = Column(String(50), ForeignKey("control_config.config_version"), nullable=False)
    processing_cycle_id = Column(String(100), nullable=False, index=True)
    zone_id = Column(String(50), nullable=False)
    
    # ID hasil fuzzy dari node penentu (i*), bernilai NULL jika V = kosong / kendali tidak tersedia
    control_fuzzy_result_id = Column(
        BigInteger, 
        ForeignKey("fuzzy_results.fuzzy_result_id", ondelete="SET NULL"), 
        nullable=True
    )
    control_node_id = Column(String(50), nullable=True)          # node penentu i*
    zone_control_level = Column(Float, nullable=True)             # u_zona = max(u_i)
    pwm_command_percent = Column(Float, nullable=False)           # Duty cycle PWM (0 - 100%)
    
    control_status = Column(String(50), nullable=False)           # 'Aktif', 'Mati', 'Kendali tidak tersedia'
    fan_command_status = Column(String(50), nullable=False)       # 'Aktif', 'Mati', 'Kendali tidak tersedia'
    control_mode = Column(String(20), nullable=False, default="auto")  # 'auto' / 'manual'
    
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Relasi
    config = relationship("ControlConfig", back_populates="zone_controls")
    determining_fuzzy_result = relationship("FuzzyResult", back_populates="zone_controls")

    def __repr__(self):
        return f"<ZoneControl(id={self.zone_control_id}, zone='{self.zone_id}', u_zona={self.zone_control_level}, pwm={self.pwm_command_percent}%, mode='{self.control_mode}')>"
