from sqlalchemy import Column, Integer, BigInteger, String, Float, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base

class FuzzyResult(Base):
    __tablename__ = "fuzzy_results"

    fuzzy_result_id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True, autoincrement=True)
    zone_node_id = Column(Integer, ForeignKey("zone_nodes.zone_node_id", ondelete="CASCADE"), nullable=False)
    config_version = Column(String(50), ForeignKey("control_config.config_version"), nullable=False)
    processing_cycle_id = Column(String(100), nullable=False, index=True)
    source_record_id = Column(BigInteger, nullable=False)
    source_timestamp = Column(DateTime(timezone=True), nullable=False)
    
    dust_index = Column(Float, nullable=False)
    condition_score = Column(Float, nullable=False)      # s_i (0 - 100)
    condition_class = Column(String(50), nullable=False)  # 'Baik', 'Perlu Perhatian', 'Buruk'
    control_level = Column(Float, nullable=False)        # u_i (0 - 100)
    
    processed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Relasi
    zone_node = relationship("ZoneNode", back_populates="fuzzy_results")
    config = relationship("ControlConfig", back_populates="fuzzy_results")
    zone_controls = relationship("ZoneControl", back_populates="determining_fuzzy_result")

    def __repr__(self):
        return f"<FuzzyResult(id={self.fuzzy_result_id}, cycle='{self.processing_cycle_id}', s_i={self.condition_score}, u_i={self.control_level})>"
