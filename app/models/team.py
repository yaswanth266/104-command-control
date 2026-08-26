from sqlalchemy import Column, String, Boolean, DateTime, text
from sqlalchemy.sql import func
from app.db.database import Base

class Team(Base):
    __tablename__ = "ccc_team"

    code = Column(String(24), primary_key=True)
    name = Column(String(64), nullable=False)
    is_active = Column(Boolean, server_default=text("1"), nullable=False)
    created_at = Column(DateTime, default=func.now())
