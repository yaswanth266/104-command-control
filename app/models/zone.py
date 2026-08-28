from sqlalchemy import Column, Integer, String, Boolean, DateTime, text
from sqlalchemy.sql import func
from app.db.database import Base

class Zone(Base):
    __tablename__ = "ccc_zone"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(96), unique=True, nullable=False)
    team_code = Column(String(24), index=True, nullable=False)
    is_active = Column(Boolean, server_default=text("1"), nullable=False)
    created_at = Column(DateTime, default=func.now())
