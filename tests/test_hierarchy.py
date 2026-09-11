from tests.conftest import auth_headers
from app.db.database import SessionLocal
from app.models.user import User

MGR = auth_headers("CC_MANAGER")
CT = auth_headers("CALL_TAKER")
SVC = auth_headers("SERVICE")


def _make_ticket(client, **overrides):
    body = {
        "mmu_vehicle": "AP39TEST1", "district": "Test District", "problem": "hierarchy test",
        "category": "MACHINE", "priority": "P2", "caller_name": "Test Caller", "caller_phone": "9876543210",
    }
    body.update(overrides)
    r = client.post("/cccapi/ticket", json=body, headers=CT)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _chain(client, tid, headers=MGR):
    r = client.get(f"/cccapi/ticket/{tid}/assignments", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


_UNSET = object()


def _set_team_manager(username, is_manager=True, reporting_manager_id=_UNSET):
    db = SessionLocal()
    patch = {"is_team_manager": is_manager}
    if reporting_manager_id is not _UNSET:
        patch["reporting_manager_id"] = reporting_manager_id
    db.query(User).filter(User.username == username).update(patch)
    db.commit()
    db.close()


def test_default_local_chain_has_all_four_levels(client):
    tid = _make_ticket(client)
    chain = _chain(client, tid)
    levels = [row["level"] for row in chain if row["status"] == "ACTIVE"]
    assert levels == ["L1", "L2", "L3", "L4"]


def test_l1_is_the_tickets_routed_team_with_no_named_user(client):
    tid = _make_ticket(client)
    chain = _chain(client, tid)
    l1 = next(r for r in chain if r["level"] == "L1")
    assert l1["team_code"] == "SERVICE"
    assert l1["user_id"] is None
    assert l1["source"] == "LOCAL"


def test_l4_is_always_cc_manager(client):
    tid = _make_ticket(client)
    chain = _chain(client, tid)
    l4 = next(r for r in chain if r["level"] == "L4")
    assert l4["team_code"] == "CC_MANAGER"


def test_l2_is_the_teams_manager_when_one_exists(client):
    _set_team_manager("service", True)
    try:
        tid = _make_ticket(client)
        chain = _chain(client, tid)
        l2 = next(r for r in chain if r["level"] == "L2")
        assert l2["user_name"] == "Service"
    finally:
        _set_team_manager("service", False)


def test_l3_is_l2s_reporting_manager(client):
    db = SessionLocal()
    mgr_id = db.query(User).filter(User.username == "cc_manager").first().id
    db.close()
    _set_team_manager("service", True, reporting_manager_id=mgr_id)
    try:
        tid = _make_ticket(client)
        chain = _chain(client, tid)
        l3 = next(r for r in chain if r["level"] == "L3")
        assert l3["user_id"] == mgr_id
    finally:
        _set_team_manager("service", False, reporting_manager_id=None)


def test_no_team_manager_means_l2_and_l3_have_no_user(client):
    tid = _make_ticket(client)
    chain = _chain(client, tid)
    l2 = next(r for r in chain if r["level"] == "L2")
    l3 = next(r for r in chain if r["level"] == "L3")
    assert l2["user_id"] is None
    assert l3["user_id"] is None


def test_admin_can_crud_routing_rules(client):
    r = client.post("/cccapi/admin/routing-rules", json={
        "code": "MACHINE-RULE-1", "category_code": "MACHINE", "l1_username": "service",
    }, headers=MGR)
    assert r.status_code == 200, r.text

    r = client.get("/cccapi/admin/routing-rules", headers=MGR)
    codes = [x["code"] for x in r.json()]
    assert "MACHINE-RULE-1" in codes

    r = client.put("/cccapi/admin/routing-rules/MACHINE-RULE-1", json={"is_active": False}, headers=MGR)
    assert r.status_code == 200
    assert r.json()["is_active"] is False


def test_routing_rule_rejects_unknown_category(client):
    r = client.post("/cccapi/admin/routing-rules", json={"code": "BADRULE", "category_code": "NOT_A_CATEGORY"}, headers=MGR)
    assert r.status_code == 400


def test_duplicate_routing_rule_for_same_scope_rejected(client):
    client.post("/cccapi/admin/routing-rules", json={"code": "DUP1", "category_code": "QC"}, headers=MGR)
    r = client.post("/cccapi/admin/routing-rules", json={"code": "DUP2", "category_code": "QC"}, headers=MGR)
    assert r.status_code == 409


def test_non_admin_cannot_manage_routing_rules(client):
    r = client.post("/cccapi/admin/routing-rules", json={"code": "X", "category_code": "MACHINE"}, headers=SVC)
    assert r.status_code == 403


def test_routing_rule_overrides_l1_l4_named_users(client):
    client.post("/cccapi/admin/routing-rules", json={
        "code": "MACHINE-NAMED", "category_code": "MACHINE",
        "l1_username": "service", "l4_username": "cc_manager",
    }, headers=MGR)
    tid = _make_ticket(client)
    chain = _chain(client, tid)
    l1 = next(r for r in chain if r["level"] == "L1")
    l4 = next(r for r in chain if r["level"] == "L4")
    assert l1["user_name"] == "Service"
    assert l4["user_name"] == "Cc Manager"


def test_ticket_view_permission_applies_to_assignments_endpoint(client):
    tid = _make_ticket(client)
    other_team = auth_headers("APPLICATION")
    r = client.get(f"/cccapi/ticket/{tid}/assignments", headers=other_team)
    assert r.status_code == 403
