from sqlalchemy import Column, String
from app.db.database import Base

class PriorityMatrix(Base):
    """The Impact x Urgency -> Priority lookup grid (see app/core/config.py's
    IMPACT_LEVELS/URGENCY_LEVELS for the fixed level set). One row per cell;
    admin-editable via /admin/priority-matrix."""
    __tablename__ = "ccc_priority_matrix"

    impact_code = Column(String(16), primary_key=True)
    urgency_code = Column(String(16), primary_key=True)
    priority_code = Column(String(4), nullable=False)
