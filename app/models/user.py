from sqlalchemy import Column, Integer, String, Boolean, DateTime, text
from sqlalchemy.sql import func
from app.db.database import Base

class User(Base):
    __tablename__ = "ccc_user"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, index=True)
    name = Column(String(128))
    role = Column(String(32))
    phone = Column(String(20))
    pw = Column(String(255))
    active = Column(Boolean, default=True)
    hr_emp_code = Column(String(32))
    reporting_manager_id = Column(Integer, index=True)
    # Team-scoped dispatch permission, not a separate access tier - a Team
    # Manager is a member of `role`'s team with the extra ability to assign
    # tickets to named teammates. See app/services/ticket_service.py's
    # "assign" action.
    is_team_manager = Column(Boolean, server_default=text("0"), nullable=False)
    created_at = Column(DateTime, default=func.now())
