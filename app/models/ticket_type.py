from sqlalchemy import Column, String, Boolean, DateTime, text
from sqlalchemy.sql import func
from app.db.database import Base

class TicketType(Base):
    __tablename__ = "ccc_ticket_type"

    code = Column(String(24), primary_key=True)
    label = Column(String(191), nullable=False)
    # Not read by anything yet - reserved for the workflow engine (phase 6)
    # and Change-Request approval routing.
    workflow_code = Column(String(24))
    requires_approval = Column(Boolean, server_default=text("0"), nullable=False)
    is_active = Column(Boolean, server_default=text("1"), nullable=False)
    created_at = Column(DateTime, default=func.now())
