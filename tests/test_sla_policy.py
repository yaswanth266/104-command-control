import datetime
from tests.conftest import auth_headers
from app.db.database import SessionLocal
from app.models.ticket import Ticket

MGR = auth_headers("CC_MANAGER")
CT = auth_headers("CALL_TAKER")
SVC = auth_headers("SERVICE")


def _make_ticket(client, **overrides):
    body = {
        "mmu_vehicle": "AP39TEST1", "district": "Test District", "problem": "sla policy test",
        "category": "MACHINE", "priority": "P2", "caller_name": "Test Caller", "caller_phone": "9876543210",
    }
    body.update(overrides)
    return client.post("/cccapi/ticket", json=body, headers=CT)


def db_get(tid):
    db = SessionLocal()
    t = db.query(Ticket).filter(Ticket.id == tid).first()
    db.close()
    return t


def test_baseline_policies_seeded_and_match_tat_default(client):
    r = client.get("/cccapi/admin/sla-policies", headers=MGR)
    assert r.status_code == 200
    baseline = {p["code"]: p for p in r.json() if p["code"].startswith("BASELINE-")}
    assert baseline["BASELINE-P1"]["resolution_mins"] == 240
    assert baseline["BASELINE-P2"]["resolution_mins"] == 480
    assert baseline["BASELINE-P3"]["resolution_mins"] == 1440
    assert baseline["BASELINE-P4"]["resolution_mins"] == 4320
    assert baseline["BASELINE-P1"]["calendar_code"] == "DEFAULT-24X7"


def test_ticket_created_with_baseline_policy_has_no_category_specific_override(client):
    r = _make_ticket(client, priority="P1")
    tid = r.json()["id"]
    t = db_get(tid)
    assert t.sla_policy_code == "BASELINE-P1"
    assert t.tat_mins == 240
    expected_due = t.created_at + datetime.timedelta(minutes=240)
    assert abs((t.due_at - expected_due).total_seconds()) < 5


def test_admin_can_create_category_scoped_policy_and_it_wins_over_baseline(client):
    r = client.post("/cccapi/admin/sla-policies", json={
        "code": "MACHINE-P2", "priority_code": "P2", "resolution_mins": 60,
        "category_code": "MACHINE", "calendar_code": "DEFAULT-24X7",
    }, headers=MGR)
    assert r.status_code == 200, r.text

    r = _make_ticket(client, priority="P2")
    tid = r.json()["id"]
    t = db_get(tid)
    assert t.sla_policy_code == "MACHINE-P2"
    assert t.tat_mins == 60
    expected_due = t.created_at + datetime.timedelta(minutes=60)
    assert abs((t.due_at - expected_due).total_seconds()) < 5


def test_subcategory_scoped_policy_wins_over_category_scoped(client):
    client.post("/cccapi/admin/sla-policies", json={
        "code": "MACHINE-P2-B", "priority_code": "P2", "resolution_mins": 60,
        "category_code": "MACHINE", "calendar_code": "DEFAULT-24X7",
    }, headers=MGR)
    client.post("/cccapi/admin/reasons", json={
        "code": "SLA_SUBCAT", "category_code": "MACHINE", "label": "SLA test subcat",
    }, headers=MGR)
    r = client.post("/cccapi/admin/sla-policies", json={
        "code": "SLA_SUBCAT-P2", "priority_code": "P2", "resolution_mins": 15,
        "subcategory_code": "SLA_SUBCAT", "calendar_code": "DEFAULT-24X7",
    }, headers=MGR)
    assert r.status_code == 200, r.text

    r = _make_ticket(client, priority="P2", subcategory_code="SLA_SUBCAT")
    tid = r.json()["id"]
    t = db_get(tid)
    assert t.sla_policy_code == "SLA_SUBCAT-P2"
    assert t.tat_mins == 15


