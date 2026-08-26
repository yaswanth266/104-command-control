from tests.conftest import auth_headers

CT = auth_headers("CALL_TAKER")
SVC = auth_headers("SERVICE")
MGR = auth_headers("CC_MANAGER")


def make_ticket(client, priority="P2", category="MACHINE"):
    r = client.post("/cccapi/ticket", json={
        "mmu_vehicle": "AP39TEST1", "district": "Test District", "problem": "workflow test",
        "category": category, "priority": priority,
    }, headers=CT)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_full_lifecycle(client):
    tid = make_ticket(client)

    r = client.get(f"/cccapi/ticket/{tid}", headers=SVC)
    assert r.json()["ticket"]["status"] == "ASSIGNED"

    r = client.post("/cccapi/ticket/action", json={"id": tid, "action": "acknowledge"}, headers=SVC)
    assert r.status_code == 200
    assert r.json()["action"] == "acknowledge"

    r = client.post("/cccapi/ticket/action", json={"id": tid, "action": "start"}, headers=SVC)
    assert r.status_code == 200

    r = client.post("/cccapi/ticket/action", json={"id": tid, "action": "resolve", "resolution": "fixed",
                                                     "diagnosis": "d", "action_taken": "a", "root_cause": "rc", "parts": "p"}, headers=SVC)
    assert r.status_code == 200

    r = client.post("/cccapi/ticket/action", json={"id": tid, "action": "confirm", "confirmed_by": "Ramesh"}, headers=SVC)
    assert r.status_code == 200

    r = client.post("/cccapi/ticket/action", json={"id": tid, "action": "close"}, headers=SVC)
    assert r.status_code == 200

    r = client.get(f"/cccapi/ticket/{tid}", headers=SVC)
    t = r.json()["ticket"]
    assert t["status"] == "CLOSED"
    assert t["diagnosis"] == "d" and t["action_taken"] == "a" and t["root_cause"] == "rc" and t["parts"] == "p"
    assert t["resolution"] == "fixed"
    assert t["confirmed_by"] == "Ramesh"


def test_cannot_resolve_before_acknowledge(client):
    tid = make_ticket(client)
    r = client.post("/cccapi/ticket/action", json={"id": tid, "action": "resolve", "resolution": "x"}, headers=SVC)
    assert r.status_code == 409


def test_cannot_close_before_confirm(client):
    tid = make_ticket(client)
    client.post("/cccapi/ticket/action", json={"id": tid, "action": "acknowledge"}, headers=SVC)
    client.post("/cccapi/ticket/action", json={"id": tid, "action": "resolve", "resolution": "fixed"}, headers=SVC)
    r = client.post("/cccapi/ticket/action", json={"id": tid, "action": "close"}, headers=SVC)
    assert r.status_code == 409


def test_cannot_start_on_closed_ticket(client):
    tid = make_ticket(client)
    for action, extra in [("acknowledge", {}), ("resolve", {"resolution": "x"}),
                           ("confirm", {"confirmed_by": "x"}), ("close", {})]:
        r = client.post("/cccapi/ticket/action", json={"id": tid, "action": action, **extra}, headers=SVC)
        assert r.status_code == 200, (action, r.text)
    r = client.post("/cccapi/ticket/action", json={"id": tid, "action": "start"}, headers=SVC)
    assert r.status_code == 409


def test_empty_resolution_blocked(client):
    tid = make_ticket(client)
    client.post("/cccapi/ticket/action", json={"id": tid, "action": "acknowledge"}, headers=SVC)
    r = client.post("/cccapi/ticket/action", json={"id": tid, "action": "resolve", "resolution": "  "}, headers=SVC)
    assert r.status_code == 400


def test_empty_pending_reason_blocked(client):
    tid = make_ticket(client)
    client.post("/cccapi/ticket/action", json={"id": tid, "action": "acknowledge"}, headers=SVC)
    r = client.post("/cccapi/ticket/action", json={"id": tid, "action": "pending", "pending_reason": ""}, headers=SVC)
    assert r.status_code == 400


def test_empty_confirmed_by_blocked(client):
    tid = make_ticket(client)
    client.post("/cccapi/ticket/action", json={"id": tid, "action": "acknowledge"}, headers=SVC)
    client.post("/cccapi/ticket/action", json={"id": tid, "action": "resolve", "resolution": "x"}, headers=SVC)
    r = client.post("/cccapi/ticket/action", json={"id": tid, "action": "confirm", "confirmed_by": ""}, headers=SVC)
    assert r.status_code == 400


def test_reopen_requires_reason(client):
    tid = make_ticket(client)
    for action, extra in [("acknowledge", {}), ("resolve", {"resolution": "x"}),
                           ("confirm", {"confirmed_by": "x"}), ("close", {})]:
        client.post("/cccapi/ticket/action", json={"id": tid, "action": action, **extra}, headers=SVC)
    r = client.post("/cccapi/ticket/action", json={"id": tid, "action": "reopen"}, headers=MGR)
    assert r.status_code == 400
    r = client.post("/cccapi/ticket/action", json={"id": tid, "action": "reopen", "note": "recurred"}, headers=MGR)
    assert r.status_code == 200


def test_escalate_blocked_on_closed_ticket(client):
    tid = make_ticket(client)
    for action, extra in [("acknowledge", {}), ("resolve", {"resolution": "x"}),
                           ("confirm", {"confirmed_by": "x"}), ("close", {})]:
        client.post("/cccapi/ticket/action", json={"id": tid, "action": action, **extra}, headers=SVC)
    r = client.post("/cccapi/ticket/action", json={"id": tid, "action": "escalate"}, headers=SVC)
    assert r.status_code == 409
