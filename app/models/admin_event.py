from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from app.db.database import Base

class AdminEvent(Base):
    __tablename__ = "ccc_admin_event"

    id = Column(Integer, primary_key=True, autoincrement=True)
    at = Column(DateTime, default=func.now(), index=True)
    actor = Column(String(64))
    actor_role = Column(String(32))
    action = Column(String(48))
    entity_type = Column(String(32), index=True)
    entity_id = Column(String(64))
    detail = Column(Text)