def test_response_sla_is_measured_on_first_acknowledge(client):
    r = client.post("/cccapi/admin/sla-policies", json={
        "code": "MACHINE-P3-RESP", "priority_code": "P3", "resolution_mins": 1440,
        "response_mins": 30, "category_code": "MACHINE", "calendar_code": "DEFAULT-24X7",
    }, headers=MGR)
    assert r.status_code == 200, r.text

    r = _make_ticket(client, priority="P3")
    tid = r.json()["id"]
    t = db_get(tid)
    assert t.response_due_at is not None
    assert abs((t.response_due_at - (t.created_at + datetime.timedelta(minutes=30))).total_seconds()) < 5

    # Simulate the response arriving after the response SLA window.
    db = SessionLocal()
    db.query(Ticket).filter(Ticket.id == tid).update({
        "response_due_at": datetime.datetime.now() - datetime.timedelta(minutes=5)
    })
    db.commit()
    db.close()

    r = client.post("/cccapi/ticket/action", json={"id": tid, "action": "acknowledge"}, headers=SVC)
    assert r.status_code == 200
    t = db_get(tid)
    assert t.response_breached is True

    # A later action must not re-evaluate/overwrite the response verdict.
    client.post("/cccapi/ticket/action", json={"id": tid, "action": "start"}, headers=SVC)
    t2 = db_get(tid)
    assert t2.response_breached is True
    assert t2.first_response_at == t.first_response_at


def test_ticket_type_scoped_policy_used_when_no_category_or_subcategory_match(client):
    r = client.post("/cccapi/admin/sla-policies", json={
        "code": "INCIDENT-P4", "priority_code": "P4", "resolution_mins": 999,
        "ticket_type": "INCIDENT", "calendar_code": "DEFAULT-24X7",
    }, headers=MGR)
    assert r.status_code == 200, r.text

    r = _make_ticket(client, category="QC", priority="P4")
    tid = r.json()["id"]
    t = db_get(tid)
    assert t.sla_policy_code == "INCIDENT-P4"
    assert t.tat_mins == 999


def test_admin_sla_policy_crud_validation(client):
    r = client.post("/cccapi/admin/sla-policies", json={
        "code": "BADPOLICY", "priority_code": "P1", "resolution_mins": 0,
    }, headers=MGR)
    assert r.status_code == 400

    r = client.post("/cccapi/admin/sla-policies", json={
        "code": "OKPOLICY", "priority_code": "P1", "resolution_mins": 100,
    }, headers=MGR)
    assert r.status_code == 200, r.text

    r = client.post("/cccapi/admin/sla-policies", json={
        "code": "OKPOLICY", "priority_code": "P1", "resolution_mins": 100,
    }, headers=MGR)
    assert r.status_code == 409

    r = client.put("/cccapi/admin/sla-policies/OKPOLICY", json={"resolution_mins": 200}, headers=MGR)
    assert r.status_code == 200
    assert r.json()["resolution_mins"] == 200

    r = client.put("/cccapi/admin/sla-policies/OKPOLICY", json={"is_active": False}, headers=MGR)
    assert r.status_code == 200
    assert r.json()["is_active"] is False


def test_non_admin_cannot_manage_sla_policies(client):
    r = client.post("/cccapi/admin/sla-policies", json={"code": "X", "priority_code": "P1", "resolution_mins": 10}, headers=SVC)
    assert r.status_code == 403


def test_repriority_uses_ticket_own_category_scoped_policy(client):
    client.post("/cccapi/admin/sla-policies", json={
        "code": "MACHINE-P1-REPRI", "priority_code": "P1", "resolution_mins": 30,
        "category_code": "MACHINE", "calendar_code": "DEFAULT-24X7",
    }, headers=MGR)

    tid = _make_ticket(client, priority="P3").json()["id"]
    r = client.post("/cccapi/ticket/action", json={"id": tid, "action": "repriority", "priority": "P1"}, headers=MGR)
    assert r.status_code == 200, r.text

    t = db_get(tid)
    assert t.sla_policy_code == "MACHINE-P1-REPRI"
    assert t.tat_mins == 30
    expected_due = t.created_at + datetime.timedelta(minutes=30)
    assert abs((t.due_at - expected_due).total_seconds()) < 5
