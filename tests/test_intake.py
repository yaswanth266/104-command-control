from tests.conftest import auth_headers, INTAKE_KEY

MGR = auth_headers("CC_MANAGER")
KEY_HEADER = {"X-Intake-Key": INTAKE_KEY}


def test_valid_field_app_payload_creates_ticket(client):
    r = client.post("/cccapi/intake", json={
        "source": "whatever-the-caller-sends", "category": "device", "priority": "critical",
        "vehicle": "AP39FIELD1", "district": "Field District",
        "raised_by_name": "LT Officer", "subject": "Analyzer down", "detail": "won't power on",
    }, headers=KEY_HEADER)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["team"] == "SERVICE"  # category DEVICE -> MACHINE -> SERVICE
    assert body["priority"] == "P1"   # priority CRITICAL -> P1

    r2 = client.get(f"/cccapi/ticket/{body['id']}", headers=MGR)
    t = r2.json()["ticket"]
    assert t["source"] == "GOV_EHR"  # forced server-side regardless of what the caller sent
    assert t["mmu_vehicle"] == "AP39FIELD1"
    assert t["status"] == "ASSIGNED"


def test_missing_key_rejected(client):
    r = client.post("/cccapi/intake", json={"category": "device"})
    assert r.status_code == 401


def test_wrong_key_rejected(client):
    r = client.post("/cccapi/intake", json={"category": "device"}, headers={"X-Intake-Key": "not-the-real-key"})
    assert r.status_code == 401


def test_missing_fields_default_gracefully(client):
    r = client.post("/cccapi/intake", json={}, headers=KEY_HEADER)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["category"] == "OTHER"
    assert body["priority"] == "P3"


def test_unknown_category_and_priority_fall_back(client):
    r = client.post("/cccapi/intake", json={"category": "not-a-real-category", "priority": "not-a-real-priority"}, headers=KEY_HEADER)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["category"] == "OTHER"
    assert body["priority"] == "P3"


def test_malformed_payload_type_does_not_500(client):
    # a non-object JSON body should be rejected cleanly, not crash the server
    r = client.post("/cccapi/intake", json=["not", "an", "object"], headers=KEY_HEADER)
    assert r.status_code in (400, 422)
