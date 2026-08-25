from sqlalchemy import Column, String, Text
from app.db.database import Base

class Config(Base):
    __tablename__ = "ccc_config"

    k = Column(String(64), primary_key=True)
    v = Column(Text)
