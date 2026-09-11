import datetime

_DAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
_MAX_DAYS = 3650  # ~10 years - a misconfigured calendar with zero working
                  # days must raise, not hang the request forever.


def _parse_time(s: str) -> datetime.time:
    h, m = s.split(":")
    return datetime.time(int(h), int(m))


def _is_24x7(calendar_cfg: dict) -> bool:
    return not calendar_cfg or calendar_cfg.get("is_24x7", True) or not calendar_cfg.get("working_hours")


def add_working_minutes(start: datetime.datetime, minutes, calendar_cfg: dict):
    """start + `minutes` of WORKING time under `calendar_cfg` (the shape
    returned by app/crud/crud_calendar.py's get_calendar_config: {is_24x7,
    working_hours, holidays}). A 24x7 calendar (or `minutes` being None) is a
    plain wall-clock add - this is what every ticket's TAT computation did
    before business calendars existed, and what the seeded DEFAULT-24X7
    calendar still does, so existing behavior is unchanged unless a non-24x7
    calendar is deliberately configured."""
    if minutes is None:
        return None
    if _is_24x7(calendar_cfg):
        return start + datetime.timedelta(minutes=minutes)

    working_hours = calendar_cfg["working_hours"]
    holidays = set(calendar_cfg.get("holidays") or [])
    remaining = float(minutes)
    cur = start

    for _ in range(_MAX_DAYS):
        if remaining <= 0:
            return cur
        day_key = _DAY_KEYS[cur.weekday()]
        date_str = cur.strftime("%Y-%m-%d")
        window = working_hours.get(day_key)
        if not window or date_str in holidays:
            cur = datetime.datetime.combine(cur.date() + datetime.timedelta(days=1), datetime.time.min)
            continue
        day_start = datetime.datetime.combine(cur.date(), _parse_time(window[0]))
        day_end = datetime.datetime.combine(cur.date(), _parse_time(window[1]))
        if cur < day_start:
            cur = day_start
        if cur >= day_end:
            cur = datetime.datetime.combine(cur.date() + datetime.timedelta(days=1), datetime.time.min)
            continue
        available = (day_end - cur).total_seconds() / 60.0
        if remaining <= available:
            return cur + datetime.timedelta(minutes=remaining)
        remaining -= available
        cur = datetime.datetime.combine(cur.date() + datetime.timedelta(days=1), datetime.time.min)

    raise ValueError(f"Calendar has no working time in the next {_MAX_DAYS} days - check its working_hours")


def working_minutes_between(a: datetime.datetime, b: datetime.datetime, calendar_cfg: dict) -> float:
    """Working minutes that fall within [a, b). 0 if b <= a."""
    if b <= a:
        return 0.0
    if _is_24x7(calendar_cfg):
        return (b - a).total_seconds() / 60.0

    working_hours = calendar_cfg["working_hours"]
    holidays = set(calendar_cfg.get("holidays") or [])
    total = 0.0
    cur = datetime.datetime.combine(a.date(), datetime.time.min)

    for _ in range(_MAX_DAYS):
        if cur >= b:
            break
        day_key = _DAY_KEYS[cur.weekday()]
        date_str = cur.strftime("%Y-%m-%d")
        window = working_hours.get(day_key)
        if window and date_str not in holidays:
            day_start = max(a, datetime.datetime.combine(cur.date(), _parse_time(window[0])))
            day_end = min(b, datetime.datetime.combine(cur.date(), _parse_time(window[1])))
            if day_end > day_start:
                total += (day_end - day_start).total_seconds() / 60.0
        cur = datetime.datetime.combine(cur.date() + datetime.timedelta(days=1), datetime.time.min)

    return total
