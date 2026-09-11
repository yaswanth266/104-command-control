from sqlalchemy import Column, Integer, String, DateTime, UniqueConstraint
from app.db.database import Base

class EmpHierarchy(Base):
    """5-minute-synced shadow copy of the external per-employee organizational
    hierarchy (Phase 5 stage 2): for the employee identified by emp_code,
    who holds each role (OE/DM/RM/SPH/...) above them. One row per
    (emp_code, role_code) - e.g. (emp_code='E123', role_code='OE') names
    E123's OE. app/services/roles.py's resolve_role_holder(emp_code,
    role_code) reads this table directly; app/services/hierarchy.py's
    _resolve_level() calls it when a Routing Rule's lN_role is set. Read-only
    cache - see app/models/ext_vehicle.py's docstring."""
    __tablename__ = "ccc_emp_hierarchy"

    id = Column(Integer, primary_key=True, autoincrement=True)
    emp_code = Column(String(32), index=True, nullable=False)
    role_code = Column(String(24), nullable=False)
    holder_emp_code = Column(String(32))
    holder_name = Column(String(191))
    holder_designation = Column(String(128))
    synced_at = Column(DateTime)

    __table_args__ = (UniqueConstraint("emp_code", "role_code", name="ux_ccc_emp_hierarchy_emp_role"),)
