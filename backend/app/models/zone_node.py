from sqlalchemy import Column, Integer, String, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship
from app.core.database import Base

class ZoneNode(Base):
    __tablename__ = "zone_nodes"

    zone_node_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    zone_id = Column(String(50), nullable=False)
    node_id = Column(String(50), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)

    __table_args__ = (
        UniqueConstraint("zone_id", "node_id", name="uq_zone_node"),
    )

    # Relasi
    fuzzy_results = relationship("FuzzyResult", back_populates="zone_node", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ZoneNode(id={self.zone_node_id}, zone='{self.zone_id}', node='{self.node_id}')>"
