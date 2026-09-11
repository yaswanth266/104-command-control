from sqlalchemy import Column, Integer, String, DateTime, text
from sqlalchemy.sql import func
from app.db.database import Base

class TicketAssignment(Base):
    """Both the L1-L4 hierarchy snapshot (spec S20) AND the assignment history
    (spec S28) - one row per (ticket, level) occupant over time. A level's
    CURRENT occupant is its most recent row with status='ACTIVE'; releasing
    one (a manual reassignment, or a future escalation ownership transfer)
    sets released_at and status='RELEASED' rather than deleting it, so the
    full history stays queryable - append-only in spirit, like ccc_event."""
    __tablename__ = "ccc_ticket_assignment"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id = Column(Integer, index=True, nullable=False)
    level = Column(String(8), nullable=False)  # 'L1'..'L4' - a plain string, not an enum, so L5+ needs no schema change
    user_id = Column(Integer)
    user_name_snapshot = Column(String(128))
    team_code = Column(String(24))
    team_name_snapshot = Column(String(191))
    assigned_at = Column(DateTime, default=func.now())
    released_at = Column(DateTime)
    status = Column(String(16), server_default=text("'ACTIVE'"), nullable=False)
    # 'LOCAL' (LocalMappingProvider) / 'EXTERNAL_API' (ExternalApiProvider) /
    # 'MANUAL' (the existing assign action recording who a Team Executive
    # pointed the ticket at) - see app/services/hierarchy.py.
    source = Column(String(16), server_default=text("'LOCAL'"), nullable=False)
