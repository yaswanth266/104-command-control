from sqlalchemy import Column, String, Boolean, DateTime, text
from sqlalchemy.sql import func
from app.db.database import Base

class Category(Base):
    __tablename__ = "ccc_category"

    code = Column(String(24), primary_key=True)
    label = Column(String(191), nullable=False)
    team_code = Column(String(24), index=True, nullable=False)
    default_owner = Column(String(128))
    is_active = Column(Boolean, server_default=text("1"), nullable=False)
    created_at = Column(DateTime, default=func.now())
