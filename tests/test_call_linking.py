from tests.conftest import auth_headers, LT_CATEGORY, LT_USERNAME, lt_ids

LT = auth_headers("LT", username=LT_USERNAME)
CT = auth_headers("CALL_TAKER")
MGR = auth_headers("CC_MANAGER")
SVC = auth_headers("SERVICE")


def _raise_lt_ticket(client):
    r = client.post("/cccapi/lt/tickets", data={
        "category": LT_CATEGORY, "reason_codes": "NO_POWER", "priority": "P1", "problem": "call-link test",
    }, headers=LT)
    assert r.status_code == 200, r.text
    return r.json()


def _register_call(client, **overrides):
    body = {"mmu_vehicle": "AP1", "district": "D", "problem": "regular call",
            "category": "MACHINE", "priority": "P2", "caller_name": "Test Caller", "caller_phone": "9876543210"}
    body.update(overrides)
    r = client.post("/cccapi/ticket", json=body, headers=CT)
    assert r.status_code == 200, r.text
    return r.json()


def test_lookup_by_number_returns_the_portal_ticket(client):
    created = _raise_lt_ticket(client)
    r = client.get(f"/cccapi/ticket/by-number/{created['ticket_no']}", headers=CT)
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]


def test_lookup_rejects_a_non_portal_ticket(client):
    created = _register_call(client)
    r = client.get(f"/cccapi/ticket/by-number/{created['ticket_no']}", headers=CT)
    assert r.status_code == 400


def test_lookup_rejects_unknown_ticket_number(client):
    r = client.get("/cccapi/ticket/by-number/CCC-NOPE-9999", headers=CT)
    assert r.status_code == 404


def test_lookup_forbidden_for_engineer(client):
    created = _raise_lt_ticket(client)
    r = client.get(f"/cccapi/ticket/by-number/{created['ticket_no']}", headers=SVC)
    assert r.status_code == 403


def test_log_call_adds_event_and_creates_no_new_ticket(client):
    created = _raise_lt_ticket(client)
    tid = created["id"]

    before = client.get("/cccapi/tickets", headers=MGR).json()["total"]
    r = client.post(f"/cccapi/ticket/{tid}/log-call",
                     json={"caller_name": "Ravi", "caller_phone": "9876543210", "note": "checking status"},
                     headers=CT)
    assert r.status_code == 200, r.text
    after = client.get("/cccapi/tickets", headers=MGR).json()["total"]
    assert after == before  # link only - no duplicate ticket

    events = client.get(f"/cccapi/ticket/{tid}", headers=MGR).json()["events"]
    assert any(e["action"] == "CALL_RECEIVED" for e in events)


def test_log_call_rejects_non_portal_ticket(client):
    created = _register_call(client)
    r = client.post(f"/cccapi/ticket/{created['id']}/log-call", json={"note": "x"}, headers=CT)
    assert r.status_code == 400


def test_log_call_forbidden_for_engineer(client):
    created = _raise_lt_ticket(client)
    r = client.post(f"/cccapi/ticket/{created['id']}/log-call", json={"note": "x"}, headers=SVC)
    assert r.status_code == 403


def test_register_call_machine_id_persists_on_ticket(client):
    created = _register_call(client, machine_id=lt_ids["machine_id"])
    r = client.get(f"/cccapi/ticket/{created['id']}", headers=MGR)
    assert r.json()["ticket"]["machine_id"] == lt_ids["machine_id"]
