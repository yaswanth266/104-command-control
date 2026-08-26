from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from app.db.database import Base

class Event(Base):
    __tablename__ = "ccc_event"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id = Column(Integer, index=True)
    at = Column(DateTime, default=func.now())
    actor = Column(String(64))
    actor_role = Column(String(32))
    action = Column(String(48))
    detail = Column(Text)
    old_status = Column(String(32))
    new_status = Column(String(32))
