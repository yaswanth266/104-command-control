from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON, text
from sqlalchemy.sql import func
from app.db.database import Base

class Ticket(Base):
    __tablename__ = "ccc_ticket"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_no = Column(String(32), unique=True)
    source = Column(String(24), server_default='CALL')
    mmu_vehicle = Column(String(64), index=True)
    vehicle_id = Column(Integer, index=True)
    district = Column(String(96))
    # Geo snapshot at creation time - resolved team may depend on these, and
    # they must NOT silently change if the District/Mandal hierarchy is later
    # reorganized (historical reporting stays accurate).
    district_id = Column(Integer, index=True)
    mandal_id = Column(Integer, index=True)
    zone_id = Column(Integer, index=True)
    location = Column(String(191))
    caller_name = Column(String(128))
    caller_phone = Column(String(20))
    called_at = Column(DateTime)
    equipment = Column(String(128))
    machine_id = Column(Integer, index=True)
    reason_codes = Column(JSON)
    photo_path = Column(String(255))
    problem = Column(Text)
    error_code = Column(String(96))
    impact = Column(String(191))
    category = Column(String(24), index=True)
    # Taxonomy (enterprise framework alignment): ticket_type mirrors
    # ccc_ticket_type.code, subcategory_code mirrors ccc_reason.code. Label
    # snapshots follow the same rule as the geo snapshot above - they must
    # NOT change if the master row is later relabeled/deactivated.
    ticket_type = Column(String(24), server_default=text("'INCIDENT'"), index=True)
    subcategory_code = Column(String(32), index=True)
    category_label_snapshot = Column(String(191))
    subcategory_label_snapshot = Column(String(191))
    priority = Column(String(4), index=True)
    team = Column(String(24), index=True)
    owner = Column(String(128))
    assignee = Column(String(64))
    status = Column(String(32), server_default='NEW', index=True)
    tat_mins = Column(Integer)
    due_at = Column(DateTime, index=True)
    created_at = Column(DateTime, default=func.now(), index=True)
    created_by = Column(String(64))
    assigned_at = Column(DateTime)
    acknowledged_at = Column(DateTime)
    first_response_at = Column(DateTime)
    resolved_at = Column(DateTime)
    closed_at = Column(DateTime, index=True)
    diagnosis = Column(Text)
    action_taken = Column(Text)
    root_cause = Column(Text)
    parts = Column(Text)
    resolution = Column(Text)
    pending_reason = Column(String(255))
    pending_since = Column(DateTime)
    paused_minutes = Column(Integer, server_default=text("0"))
    vip = Column(Boolean, server_default=text("0"))
    confirmed_by = Column(String(128))
    confirmed_at = Column(DateTime)
    escalated = Column(Boolean, server_default=text("0"))
    escalated_at = Column(DateTime)
    escalated_to = Column(String(64))
    escalation_note = Column(String(255))
    # How many times this ticket has been escalated (not just whether it
    # currently is - `escalated`/`escalation_note` only reflect the latest
    # one). Each escalation's own reason still lives forever in ccc_event
    # (append-only), this is just a quick running count for the UI/reports.
    escalation_count = Column(Integer, server_default=text("0"))
    breached = Column(Boolean, server_default=text("0"))
    reopened = Column(Integer, server_default=text("0"))
