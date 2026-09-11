from sqlalchemy import Column, String, Integer, Boolean, DateTime, text
from sqlalchemy.sql import func
from app.db.database import Base

class Priority(Base):
    """Replaces the old hardcoded PRIORITY dict in app/core/config.py. The
    four seeded codes (P1-P4) are still assumed elsewhere (TAT map keys,
    ccc_ticket queue sort SQL, the .p-P1..p-P4 CSS pills) - this master makes
    their label/description/severity editable, it does not yet make the set
    of codes itself freely extensible."""
    __tablename__ = "ccc_priority"

    code = Column(String(4), primary_key=True)
    label = Column(String(64), nullable=False)
    description = Column(String(255))
    # Lower is more severe (1 = highest). Informational only for now.
    severity = Column(Integer)
    display_order = Column(Integer, server_default=text("0"), nullable=False)
    is_active = Column(Boolean, server_default=text("1"), nullable=False)
    created_at = Column(DateTime, default=func.now())
