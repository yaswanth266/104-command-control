from tests.conftest import auth_headers

CT = auth_headers("CALL_TAKER")
SVC = auth_headers("SERVICE")
NET = auth_headers("NETWORK")  # unrelated department for a SERVICE-routed ticket
MGR = auth_headers("CC_MANAGER")


def make_service_ticket(client):
    r = client.post("/cccapi/ticket", json={
        "mmu_vehicle": "AP39TEST1", "district": "Test District", "problem": "access test",
        "category": "MACHINE", "priority": "P3",
    }, headers=CT)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_other_department_cannot_view_ticket(client):
    tid = make_service_ticket(client)
    r = client.get(f"/cccapi/ticket/{tid}", headers=NET)
    assert r.status_code == 403


def test_owning_department_can_view_ticket(client):
    tid = make_service_ticket(client)
    r = client.get(f"/cccapi/ticket/{tid}", headers=SVC)
    assert r.status_code == 200


def test_manager_and_call_taker_can_view_any_ticket(client):
    tid = make_service_ticket(client)
    assert client.get(f"/cccapi/ticket/{tid}", headers=MGR).status_code == 200
    assert client.get(f"/cccapi/ticket/{tid}", headers=CT).status_code == 200


def test_other_department_cannot_act_on_ticket(client):
    tid = make_service_ticket(client)
    r = client.post("/cccapi/ticket/action", json={"id": tid, "action": "acknowledge"}, headers=NET)
    assert r.status_code == 403
    r = client.post("/cccapi/ticket/action", json={"id": tid, "action": "escalate"}, headers=NET)
    assert r.status_code == 403


def test_dashboard_is_manager_only(client):
    assert client.get("/cccapi/dashboard", headers=SVC).status_code == 403
    assert client.get("/cccapi/dashboard", headers=MGR).status_code == 200


def test_users_list_is_manager_only(client):
    assert client.get("/cccapi/users", headers=SVC).status_code == 403
    assert client.get("/cccapi/users", headers=MGR).status_code == 200


def test_detailed_health_is_manager_only(client):
    assert client.get("/cccapi/health/detailed", headers=SVC).status_code == 403
    assert client.get("/cccapi/health/detailed", headers=MGR).status_code == 200


def test_login_lockout_after_repeated_failures(client):
    for _ in range(5):
        r = client.post("/cccapi/auth", json={"username": "service", "password": "wrong"})
        assert r.status_code == 401
    r = client.post("/cccapi/auth", json={"username": "service", "password": "wrong"})
    assert r.status_code == 429


def test_valid_login_returns_token(client):
    r = client.post("/cccapi/auth", json={"username": "call_taker", "password": "testpass123"})
    assert r.status_code == 200
    body = r.json()
    assert body["token"]
    assert body["user"]["role"] == "CALL_TAKER"
