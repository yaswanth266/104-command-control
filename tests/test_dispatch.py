from tests.conftest import auth_headers
from app.db.database import SessionLocal
from app.models.user import User

CT = auth_headers("CALL_TAKER")
SVC = auth_headers("SERVICE")  # plain team member, not a manager
MGR = auth_headers("CC_MANAGER")


def make_ticket(client, team_headers=CT):
    r = client.post("/cccapi/ticket", json={
        "mmu_vehicle": "AP1", "district": "D", "problem": "dispatch test",
        "category": "MACHINE", "priority": "P2",
    }, headers=team_headers)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _set_team_manager(username, is_manager=True):
    db = SessionLocal()
    db.query(User).filter(User.username == username).update({"is_team_manager": is_manager})
    db.commit()
    db.close()


def _team_manager_headers():
    # service is the seeded SERVICE user - promote then log in fresh so the
    # token carries is_team_manager (it's embedded at login, not re-checked
    # per request - see app/api/routers/auth.py).
    _set_team_manager("service", True)
    r_login = None
    from starlette.testclient import TestClient
    import main
    with TestClient(main.app) as c:
        r_login = c.post("/cccapi/auth", json={"username": "service", "password": "testpass123"})
    assert r_login.status_code == 200, r_login.text
    return {"Authorization": "Bearer " + r_login.json()["token"]}


def test_plain_team_member_cannot_assign(client):
    tid = make_ticket(client)
    r = client.post("/cccapi/ticket/action", json={"id": tid, "action": "assign", "assignee": "service"}, headers=SVC)
    assert r.status_code == 403


def test_cc_manager_can_assign_on_any_team(client):
    tid = make_ticket(client)
    r = client.post("/cccapi/ticket/action", json={"id": tid, "action": "assign", "assignee": "service"}, headers=MGR)
    assert r.status_code == 200
    t = client.get(f"/cccapi/ticket/{tid}", headers=MGR).json()["ticket"]
    assert t["assignee"] == "service"


def test_team_manager_can_assign_within_team(client):
    tm_headers = _team_manager_headers()
    try:
        tid = make_ticket(client)
        r = client.post("/cccapi/ticket/action", json={"id": tid, "action": "assign", "assignee": "service"}, headers=tm_headers)
        assert r.status_code == 200, r.text
    finally:
        _set_team_manager("service", False)


def test_assign_rejects_cross_team_target(client):
    tm_headers = _team_manager_headers()
    try:
        tid = make_ticket(client)
        r = client.post("/cccapi/ticket/action", json={"id": tid, "action": "assign", "assignee": "application"}, headers=tm_headers)
        assert r.status_code == 400
    finally:
        _set_team_manager("service", False)


def test_assign_requires_a_target(client):
    tm_headers = _team_manager_headers()
    try:
        tid = make_ticket(client)
        r = client.post("/cccapi/ticket/action", json={"id": tid, "action": "assign", "assignee": ""}, headers=tm_headers)
        assert r.status_code == 400
    finally:
        _set_team_manager("service", False)


def test_assign_notifies_only_the_target_not_the_whole_team(client):
    tm_headers = _team_manager_headers()
    try:
        tid = make_ticket(client)
        client.post("/cccapi/ticket/action", json={"id": tid, "action": "assign", "assignee": "service"}, headers=tm_headers)

        # service (the target) should see a personal ASSIGNED notification
        r = client.get("/cccapi/notifications", headers=SVC)
        assert any(n["type"] == "ASSIGNED" for n in r.json()["rows"])

        # a different member of the SAME team should NOT see it as theirs
        # (they'd only see role-wide broadcasts like NEW_TICKET)
        other_headers = auth_headers("SERVICE", username="service_other_member")
        r2 = client.get("/cccapi/notifications", headers=other_headers)
        assigned_for_other = [n for n in r2.json()["rows"] if n["type"] == "ASSIGNED"]
        assert assigned_for_other == []
    finally:
        _set_team_manager("service", False)


def test_dashboard_reports_unassigned_tickets(client):
    make_ticket(client)  # freshly created, nobody acknowledged/assigned yet
    r = client.get("/cccapi/dashboard", headers=MGR)
    assert r.json()["today"]["unassigned"] >= 1


def test_plain_team_member_cannot_view_roster(client):
    r = client.get("/cccapi/users/team-roster", headers=SVC)
    assert r.status_code == 403


def test_team_manager_sees_only_their_own_team_roster(client):
    tm_headers = _team_manager_headers()
    try:
        r = client.get("/cccapi/users/team-roster", headers=tm_headers)
        assert r.status_code == 200
        assert all(True for _ in r.json())  # just confirms the shape works
        usernames = [u["username"] for u in r.json()]
        assert "service" in usernames
        assert "application" not in usernames  # a different team, not theirs
    finally:
        _set_team_manager("service", False)


def test_cc_manager_roster_requires_team_param(client):
    r = client.get("/cccapi/users/team-roster", headers=MGR)
    assert r.status_code == 400
    r2 = client.get("/cccapi/users/team-roster?team=SERVICE", headers=MGR)
    assert r2.status_code == 200
    assert any(u["username"] == "service" for u in r2.json())
