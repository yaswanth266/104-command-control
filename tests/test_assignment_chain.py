from tests.conftest import auth_headers
from app.db.database import SessionLocal
from app.models.user import User
from app.models.ticket import Ticket

MGR = auth_headers("CC_MANAGER")
CT = auth_headers("CALL_TAKER")
SVC = auth_headers("SERVICE")


def _make_ticket(client):
    r = client.post("/cccapi/ticket", json={
        "mmu_vehicle": "AP39TEST1", "district": "Test District", "problem": "assignment chain test",
        "category": "MACHINE", "priority": "P2", "caller_name": "Test Caller", "caller_phone": "9876543210",
    }, headers=CT)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _set_team_manager(username, is_manager=True):
    db = SessionLocal()
    db.query(User).filter(User.username == username).update({"is_team_manager": is_manager})
    db.commit()
    db.close()


def db_get_ticket(tid):
    db = SessionLocal()
    t = db.query(Ticket).filter(Ticket.id == tid).first()
    db.close()
    return t


def _chain(client, tid):
    return client.get(f"/cccapi/ticket/{tid}/assignments", headers=MGR).json()


def test_manual_assign_records_l1_occupant(client):
    tid = _make_ticket(client)
    r = client.post("/cccapi/ticket/action", json={"id": tid, "action": "assign", "assignee": "service"}, headers=MGR)
    assert r.status_code == 200, r.text

    chain = _chain(client, tid)
    active_l1 = [row for row in chain if row["level"] == "L1" and row["status"] == "ACTIVE"]
    assert len(active_l1) == 1
    assert active_l1[0]["user_name"] == "Service"
    assert active_l1[0]["source"] == "MANUAL"

    t = db_get_ticket(tid)
    assert t.current_assignee_username == "service"


def test_reassigning_releases_the_previous_occupant(client):
    tm_headers = MGR
    tid = _make_ticket(client)
    client.post("/cccapi/ticket/action", json={"id": tid, "action": "assign", "assignee": "service"}, headers=tm_headers)

    other = auth_headers("SERVICE", username="service_other_member")
    r = client.post("/cccapi/admin/users", json={
        "username": "service_other_member", "name": "Other Member", "role": "SERVICE", "password": "longenoughpw",
    }, headers=MGR)
    assert r.status_code == 200, r.text

    r = client.post("/cccapi/ticket/action", json={"id": tid, "action": "assign", "assignee": "service_other_member"}, headers=tm_headers)
    assert r.status_code == 200, r.text

    chain = _chain(client, tid)
    l1_rows = [row for row in chain if row["level"] == "L1"]
    active = [row for row in l1_rows if row["status"] == "ACTIVE"]
    released = [row for row in l1_rows if row["status"] == "RELEASED"]
    assert len(active) == 1
    assert active[0]["user_name"] == "Other Member"
    # 2 released rows: the initial LOCAL (unassigned) row from ticket
    # creation, then the first manual assignment to "service" - both
    # superseded in turn, full history preserved for each.
    assert len(released) == 2
    assert released[-1]["user_name"] == "Service"
    assert all(row["released_at"] is not None for row in released)


def test_history_accumulates_across_multiple_reassignments(client):
    tid = _make_ticket(client)
    client.post("/cccapi/admin/users", json={
        "username": "svc_a", "name": "Svc A", "role": "SERVICE", "password": "longenoughpw",
    }, headers=MGR)
    client.post("/cccapi/admin/users", json={
        "username": "svc_b", "name": "Svc B", "role": "SERVICE", "password": "longenoughpw",
    }, headers=MGR)

    client.post("/cccapi/ticket/action", json={"id": tid, "action": "assign", "assignee": "svc_a"}, headers=MGR)
    client.post("/cccapi/ticket/action", json={"id": tid, "action": "assign", "assignee": "svc_b"}, headers=MGR)
    client.post("/cccapi/ticket/action", json={"id": tid, "action": "assign", "assignee": "svc_a"}, headers=MGR)

    chain = _chain(client, tid)
    l1_rows = [row for row in chain if row["level"] == "L1"]
    # 1 initial LOCAL row (created at ticket creation) + 3 manual assigns = 4
    assert len(l1_rows) == 4
    active = [row for row in l1_rows if row["status"] == "ACTIVE"]
    assert len(active) == 1
    assert active[0]["user_name"] == "Svc A"


def test_team_manager_can_assign_and_it_is_recorded(client):
    _set_team_manager("service", True)
    try:
        from starlette.testclient import TestClient
        import main
        with TestClient(main.app) as c:
            r_login = c.post("/cccapi/auth", json={"username": "service", "password": "testpass123"})
        tm_headers = {"Authorization": "Bearer " + r_login.json()["token"]}

        tid = _make_ticket(client)
        r = client.post("/cccapi/ticket/action", json={"id": tid, "action": "assign", "assignee": "service"}, headers=tm_headers)
        assert r.status_code == 200, r.text

        chain = _chain(client, tid)
        active_l1 = [row for row in chain if row["level"] == "L1" and row["status"] == "ACTIVE"]
        assert active_l1[0]["source"] == "MANUAL"
    finally:
        _set_team_manager("service", False)
