from sqlalchemy import Column, Integer, String, Boolean, DateTime, text
from app.db.database import Base

class ExtEmployee(Base):
    """5-minute-synced shadow copy of the external employee roster (Phase 5
    stage 2). Read-only cache, no foreign keys point at it - see
    app/models/ext_vehicle.py's docstring for why. role_code is the external
    system's organizational role for this person (OE/DM/RM/SPH/...), used by
    app/services/roles.py to resolve a Routing Rule's lN_role. Backs
    app/services/hierarchy.py's search_employees() as a cache-first layer."""
    __tablename__ = "ccc_ext_employee"

    id = Column(Integer, primary_key=True, autoincrement=True)
    emp_code = Column(String(32), unique=True, nullable=False, index=True)
    name = Column(String(191))
    designation = Column(String(128))
    role_code = Column(String(24), index=True)
    phone = Column(String(20))
    is_active = Column(Boolean, server_default=text("1"), nullable=False)
    synced_at = Column(DateTime)
