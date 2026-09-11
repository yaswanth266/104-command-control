from sqlalchemy import Column, Integer, String, Text, DateTime, text
from sqlalchemy.sql import func
from app.db.database import Base

class AssignmentException(Base):
    """Recovery queue for a hierarchy resolution that couldn't be fully
    trusted (external API unreachable, no L1 team resolvable, etc - spec
    SS17/41). The ticket itself is never blocked on this (BR-013) - it's
    created and routed via the existing team-based mechanism regardless;
    this queue is purely so a supervisor can review/fix the L1-L4 chain
    afterward."""
    __tablename__ = "ccc_assignment_exception"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id = Column(Integer, index=True, nullable=False)
    reason = Column(String(64), nullable=False)  # e.g. API_FAILURE, NO_L1_FOUND, INACTIVE_USER
    detail = Column(Text)
    status = Column(String(16), server_default=text("'OPEN'"), nullable=False)
    created_at = Column(DateTime, default=func.now())
    resolved_at = Column(DateTime)
    resolved_by = Column(String(64))
