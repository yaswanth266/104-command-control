import datetime
from app.services.calendar import add_working_minutes, working_minutes_between

TWENTYFOURSEVEN = {"is_24x7": True, "working_hours": None, "holidays": []}

BUSINESS_HOURS = {
    "is_24x7": False,
    "working_hours": {
        "mon": ["09:00", "18:00"], "tue": ["09:00", "18:00"], "wed": ["09:00", "18:00"],
        "thu": ["09:00", "18:00"], "fri": ["09:00", "18:00"], "sat": None, "sun": None,
    },
    "holidays": [],
}


def test_24x7_is_a_plain_wall_clock_add():
    start = datetime.datetime(2026, 1, 1, 10, 0)  # a Thursday
    result = add_working_minutes(start, 500, TWENTYFOURSEVEN)
    assert result == start + datetime.timedelta(minutes=500)


def test_none_minutes_returns_none():
    start = datetime.datetime(2026, 1, 1, 10, 0)
    assert add_working_minutes(start, None, TWENTYFOURSEVEN) is None
    assert add_working_minutes(start, None, BUSINESS_HOURS) is None


def test_business_hours_within_same_day_window():
    start = datetime.datetime(2026, 1, 5, 10, 0)  # Monday 10:00
    result = add_working_minutes(start, 120, BUSINESS_HOURS)
    assert result == datetime.datetime(2026, 1, 5, 12, 0)


def test_business_hours_spills_into_next_working_day():
    # Monday 17:00 + 180 working minutes: 60 left today (to 18:00), then
    # 120 more starting Tuesday 09:00 -> Tuesday 11:00.
    start = datetime.datetime(2026, 1, 5, 17, 0)
    result = add_working_minutes(start, 180, BUSINESS_HOURS)
    assert result == datetime.datetime(2026, 1, 6, 11, 0)


def test_business_hours_skips_weekend():
    # Friday 17:00 + 120 working minutes: 60 left today, then 60 more
    # starting Monday 09:00 (Sat/Sun are non-working) -> Monday 10:00.
    start = datetime.datetime(2026, 1, 9, 17, 0)  # a Friday
    result = add_working_minutes(start, 120, BUSINESS_HOURS)
    assert result == datetime.datetime(2026, 1, 12, 10, 0)


def test_business_hours_starting_outside_the_window_clamps_forward():
    # Started at 20:00 (after hours) - should be treated as starting at the
    # next working-day open.
    start = datetime.datetime(2026, 1, 5, 20, 0)  # Monday night
    result = add_working_minutes(start, 30, BUSINESS_HOURS)
    assert result == datetime.datetime(2026, 1, 6, 9, 30)


def test_business_hours_respects_a_holiday():
    cal = dict(BUSINESS_HOURS, holidays=["2026-01-06"])  # Tuesday off
    start = datetime.datetime(2026, 1, 5, 17, 0)  # Monday 17:00
    result = add_working_minutes(start, 120, cal)
    # 60 min left Monday, Tuesday is a holiday, so the remaining 60 land
    # Wednesday 09:00 -> 10:00.
    assert result == datetime.datetime(2026, 1, 7, 10, 0)


def test_working_minutes_between_24x7_is_plain_delta():
    a = datetime.datetime(2026, 1, 1, 10, 0)
    b = datetime.datetime(2026, 1, 1, 12, 30)
    assert working_minutes_between(a, b, TWENTYFOURSEVEN) == 150.0


def test_working_minutes_between_returns_zero_for_non_positive_span():
    a = datetime.datetime(2026, 1, 1, 12, 0)
    b = datetime.datetime(2026, 1, 1, 10, 0)
    assert working_minutes_between(a, b, TWENTYFOURSEVEN) == 0.0


def test_working_minutes_between_business_hours_excludes_off_hours():
    # Monday 17:00 to Tuesday 10:00: 60 min Monday (17-18) + 60 min Tuesday
    # (09-10) = 120 working minutes, even though 17 wall-clock hours passed.
    a = datetime.datetime(2026, 1, 5, 17, 0)
    b = datetime.datetime(2026, 1, 6, 10, 0)
    assert working_minutes_between(a, b, BUSINESS_HOURS) == 120.0


def test_working_minutes_between_business_hours_skips_weekend():
    # Friday 17:00 to Monday 10:00: 60 min Friday + 60 min Monday = 120,
    # the whole weekend contributes zero.
    a = datetime.datetime(2026, 1, 9, 17, 0)
    b = datetime.datetime(2026, 1, 12, 10, 0)
    assert working_minutes_between(a, b, BUSINESS_HOURS) == 120.0
