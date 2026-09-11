from sqlalchemy import Column, Integer, String, Text, JSON, DateTime
from sqlalchemy.sql import func
from app.db.database import Base

class ApiAssignmentLog(Base):
    """Every hierarchy-resolution attempt, local or external (spec S39) -
    troubleshooting trail for "why did this ticket end up with this L1-L4
    chain". ticket_id is set even on failure (the ticket is always persisted
    before hierarchy resolution is attempted - BR-013)."""
    __tablename__ = "ccc_api_assignment_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id = Column(Integer, index=True, nullable=False)
    mode = Column(String(16), nullable=False)  # 'LOCAL' / 'EXTERNAL_API'
    request_payload = Column(JSON)
    response_payload = Column(JSON)
    status = Column(String(16), nullable=False)  # 'SUCCESS' / 'ERROR'
    error_message = Column(Text)
    created_at = Column(DateTime, default=func.now())
