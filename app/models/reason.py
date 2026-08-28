from sqlalchemy import Column, String, Boolean, DateTime, text
from sqlalchemy.sql import func
from app.db.database import Base

class Reason(Base):
    __tablename__ = "ccc_reason"

    code = Column(String(32), primary_key=True)
    category_code = Column(String(24), index=True, nullable=False)
    label = Column(String(191), nullable=False)
    is_active = Column(Boolean, server_default=text("1"), nullable=False)
    created_at = Column(DateTime, default=func.now())
