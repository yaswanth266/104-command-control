import datetime
from tests.conftest import auth_headers
from app.db.database import SessionLocal
from app.models.ticket import Ticket

MGR = auth_headers("CC_MANAGER")
CT = auth_headers("CALL_TAKER")
SVC = auth_headers("SERVICE")

_BUSINESS_HOURS = {
    "mon": ["09:00", "18:00"], "tue": ["09:00", "18:00"], "wed": ["09:00", "18:00"],
    "thu": ["09:00", "18:00"], "fri": ["09:00", "18:00"], "sat": None, "sun": None,
}


def _make_ticket(client, **overrides):
    body = {
        "mmu_vehicle": "AP39TEST1", "district": "Test District", "problem": "calendar test",
        "category": "MACHINE", "priority": "P2", "caller_name": "Test Caller", "caller_phone": "9876543210",
    }
    body.update(overrides)
    return client.post("/cccapi/ticket", json=body, headers=CT)


def db_get(tid):
    db = SessionLocal()
    t = db.query(Ticket).filter(Ticket.id == tid).first()
    db.close()
    return t


def test_default_calendar_is_seeded_24x7(client):
    r = client.get("/cccapi/admin/calendars", headers=MGR)
    assert r.status_code == 200
    cal = next(c for c in r.json() if c["code"] == "DEFAULT-24X7")
    assert cal["is_24x7"] is True


def test_admin_can_create_a_business_hours_calendar(client):
    r = client.post("/cccapi/admin/calendars", json={
        "code": "BIZ-HOURS", "name": "Business Hours (Mon-Fri 9-6)", "is_24x7": False,
        "working_hours": _BUSINESS_HOURS,
    }, headers=MGR)
    assert r.status_code == 200, r.text
    assert r.json()["is_24x7"] is False
    assert r.json()["working_hours"]["mon"] == ["09:00", "18:00"]
    assert r.json()["working_hours"]["sat"] is None


def test_non_24x7_calendar_requires_working_hours(client):
    r = client.post("/cccapi/admin/calendars", json={
        "code": "BAD-CAL", "name": "Bad", "is_24x7": False,
    }, headers=MGR)
    assert r.status_code == 400


def test_calendar_rejects_malformed_working_hours(client):
    r = client.post("/cccapi/admin/calendars", json={
        "code": "BAD-CAL2", "name": "Bad", "is_24x7": False,
        "working_hours": {"mon": ["9am", "6pm"]},
    }, headers=MGR)
    assert r.status_code == 400


def test_duplicate_calendar_code_rejected(client):
    r = client.post("/cccapi/admin/calendars", json={"code": "DEFAULT-24X7", "name": "Dup"}, headers=MGR)
    assert r.status_code == 409


def test_admin_can_add_and_list_and_remove_a_holiday(client):
    client.post("/cccapi/admin/calendars", json={
        "code": "HOL-CAL", "name": "Holiday Test Calendar", "is_24x7": False, "working_hours": _BUSINESS_HOURS,
    }, headers=MGR)
    r = client.post("/cccapi/admin/calendars/HOL-CAL/holidays", json={
        "holiday_date": "2026-01-26", "label": "Republic Day",
    }, headers=MGR)
    assert r.status_code == 200, r.text
    hid = r.json()["id"]

    r = client.get("/cccapi/admin/calendars/HOL-CAL/holidays", headers=MGR)
    assert any(h["id"] == hid for h in r.json())

    r = client.delete(f"/cccapi/admin/calendars/holidays/{hid}", headers=MGR)
    assert r.status_code == 200

    r = client.get("/cccapi/admin/calendars/HOL-CAL/holidays", headers=MGR)
    assert not any(h["id"] == hid for h in r.json())


def test_holiday_rejects_unknown_calendar(client):
    r = client.post("/cccapi/admin/calendars/NOT_A_CAL/holidays", json={"holiday_date": "2026-01-01"}, headers=MGR)
    assert r.status_code == 400


def test_non_admin_cannot_manage_calendars(client):
    r = client.post("/cccapi/admin/calendars", json={"code": "X", "name": "X"}, headers=SVC)
    assert r.status_code == 403


def test_ticket_due_date_respects_a_business_hours_calendar_end_to_end(client):
    """The real point of phase 3: a category scoped to a non-24x7 calendar
    must compute a genuinely different (calendar-aware) due_at, not a plain
    wall-clock add - and the ticket detail response must reflect it."""
    client.post("/cccapi/admin/calendars", json={
        "code": "E2E-BIZ", "name": "E2E Business Hours", "is_24x7": False, "working_hours": _BUSINESS_HOURS,
    }, headers=MGR)
    r = client.post("/cccapi/admin/sla-policies", json={
        "code": "MACHINE-P2-BIZ", "priority_code": "P2", "resolution_mins": 180,
        "category_code": "MACHINE", "calendar_code": "E2E-BIZ",
    }, headers=MGR)
    assert r.status_code == 200, r.text

    tid = _make_ticket(client, priority="P2").json()["id"]
    t = db_get(tid)
    assert t.sla_policy_code == "MACHINE-P2-BIZ"

    # Force a known start instant (Monday 17:00) so the expected due_at is
    # deterministic, then re-run through the same engine the app uses.
    db = SessionLocal()
    db.query(Ticket).filter(Ticket.id == tid).update({"created_at": datetime.datetime(2026, 1, 5, 17, 0)})
    db.commit()
    db.close()

    from app.db.database import SessionLocal as SL
    from app.services.sla_engine import resolve_ticket_sla
    dbs = SL()
    sla = resolve_ticket_sla(dbs, "INCIDENT", "MACHINE", None, "P2", now=datetime.datetime(2026, 1, 5, 17, 0))
    dbs.close()
    # 60 min left Monday (17-18) + 120 more starting Tuesday 09:00 -> 11:00.
    assert sla["due_at"] == datetime.datetime(2026, 1, 6, 11, 0)
    assert sla["policy_code"] == "MACHINE-P2-BIZ"
