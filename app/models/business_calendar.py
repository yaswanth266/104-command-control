from sqlalchemy import Column, String, Boolean, DateTime, JSON, text
from sqlalchemy.sql import func
from app.db.database import Base

class BusinessCalendar(Base):
    """Working days/hours an SLA policy's minutes are measured against. A
    24x7 calendar (is_24x7=True) makes add_working_minutes() a plain wall-
    clock add - see app/services/calendar.py - which is what every ticket
    used before this master existed, and what the seeded DEFAULT-24X7
    calendar continues to do."""
    __tablename__ = "ccc_business_calendar"

    code = Column(String(32), primary_key=True)
    name = Column(String(191), nullable=False)
    is_24x7 = Column(Boolean, server_default=text("1"), nullable=False)
    # Informational only for now - all datetimes in this codebase are naive
    # local wall-clock; no timezone conversion is performed.
    timezone = Column(String(64), server_default=text("'Asia/Kolkata'"), nullable=False)
    # {"mon": ["09:00","18:00"], "tue": [...], ..., "sun": null} - only read
    # when is_24x7 is False.
    working_hours = Column(JSON)
    is_active = Column(Boolean, server_default=text("1"), nullable=False)
    created_at = Column(DateTime, default=func.now())
