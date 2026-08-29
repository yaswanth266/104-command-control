from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from app.db.database import Base

class Attachment(Base):
    __tablename__ = "ccc_attachment"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id = Column(Integer, index=True, nullable=False)
    filename = Column(String(255), nullable=False)
    original_name = Column(String(255))
    content_type = Column(String(100))
    size_bytes = Column(Integer)
    uploaded_by = Column(String(64))
    uploaded_by_role = Column(String(32))
    uploaded_at = Column(DateTime, default=func.now())
    note = Column(String(255))
