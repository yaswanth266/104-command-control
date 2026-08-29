import datetime
from tests.conftest import auth_headers, lt_ids
from app.db.database import SessionLocal
from app.models.ticket import Ticket
from app.models.user import User
from app.core.security import hash_pw
from app.services.sla_sweep import run_sla_sweep_once

CT = auth_headers("CALL_TAKER")
MGR = auth_headers("CC_MANAGER")
SVC = auth_headers("SERVICE")


def _make_district_ticket(client, district_id, priority="P1"):
    r = client.post("/cccapi/ticket", json={
        "mmu_vehicle": "AP2", "district": "D", "district_id": district_id,
        "problem": "local lead routing test", "category": "MACHINE", "priority": priority,
        "caller_name": "Test Caller", "caller_phone": "9876543210",
    }, headers=CT)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def age_ticket(tid, pct_used, tat_mins=240):
    db = SessionLocal()
    t = db.query(Ticket).filter(Ticket.id == tid).first()
    now = datetime.datetime.now()
    elapsed = tat_mins * pct_used
    t.created_at = now - datetime.timedelta(minutes=elapsed)
    t.due_at = now + datetime.timedelta(minutes=tat_mins - elapsed)
    t.tat_mins = tat_mins
    db.commit()
    db.close()


def _upsert_local_lead(username, district_id):
    db = SessionLocal()
    u = db.query(User).filter(User.username == username).first()
    if not u:
        u = User(username=username, name="Local Lead", role="SERVICE", pw=hash_pw("testpass123"), active=True)
        db.add(u)
    u.is_team_manager = True
    u.district_id = district_id
    db.commit()
    db.close()


def _delete_user(username):
    db = SessionLocal()
    db.query(User).filter(User.username == username).delete()
    db.commit()
    db.close()


def _set_team_manager(username, is_manager):
    db = SessionLocal()
    db.query(User).filter(User.username == username).update({"is_team_manager": is_manager})
    db.commit()
    db.close()


def _set_dispatch(client, enabled):
    r = client.put("/cccapi/admin/dispatch", json={"local_team_lead_enabled": enabled}, headers=MGR)
    assert r.status_code == 200, r.text


def notif_types_for(client, headers, ticket_id):
    r = client.get("/cccapi/notifications", headers=headers)
    return [n["type"] for n in r.json()["rows"] if n["ticket_id"] == ticket_id]


def _login_headers(client, username, password="testpass123"):
    # is_team_manager is embedded into the token at login (app/api/routers/auth.py),
    # not re-checked per request - a crafted auth_headers() token never carries it,
    # so assign-permission tests need a real login instead.
    r = client.post("/cccapi/auth", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


def test_dispatch_toggle_defaults_off(client):
    r = client.get("/cccapi/admin/dispatch", headers=MGR)
    assert r.status_code == 200
    assert r.json()["local_team_lead_enabled"] is False


def test_toggle_off_new_ticket_does_not_personally_notify_district_lead(client):
    _upsert_local_lead("svc_lead_a", lt_ids["district_id"])
    try:
        tid = _make_district_ticket(client, lt_ids["district_id"])
        types = notif_types_for(client, auth_headers("SERVICE", username="svc_lead_a"), tid)
        assert "NEW_TICKET_LOCAL_LEAD" not in types
    finally:
        _delete_user("svc_lead_a")


def test_toggle_on_new_ticket_personally_notifies_district_lead(client):
    _set_dispatch(client, True)
    _upsert_local_lead("svc_lead_b", lt_ids["district_id"])
    try:
        tid = _make_district_ticket(client, lt_ids["district_id"])
        types = notif_types_for(client, auth_headers("SERVICE", username="svc_lead_b"), tid)
        assert "NEW_TICKET_LOCAL_LEAD" in types
    finally:
        _delete_user("svc_lead_b")
        _set_dispatch(client, False)


def test_toggle_on_50pct_warns_local_lead_instead_of_statewide_exec(client):
    _set_dispatch(client, True)
    _upsert_local_lead("svc_lead_c", lt_ids["district_id"])
    _set_team_manager("service", True)  # statewide Team Executive, no district set
    try:
        tid = _make_district_ticket(client, lt_ids["district_id"])
        age_ticket(tid, 0.85)
        run_sla_sweep_once()
        lead_types = notif_types_for(client, auth_headers("SERVICE", username="svc_lead_c"), tid)
        exec_types = notif_types_for(client, SVC, tid)
        assert "TAT_TEAM_MANAGER_WARN" in lead_types
        assert "TAT_TEAM_MANAGER_WARN" not in exec_types
    finally:
        _delete_user("svc_lead_c")
        _set_team_manager("service", False)
        _set_dispatch(client, False)


def test_toggle_on_50pct_falls_back_to_statewide_exec_when_no_local_lead(client):
    _set_dispatch(client, True)
    _set_team_manager("service", True)
    try:
        tid = _make_district_ticket(client, lt_ids["district_id"])
        age_ticket(tid, 0.85)
        run_sla_sweep_once()
        assert "TAT_TEAM_MANAGER_WARN" in notif_types_for(client, SVC, tid)
    finally:
        _set_team_manager("service", False)
        _set_dispatch(client, False)


def test_local_lead_cannot_assign_ticket_outside_their_district(client):
    _set_dispatch(client, True)
    _upsert_local_lead("svc_lead_d", lt_ids["district_id"])
    try:
        lead_headers = _login_headers(client, "svc_lead_d")
        tid = _make_district_ticket(client, lt_ids["district_id"] + 99999)  # a different district
        r = client.post("/cccapi/ticket/action", json={"id": tid, "action": "assign", "assignee": "service"},
                         headers=lead_headers)
        assert r.status_code == 403
    finally:
        _delete_user("svc_lead_d")
        _set_dispatch(client, False)


def test_local_lead_can_assign_within_their_district(client):
    _set_dispatch(client, True)
    _upsert_local_lead("svc_lead_e", lt_ids["district_id"])
    try:
        lead_headers = _login_headers(client, "svc_lead_e")
        tid = _make_district_ticket(client, lt_ids["district_id"])
        r = client.post("/cccapi/ticket/action", json={"id": tid, "action": "assign", "assignee": "service"},
                         headers=lead_headers)
        assert r.status_code == 200, r.text
    finally:
        _delete_user("svc_lead_e")
        _set_dispatch(client, False)


def test_statewide_exec_keeps_assign_rights_regardless_of_district_when_toggle_on(client):
    _set_dispatch(client, True)
    _set_team_manager("service", True)  # no district_id -> statewide
    try:
        exec_headers = _login_headers(client, "service")
        tid = _make_district_ticket(client, lt_ids["district_id"])
        r = client.post("/cccapi/ticket/action", json={"id": tid, "action": "assign", "assignee": "service"}, headers=exec_headers)
        assert r.status_code == 200, r.text
    finally:
        _set_team_manager("service", False)
        _set_dispatch(client, False)
