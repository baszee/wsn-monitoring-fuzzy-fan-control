from sqlalchemy import Column, BigInteger, Integer, String, Float, Boolean, DateTime
from sqlalchemy.sql import func
from app.core.database import Base

class MockReceiverValidData(Base):
    """
    Model tiruan tabel penerima dari Subsistem 2 (Gateway / LoRa Receiver).
    Hanya menampung rekaman data yang telah tervalidasi oleh M2.
    """
    __tablename__ = "mock_receiver_valid_data"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True, autoincrement=True)
    node_id = Column(String(50), nullable=False, index=True)
    temperature = Column(Float, nullable=False)
    humidity = Column(Float, nullable=False)
    dust_raw_voltage = Column(Float, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    status_valid = Column(Boolean, nullable=False, default=True)

    def __repr__(self):
        return f"<MockReceiverData(id={self.id}, node='{self.node_id}', T={self.temperature}C, RH={self.humidity}%, V_dust={self.dust_raw_voltage}V)>"
