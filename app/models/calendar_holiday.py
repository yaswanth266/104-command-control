from sqlalchemy import Column, Integer, String, Date
from app.db.database import Base

class CalendarHoliday(Base):
    __tablename__ = "ccc_calendar_holiday"

    id = Column(Integer, primary_key=True, autoincrement=True)
    calendar_code = Column(String(32), index=True, nullable=False)
    holiday_date = Column(Date, nullable=False)
    label = Column(String(191))
