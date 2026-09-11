from sqlalchemy import Column, String, Boolean, DateTime, text
from sqlalchemy.sql import func
from app.db.database import Base

class Reason(Base):
    """The Sub-Category master (enterprise framework alignment) - historically
    LT-only, now selectable from any intake path. Table/model name kept as
    Reason/ccc_reason to avoid churning crud_reason.py, lt.py and the LT test
    suite; "Sub-Category" is the label used in the UI and API responses."""
    __tablename__ = "ccc_reason"

    code = Column(String(32), primary_key=True)
    category_code = Column(String(24), index=True, nullable=False)
    label = Column(String(191), nullable=False)
    ticket_type = Column(String(24), server_default=text("'INCIDENT'"), nullable=False)
    # Not read by anything yet - reserved for the Priority (phase 2), SLA
    # (phase 3) and Workflow (phase 6) engines.
    default_priority = Column(String(4))
    sla_policy_code = Column(String(32))
    workflow_code = Column(String(24))
    effective_from = Column(DateTime)
    effective_to = Column(DateTime)
    is_active = Column(Boolean, server_default=text("1"), nullable=False)
    created_at = Column(DateTime, default=func.now())
