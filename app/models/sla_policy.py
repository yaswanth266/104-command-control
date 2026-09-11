from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, JSON, text
from sqlalchemy.sql import func
from app.db.database import Base

class SlaPolicy(Base):
    """One row per (scope, priority). Scope is whichever of subcategory_code /
    category_code / ticket_type is set - resolve_policy() in
    app/services/sla_engine.py matches subcategory first, then category, then
    ticket_type, then the "baseline" row (all three NULL) for that priority.
    The baseline rows are what app/crud/crud_ticket.py's get_tat_map() reads -
    they replace ccc_config's old 'tat' JSON key as the source of truth, and
    PUT /admin/sla's `tat` patch now writes here instead."""
    __tablename__ = "ccc_sla_policy"

    code = Column(String(48), primary_key=True)
    subcategory_code = Column(String(32), index=True)
    category_code = Column(String(24), index=True)
    ticket_type = Column(String(24), index=True)
    priority_code = Column(String(4), nullable=False, index=True)

    response_mins = Column(Integer)
    resolution_mins = Column(Integer, nullable=False)
    calendar_code = Column(String(32), nullable=False)

    # Reserved for the Escalation Engine (phase 5) - not read anywhere yet.
    warning_pct = Column(Float)
    breach_pct = Column(Float)
    # No server_default - some MySQL versions reject a default on a JSON
    # column outright. Always set explicitly in code (see crud_sla_policy.py).
    pause_statuses = Column(JSON)
    effective_from = Column(DateTime)
    effective_to = Column(DateTime)

    is_active = Column(Boolean, server_default=text("1"), nullable=False)
    created_at = Column(DateTime, default=func.now())
