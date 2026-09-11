from sqlalchemy import Column, Integer, String, DateTime, Text
from app.db.database import Base

class SyncRun(Base):
    """One row per master-data sync job attempt (Phase 5 stage 2) - see
    app/services/master_sync.py. job is one of 'vehicles'/'employees'/
    'hierarchy'. Mirrors the shape of app/models/api_assignment_log.py, but
    that table is ticket-scoped (ticket_id NOT NULL) and this sync work has
    no ticket, hence a separate table rather than reusing it."""
    __tablename__ = "ccc_sync_run"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job = Column(String(32), index=True, nullable=False)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    status = Column(String(16))  # SUCCESS / ERROR
    rows_upserted = Column(Integer)
    error_message = Column(String(500))
