from sqlalchemy import Column, Integer, String, Boolean, DateTime, text
from sqlalchemy.sql import func
from app.db.database import Base

class Vehicle(Base):
    __tablename__ = "ccc_vehicle"

    id = Column(Integer, primary_key=True, autoincrement=True)
    registration_no = Column(String(32), unique=True, nullable=False, index=True)
    # Prefill hint only ("last seen in this Mandal") - never authoritative.
    # Current location is captured fresh per-ticket; vehicles move.
    last_mandal_id = Column(Integer, index=True)
    is_active = Column(Boolean, server_default=text("1"), nullable=False)
    created_at = Column(DateTime, default=func.now())
