from tests.conftest import auth_headers

MGR = auth_headers("CC_MANAGER")
CT = auth_headers("CALL_TAKER")
SVC = auth_headers("SERVICE")


def _make_ticket(client, **overrides):
    body = {
        "mmu_vehicle": "AP39TEST1", "district": "Test District", "problem": "taxonomy test",
        "category": "MACHINE", "priority": "P2", "caller_name": "Test Caller", "caller_phone": "9876543210",
    }
    body.update(overrides)
    return client.post("/cccapi/ticket", json=body, headers=CT)


def test_meta_includes_ticket_types_and_subcategories(client):
    r = client.get("/cccapi/meta", headers=SVC)
    meta = r.json()
    assert "INCIDENT" in meta["ticket_types"]
    assert "SERVICE_REQUEST" in meta["ticket_types"]
    assert "CHANGE_REQUEST" in meta["ticket_types"]
    assert isinstance(meta["subcategories"], dict)


def test_admin_can_crud_ticket_types(client):
    r = client.post("/cccapi/admin/ticket-types", json={"code": "problem_task", "label": "Problem Task"}, headers=MGR)
    assert r.status_code == 200, r.text
    assert r.json()["code"] == "PROBLEM_TASK"

    r = client.get("/cccapi/admin/ticket-types", headers=MGR)
    codes = [t["code"] for t in r.json()]
    assert "PROBLEM_TASK" in codes

    r = client.put("/cccapi/admin/ticket-types/PROBLEM_TASK", json={"is_active": False}, headers=MGR)
    assert r.status_code == 200
    assert r.json()["is_active"] is False


def test_duplicate_ticket_type_code_rejected(client):
    r = client.post("/cccapi/admin/ticket-types", json={"code": "INCIDENT", "label": "Dup"}, headers=MGR)
    assert r.status_code == 409


def test_non_admin_cannot_manage_ticket_types(client):
    r = client.post("/cccapi/admin/ticket-types", json={"code": "X", "label": "X"}, headers=SVC)
    assert r.status_code == 403


def test_category_defaults_to_incident_ticket_type(client):
    r = client.post("/cccapi/admin/categories", json={
        "code": "TAXTEST1", "label": "Taxonomy Test Category", "team_code": "SERVICE",
    }, headers=MGR)
    assert r.status_code == 200, r.text
    assert r.json()["ticket_type"] == "INCIDENT"


def test_category_can_target_a_specific_ticket_type(client):
    r = client.post("/cccapi/admin/categories", json={
        "code": "TAXTEST2", "label": "Service Request Category", "team_code": "SERVICE",
        "ticket_type": "SERVICE_REQUEST",
    }, headers=MGR)
    assert r.status_code == 200, r.text
    assert r.json()["ticket_type"] == "SERVICE_REQUEST"


def test_category_rejects_unknown_ticket_type(client):
    r = client.post("/cccapi/admin/categories", json={
        "code": "TAXTEST3", "label": "Bad Type Category", "team_code": "SERVICE", "ticket_type": "NOT_A_TYPE",
    }, headers=MGR)
    assert r.status_code == 400


def test_admin_can_create_subcategory_for_any_active_category(client):
    # MACHINE is not visible_to_lt - a Sub-Category should still be creatable
    # against it now that Sub-Category is a general-purpose master, not an
    # LT-only one.
    r = client.post("/cccapi/admin/reasons", json={
        "code": "MOTOR_FAULT", "category_code": "MACHINE", "label": "Motor fault",
    }, headers=MGR)
    assert r.status_code == 200, r.text
    assert r.json()["ticket_type"] == "INCIDENT"
    assert r.json()["category_code"] == "MACHINE"

    r = client.get("/cccapi/meta", headers=MGR)
    assert "MOTOR_FAULT" in r.json()["subcategories"]
    assert r.json()["subcategories"]["MOTOR_FAULT"]["category_code"] == "MACHINE"


def test_subcategory_rejects_unknown_ticket_type(client):
    r = client.post("/cccapi/admin/reasons", json={
        "code": "BAD_SUBCAT", "category_code": "MACHINE", "label": "Bad", "ticket_type": "NOT_A_TYPE",
    }, headers=MGR)
    assert r.status_code == 400


def test_ticket_created_with_default_taxonomy_when_omitted(client):
    r = _make_ticket(client)
    assert r.status_code == 200, r.text
    tid = r.json()["id"]

    r = client.get(f"/cccapi/ticket/{tid}", headers=SVC)
    t = r.json()["ticket"]
    assert t["ticket_type"] == "INCIDENT"
    assert t["subcategory_code"] is None
    assert t["category_label_snapshot"] == "Machine / Instrument Breakdown"


def test_ticket_created_with_explicit_subcategory_and_ticket_type(client):
    client.post("/cccapi/admin/reasons", json={
        "code": "SENSOR_FAULT", "category_code": "MACHINE", "label": "Sensor fault",
    }, headers=MGR)

    r = _make_ticket(client, ticket_type="SERVICE_REQUEST", subcategory_code="SENSOR_FAULT")
    assert r.status_code == 200, r.text
    tid = r.json()["id"]

    r = client.get(f"/cccapi/ticket/{tid}", headers=SVC)
    t = r.json()["ticket"]
    assert t["ticket_type"] == "SERVICE_REQUEST"
    assert t["subcategory_code"] == "SENSOR_FAULT"
    assert t["subcategory_label_snapshot"] == "Sensor fault"


def test_ticket_rejects_subcategory_from_a_different_category(client):
    client.post("/cccapi/admin/reasons", json={
        "code": "QC_ONLY_REASON", "category_code": "QC", "label": "QC-only reason",
    }, headers=MGR)
    r = _make_ticket(client, category="MACHINE", subcategory_code="QC_ONLY_REASON")
    assert r.status_code == 400


def test_ticket_rejects_unknown_ticket_type(client):
    r = _make_ticket(client, ticket_type="NOT_A_TYPE")
    assert r.status_code == 400
