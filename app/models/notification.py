from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from app.db.database import Base

class Notification(Base):
    __tablename__ = "ccc_notification"

    id = Column(Integer, primary_key=True, autoincrement=True)
    audience_role = Column(String(32), index=True)
    ticket_id = Column(Integer, index=True)
    type = Column(String(32), index=True)
    message = Column(Text)
    created_at = Column(DateTime, default=func.now(), index=True)
    read_at = Column(DateTime)
