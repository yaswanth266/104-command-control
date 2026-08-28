from tests.conftest import auth_headers

MGR = auth_headers("CC_MANAGER")
SVC = auth_headers("SERVICE")


def test_non_admin_cannot_reach_admin_endpoints(client):
    assert client.get("/cccapi/admin/teams", headers=SVC).status_code == 403
    assert client.post("/cccapi/admin/teams", json={"code": "X", "name": "X"}, headers=SVC).status_code == 403


def test_create_team_and_it_shows_up_in_meta_and_roles(client):
    r = client.post("/cccapi/admin/teams", json={"code": "pharmacy", "name": "Pharmacy Team"}, headers=MGR)
    assert r.status_code == 200, r.text
    assert r.json()["code"] == "PHARMACY"

    r = client.get("/cccapi/meta", headers=MGR)
    meta = r.json()
    assert "PHARMACY" in meta["teams"]
    assert "PHARMACY" in meta["roles"]

    r = client.get("/cccapi/admin/roles", headers=MGR)
    assert "PHARMACY" in r.json()


def test_duplicate_team_code_rejected(client):
    r = client.post("/cccapi/admin/teams", json={"code": "SERVICE", "name": "Dup"}, headers=MGR)
    assert r.status_code == 409


def test_category_must_target_an_active_team(client):
    r = client.post("/cccapi/admin/categories", json={
        "code": "GHOST", "label": "Ghost issue", "team_code": "NOT_A_REAL_TEAM",
    }, headers=MGR)
    assert r.status_code == 400


def test_deactivating_team_blocked_while_active_category_points_at_it(client):
    client.post("/cccapi/admin/teams", json={"code": "SUPPLY", "name": "Supply Team"}, headers=MGR)
    client.post("/cccapi/admin/categories", json={
        "code": "RESTOCK", "label": "Restock request", "team_code": "SUPPLY",
    }, headers=MGR)
    r = client.put("/cccapi/admin/teams/SUPPLY", json={"is_active": False}, headers=MGR)
    assert r.status_code == 409
    # deactivate the category first, then the team should be deactivatable
    client.put("/cccapi/admin/categories/RESTOCK", json={"is_active": False}, headers=MGR)
    r = client.put("/cccapi/admin/teams/SUPPLY", json={"is_active": False}, headers=MGR)
    assert r.status_code == 200


def test_cc_manager_team_cannot_be_deactivated(client):
    r = client.put("/cccapi/admin/teams/CC_MANAGER", json={"is_active": False}, headers=MGR)
    assert r.status_code == 409


def test_new_category_routes_a_real_ticket(client):
    client.post("/cccapi/admin/teams", json={"code": "XRAY", "name": "X-Ray Team"}, headers=MGR)
    client.post("/cccapi/admin/categories", json={
        "code": "IMAGING", "label": "Imaging issue", "team_code": "XRAY", "default_owner": "X-Ray Tech",
    }, headers=MGR)
    r = client.post("/cccapi/ticket", json={
        "mmu_vehicle": "AP1", "district": "D1", "problem": "scanner down",
        "category": "IMAGING", "priority": "P2",
    }, headers=MGR)
    assert r.status_code == 200, r.text
    assert r.json()["team"] == "XRAY"


def test_sla_and_tat_update_validation(client):
    r = client.put("/cccapi/admin/sla", json={"sla": {"at_risk_minutes": -5}}, headers=MGR)
    assert r.status_code == 400
    r = client.put("/cccapi/admin/sla", json={"tat": {"P1": 0}}, headers=MGR)
    assert r.status_code == 400
    r = client.put("/cccapi/admin/sla", json={"tat": {"P1": 180}}, headers=MGR)
    assert r.status_code == 200
    assert r.json()["tat"]["P1"] == 180
    r = client.get("/cccapi/admin/sla", headers=MGR)
    assert r.json()["tat"]["P1"] == 180

    # restore default so other tests can rely on TAT_DEFAULT
    client.put("/cccapi/admin/sla", json={"tat": {"P1": 240}}, headers=MGR)


def test_create_user_and_login(client):
    r = client.post("/cccapi/admin/users", json={
        "username": "newsvc", "name": "New Service Person", "role": "SERVICE", "password": "longenoughpw",
    }, headers=MGR)
    assert r.status_code == 200, r.text

    r = client.post("/cccapi/auth", json={"username": "newsvc", "password": "longenoughpw"})
    assert r.status_code == 200
    assert r.json()["user"]["role"] == "SERVICE"


def test_create_user_rejects_invalid_role(client):
    r = client.post("/cccapi/admin/users", json={
        "username": "bogus", "name": "Bogus", "role": "NOT_A_ROLE", "password": "longenoughpw",
    }, headers=MGR)
    assert r.status_code == 400


def test_cannot_deactivate_last_cc_manager(client):
    r = client.get("/cccapi/users", headers=MGR)
    managers = [u for u in r.json() if u["role"] == "CC_MANAGER" and u["active"]]
    assert len(managers) == 1
    mgr_id = managers[0]["id"]
    r = client.put(f"/cccapi/admin/users/{mgr_id}", json={"active": False}, headers=MGR)
    assert r.status_code == 409


def test_admin_mutations_are_logged(client):
    client.post("/cccapi/admin/teams", json={"code": "AUDITME", "name": "Audit Test Team"}, headers=MGR)
    r = client.get("/cccapi/admin/audit", headers=MGR)
    actions = [e["action"] for e in r.json()]
    assert "TEAM_CREATED" in actions
    entry = next(e for e in r.json() if e["action"] == "TEAM_CREATED" and e["entity_id"] == "AUDITME")
    assert entry["actor_role"] == "CC_MANAGER"
