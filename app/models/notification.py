from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from app.db.database import Base

class Notification(Base):
    __tablename__ = "ccc_notification"

    id = Column(Integer, primary_key=True, autoincrement=True)
    audience_role = Column(String(32), index=True)
    # When set, this notification is for one specific person (e.g. "you were
    # assigned this ticket", an 80%-TAT warning to a Team Manager by name) -
    # not a role-wide broadcast. audience_role may still be set alongside it
    # for context/filtering; matching logic is in crud_notification.py.
    audience_username = Column(String(64), index=True)
    ticket_id = Column(Integer, index=True)
    type = Column(String(32), index=True)
    message = Column(Text)
    created_at = Column(DateTime, default=func.now(), index=True)
    read_at = Column(DateTime)
