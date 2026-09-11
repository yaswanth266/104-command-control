from tests.conftest import auth_headers

MGR = auth_headers("CC_MANAGER")
CT = auth_headers("CALL_TAKER")
SVC = auth_headers("SERVICE")


def _make_ticket(client, **overrides):
    body = {
        "mmu_vehicle": "AP39TEST1", "district": "Test District", "problem": "priority test",
        "category": "MACHINE", "priority": "P2", "caller_name": "Test Caller", "caller_phone": "9876543210",
    }
    body.update(overrides)
    return client.post("/cccapi/ticket", json=body, headers=CT)


def test_meta_includes_priority_masters_and_matrix(client):
    r = client.get("/cccapi/meta", headers=SVC)
    meta = r.json()
    assert set(meta["priority"].keys()) == {"P1", "P2", "P3", "P4"}
    assert meta["priorities"]["P1"]["label"] == "Critical"
    assert meta["impact_levels"] == ["HIGH", "MEDIUM", "LOW"]
    assert meta["urgency_levels"] == ["HIGH", "MEDIUM", "LOW"]
    assert meta["priority_matrix"]["HIGH"]["HIGH"] == "P1"
    assert meta["priority_matrix"]["LOW"]["LOW"] == "P4"


def test_admin_can_crud_priorities(client):
    r = client.post("/cccapi/admin/priorities", json={"code": "P5", "label": "Planned", "display_order": 5}, headers=MGR)
    assert r.status_code == 200, r.text
    assert r.json()["code"] == "P5"

    r = client.put("/cccapi/admin/priorities/P5", json={"label": "Scheduled"}, headers=MGR)
    assert r.status_code == 200
    assert r.json()["label"] == "Scheduled"

    r = client.get("/cccapi/admin/priorities", headers=MGR)
    codes = [p["code"] for p in r.json()]
    assert "P5" in codes


def test_duplicate_priority_code_rejected(client):
    r = client.post("/cccapi/admin/priorities", json={"code": "P1", "label": "Dup"}, headers=MGR)
    assert r.status_code == 409


def test_non_admin_cannot_manage_priorities(client):
    r = client.post("/cccapi/admin/priorities", json={"code": "P5", "label": "X"}, headers=SVC)
    assert r.status_code == 403


def test_admin_can_update_priority_matrix_cell(client):
    r = client.put("/cccapi/admin/priority-matrix", json={
        "impact_code": "MEDIUM", "urgency_code": "HIGH", "priority_code": "P1",
    }, headers=MGR)
    assert r.status_code == 200, r.text
    assert r.json()["priority_code"] == "P1"

    r = client.get("/cccapi/meta", headers=MGR)
    assert r.json()["priority_matrix"]["MEDIUM"]["HIGH"] == "P1"


def test_matrix_cell_rejects_unknown_impact_or_priority(client):
    r = client.put("/cccapi/admin/priority-matrix", json={
        "impact_code": "NOT_A_LEVEL", "urgency_code": "HIGH", "priority_code": "P1",
    }, headers=MGR)
    assert r.status_code == 400

    r = client.put("/cccapi/admin/priority-matrix", json={
        "impact_code": "HIGH", "urgency_code": "HIGH", "priority_code": "NOT_A_PRIORITY",
    }, headers=MGR)
    assert r.status_code == 400


def test_ticket_created_with_explicit_priority_still_works(client):
    r = _make_ticket(client, priority="P3")
    assert r.status_code == 200, r.text
    tid = r.json()["id"]
    r = client.get(f"/cccapi/ticket/{tid}", headers=SVC)
    t = r.json()["ticket"]
    assert t["priority"] == "P3"
    assert t["original_priority"] == "P3"
    assert t["impact_code"] is None and t["urgency_code"] is None


def test_ticket_priority_derived_from_impact_and_urgency(client):
    r = _make_ticket(client, priority=None, impact_code="HIGH", urgency_code="HIGH")
    assert r.status_code == 200, r.text
    tid = r.json()["id"]
    r = client.get(f"/cccapi/ticket/{tid}", headers=SVC)
    t = r.json()["ticket"]
    assert t["priority"] == "P1"
    assert t["original_priority"] == "P1"
    assert t["impact_code"] == "HIGH" and t["urgency_code"] == "HIGH"


def test_ticket_explicit_priority_overrides_matrix_suggestion(client):
    r = _make_ticket(client, priority="P4", impact_code="HIGH", urgency_code="HIGH")
    assert r.status_code == 200, r.text
    tid = r.json()["id"]
    r = client.get(f"/cccapi/ticket/{tid}", headers=SVC)
    t = r.json()["ticket"]
    assert t["priority"] == "P4"

    r = client.get(f"/cccapi/ticket/{tid}", headers=SVC)
    events = [e["detail"] for e in r.json()["events"]]
    assert any("overridden from matrix-suggested P1" in d for d in events)


def test_ticket_requires_priority_or_impact_and_urgency(client):
    r = _make_ticket(client, priority=None)
    assert r.status_code == 400


def test_ticket_requires_both_impact_and_urgency_together(client):
    r = _make_ticket(client, priority=None, impact_code="HIGH")
    assert r.status_code == 400


def test_vip_forces_p1_even_with_a_low_urgency_matrix_suggestion(client):
    r = _make_ticket(client, priority=None, impact_code="LOW", urgency_code="LOW", vip=True)
    assert r.status_code == 200, r.text
    tid = r.json()["id"]
    t = client.get(f"/cccapi/ticket/{tid}", headers=SVC).json()["ticket"]
    assert t["priority"] == "P1"           # VIP forces P1
    assert t["original_priority"] == "P1"  # snapshot reflects the VIP-forced value


def test_repriority_action_validates_against_priority_master(client):
    tid = _make_ticket(client).json()["id"]
    r = client.post("/cccapi/ticket/action", json={"id": tid, "action": "repriority", "priority": "NOT_A_PRIORITY"}, headers=MGR)
    assert r.status_code == 400

    r = client.post("/cccapi/ticket/action", json={"id": tid, "action": "repriority", "priority": "P1"}, headers=MGR)
    assert r.status_code == 200

    r = client.get(f"/cccapi/ticket/{tid}", headers=SVC)
    t = r.json()["ticket"]
    assert t["priority"] == "P1"
    assert t["original_priority"] == "P2"  # repriority never touches the creation-time snapshot


def test_repriority_rejects_inactive_priority(client):
    client.post("/cccapi/admin/priorities", json={"code": "PZ", "label": "Zeta"}, headers=MGR)
    client.put("/cccapi/admin/priorities/PZ", json={"is_active": False}, headers=MGR)
    tid = _make_ticket(client).json()["id"]
    r = client.post("/cccapi/ticket/action", json={"id": tid, "action": "repriority", "priority": "PZ"}, headers=MGR)
    assert r.status_code == 400


def test_admin_tat_update_validates_against_priority_master(client):
    r = client.put("/cccapi/admin/sla", json={"tat": {"NOT_A_PRIORITY": 100}}, headers=MGR)
    assert r.status_code == 400

    r = client.put("/cccapi/admin/sla", json={"tat": {"P1": 200}}, headers=MGR)
    assert r.status_code == 200
    assert r.json()["tat"]["P1"] == 200

    # restore default so other tests can rely on TAT_DEFAULT (same convention
    # as test_admin.py::test_sla_and_tat_update_validation)
    client.put("/cccapi/admin/sla", json={"tat": {"P1": 240}}, headers=MGR)
