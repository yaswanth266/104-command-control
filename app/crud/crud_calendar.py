import datetime
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.business_calendar import BusinessCalendar
from app.models.calendar_holiday import CalendarHoliday

_DAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

def get_calendars(db: Session, include_inactive: bool = False):
    q = db.query(BusinessCalendar)
    if not include_inactive:
        q = q.filter(BusinessCalendar.is_active == True)
    return q.order_by(BusinessCalendar.code).all()

def get_calendar(db: Session, code: str):
    return db.query(BusinessCalendar).filter(BusinessCalendar.code == code).first()

def _validate_working_hours(working_hours):
    if working_hours is None:
        return None
    if not isinstance(working_hours, dict):
        raise HTTPException(400, "working_hours must be an object keyed by mon..sun")
    out = {}
    for day in _DAY_KEYS:
        window = working_hours.get(day)
        if window is None:
            out[day] = None
            continue
        if not (isinstance(window, list) and len(window) == 2):
            raise HTTPException(400, f"working_hours.{day} must be [\"HH:MM\", \"HH:MM\"] or null")
        try:
            h1, m1 = [int(x) for x in window[0].split(":")]
            h2, m2 = [int(x) for x in window[1].split(":")]
        except Exception:
            raise HTTPException(400, f"working_hours.{day} times must be HH:MM")
        if not (0 <= h1 < 24 and 0 <= m1 < 60 and 0 <= h2 < 24 and 0 <= m2 < 60):
            raise HTTPException(400, f"working_hours.{day} has an invalid time")
        if (h1, m1) >= (h2, m2):
            raise HTTPException(400, f"working_hours.{day} start must be before end")
        out[day] = [f"{h1:02d}:{m1:02d}", f"{h2:02d}:{m2:02d}"]
    return out

def create_calendar(db: Session, code: str, name: str, is_24x7: bool = True,
                     timezone: str = "Asia/Kolkata", working_hours: dict = None) -> BusinessCalendar:
    code = (code or "").strip().upper()
    if not code or not (name or "").strip():
        raise HTTPException(400, "Calendar code and name are required")
    if db.query(BusinessCalendar).filter(BusinessCalendar.code == code).first():
        raise HTTPException(409, f"Calendar code '{code}' already exists")
    if not is_24x7 and not working_hours:
        raise HTTPException(400, "A non-24x7 calendar needs working_hours")
    c = BusinessCalendar(code=code, name=name.strip(), is_24x7=bool(is_24x7),
                          timezone=(timezone or "Asia/Kolkata").strip(),
                          working_hours=_validate_working_hours(working_hours) if not is_24x7 else None,
                          is_active=True)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c

def update_calendar(db: Session, code: str, name: str = None, is_24x7: bool = None,
                     timezone: str = None, working_hours: dict = None, is_active: bool = None) -> BusinessCalendar:
    c = get_calendar(db, code)
    if not c:
        raise HTTPException(404, "Calendar not found")
    if name is not None:
        if not name.strip():
            raise HTTPException(400, "Calendar name cannot be blank")
        c.name = name.strip()
    if timezone is not None:
        c.timezone = timezone.strip() or "Asia/Kolkata"
    if is_24x7 is not None:
        c.is_24x7 = is_24x7
    if working_hours is not None:
        c.working_hours = _validate_working_hours(working_hours)
    if not c.is_24x7 and not c.working_hours:
        raise HTTPException(400, "A non-24x7 calendar needs working_hours")
    if is_active is not None:
        c.is_active = is_active
    db.commit()
    db.refresh(c)
    return c

def get_calendar_config(db: Session, code: str) -> dict:
    """{is_24x7, working_hours, holidays} - the shape app/services/calendar.py
    consumes. An unknown/missing calendar code falls back to 24x7 rather than
    raising, so a dangling calendar_code on a policy row never breaks ticket
    creation."""
    cal = get_calendar(db, code) if code else None
    if not cal:
        return {"is_24x7": True, "working_hours": None, "holidays": []}
    holidays = [h.holiday_date.strftime("%Y-%m-%d") for h in get_holidays(db, code)]
    return {"is_24x7": cal.is_24x7, "working_hours": cal.working_hours, "holidays": holidays}

def get_holidays(db: Session, calendar_code: str):
    return (db.query(CalendarHoliday)
              .filter(CalendarHoliday.calendar_code == calendar_code.upper())
              .order_by(CalendarHoliday.holiday_date)
              .all())

def add_holiday(db: Session, calendar_code: str, holiday_date, label: str = None) -> CalendarHoliday:
    calendar_code = (calendar_code or "").strip().upper()
    if not get_calendar(db, calendar_code):
        raise HTTPException(400, f"'{calendar_code}' is not a known calendar")
    if isinstance(holiday_date, str):
        try:
            holiday_date = datetime.datetime.strptime(holiday_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(400, "holiday_date must be YYYY-MM-DD")
    h = CalendarHoliday(calendar_code=calendar_code, holiday_date=holiday_date, label=(label or "").strip() or None)
    db.add(h)
    db.commit()
    db.refresh(h)
    return h

def delete_holiday(db: Session, holiday_id: int):
    h = db.query(CalendarHoliday).filter(CalendarHoliday.id == holiday_id).first()
    if not h:
        raise HTTPException(404, "Holiday not found")
    db.delete(h)
    db.commit()
