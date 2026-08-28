from sqlalchemy import Column, Integer, String, Boolean, DateTime, UniqueConstraint, text
from sqlalchemy.sql import func
from app.db.database import Base

class Mandal(Base):
    __tablename__ = "ccc_mandal"
    __table_args__ = (UniqueConstraint("district_id", "name", name="uq_mandal_district_name"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(96), nullable=False)
    district_id = Column(Integer, index=True, nullable=False)
    zone_id = Column(Integer, index=True)
    is_active = Column(Boolean, server_default=text("1"), nullable=False)
    created_at = Column(DateTime, default=func.now())
