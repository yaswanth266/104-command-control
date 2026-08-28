from sqlalchemy import Column, Integer, String, Boolean, DateTime, text
from sqlalchemy.sql import func
from app.db.database import Base

class Machine(Base):
    __tablename__ = "ccc_machine"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(96), unique=True, nullable=False)
    is_active = Column(Boolean, server_default=text("1"), nullable=False)
    created_at = Column(DateTime, default=func.now())
