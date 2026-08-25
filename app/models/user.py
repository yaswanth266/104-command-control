from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from app.db.database import Base

class User(Base):
    __tablename__ = "ccc_user"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, index=True)
    name = Column(String(128))
    role = Column(String(32))
    phone = Column(String(20))
    pw = Column(String(255))
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
