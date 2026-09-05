import io
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from tests.conftest import auth_headers, LT_CDA_TEAM, LT_CATEGORY, LT_USERNAME, lt_ids
from app.db.database import SessionLocal
from app.models.config import Config
from app.services import webhooks as webhook_service

CT = auth_headers("CALL_TAKER")
SVC = auth_headers("SERVICE")
MGR = auth_headers("CC_MANAGER")
LT = auth_headers("LT", username=LT_USERNAME)


def make_ticket(client, priority="P2", category="MACHINE"):
    r = client.post("/cccapi/ticket", json={
        "mmu_vehicle": "AP39TEST1", "district": "Test District", "problem": "webhook test",
        "category": category, "priority": priority, "caller_name": "Test Caller", "caller_phone": "9876543210",
    }, headers=CT)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def make_lt_ticket(client):
    r = client.post("/cccapi/lt/tickets", data={
        "category": LT_CATEGORY, "reason_codes": "NO_POWER", "machine_id": str(lt_ids["machine_id"]),
        "priority": "P1", "problem": "field webhook test",
    }, headers=LT)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def configure_webhook(client, url, **extra):
    r = client.post("/cccapi/admin/webhooks/config", json={
        "url": url, "enabled": True, "events": webhook_service.WEBHOOK_EVENTS, **extra,
    }, headers=MGR)
    assert r.status_code == 200, r.text


class _EchoHandler(BaseHTTPRequestHandler):
    """A tiny local "external system" that records every delivery it gets -
    stands in for the Government EHR / vendor ticketing tool in the spec's
    manual verification plan, but automated so it runs in CI."""
    received = []
    response_status = 200

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        _EchoHandler.received.append({
            "event": self.headers.get("X-CCC-Event"),
            "signature": self.headers.get("X-CCC-Signature"),
            "delivery_id": self.headers.get("X-CCC-Delivery"),
            "body": body,
        })
        self.send_response(_EchoHandler.response_status)
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, *a):
        pass


@pytest.fixture
def echo_server():
    _EchoHandler.received = []
    _EchoHandler.response_status = 200
    server = HTTPServer(("127.0.0.1", 0), _EchoHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}/hook", _EchoHandler.received
    finally:
        server.shutdown()
        thread.join(timeout=2)


@pytest.fixture(autouse=True)
def _reset_webhook_config():
    """Every test starts from an unconfigured webhook (no ccc_config row) -
    mirrors _clean_tickets in conftest.py, just scoped to this file since
    webhook config isn't ticket data."""
    yield
    db = SessionLocal()
    db.query(Config).filter(Config.k == "webhook").delete()
    db.commit()
    db.close()


def _wait_for(predicate, timeout=3.0, interval=0.05):
    """Delivery is dispatched on a background thread - poll briefly instead
    of asserting immediately."""
    deadline = time.monotonic() + timeout
    ok = predicate()
    while not ok and time.monotonic() < deadline:
        time.sleep(interval)
        ok = predicate()
    return ok


# ---------- HMAC-SHA256 signature generation and verification ----------

def test_sign_and_verify_signature():
    secret = "topsecret"
    body = b'{"event":"ticket.created","data":{}}'
    sig = webhook_service.sign_payload(secret, body)
    assert sig.startswith("sha256=")
    assert webhook_service.verify_signature(secret, body, sig)
    assert not webhook_service.verify_signature(secret, body, "sha256=" + "0" * 64)
    assert not webhook_service.verify_signature("wrong-secret", body, sig)
    assert not webhook_service.verify_signature(secret, b"tampered body", sig)
    assert not webhook_service.verify_signature(secret, body, "")


# ---------- admin config endpoints ----------

def test_non_admin_cannot_read_or_update_webhook_config(client):
    assert client.get("/cccapi/admin/webhooks/config", headers=SVC).status_code == 403
    assert client.post("/cccapi/admin/webhooks/config", json={"enabled": True}, headers=SVC).status_code == 403


def test_admin_can_configure_webhook_and_secret_is_never_echoed_back(client):
    r = client.get("/cccapi/admin/webhooks/config", headers=MGR)
    assert r.status_code == 200
    assert r.json()["secret_set"] is False

    r = client.post("/cccapi/admin/webhooks/config", json={
        "url": "http://127.0.0.1:9/hook", "secret": "shh", "enabled": True,
        "events": ["ticket.created", "ticket.status_changed"], "timeout_seconds": 2,
    }, headers=MGR)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["url"] == "http://127.0.0.1:9/hook"
    assert body["enabled"] is True
    assert body["events"] == ["ticket.created", "ticket.status_changed"]
    assert body["secret_set"] is True
    assert "secret" not in body

    r = client.get("/cccapi/admin/webhooks/config", headers=MGR)
    assert r.json()["url"] == "http://127.0.0.1:9/hook"


def test_cannot_enable_without_a_url(client):
    r = client.post("/cccapi/admin/webhooks/config", json={"enabled": True, "url": ""}, headers=MGR)
    assert r.status_code == 400


def test_rejects_unknown_event(client):
    r = client.post("/cccapi/admin/webhooks/config", json={"events": ["not.a.real.event"]}, headers=MGR)
    assert r.status_code == 400


def test_rejects_malformed_url(client):
    r = client.post("/cccapi/admin/webhooks/config", json={"url": "not-a-url"}, headers=MGR)
    assert r.status_code == 400


# ---------- ticket actions trigger the dispatcher ----------

def test_ticket_created_dispatches_webhook_with_ccc_master_data(client, echo_server):
    url, received = echo_server
    r = client.post("/cccapi/admin/webhooks/config", json={
        "url": url, "secret": "s3cr3t", "enabled": True, "events": webhook_service.WEBHOOK_EVENTS,
    }, headers=MGR)
    assert r.status_code == 200, r.text

    tid = make_ticket(client, priority="P1", category="MACHINE")

    assert _wait_for(lambda: any(d["event"] == "ticket.created" for d in received))
    delivery = next(d for d in received if d["event"] == "ticket.created")
    assert webhook_service.verify_signature("s3cr3t", delivery["body"], delivery["signature"])

    envelope = json.loads(delivery["body"])
    assert envelope["event"] == "ticket.created"
    assert envelope["delivery_id"] == delivery["delivery_id"]
    data = envelope["data"]
    assert data["ticket_id"] == tid
    # CCC's OWN master data goes out, not whatever terms a caller might use
    assert data["category"] == "MACHINE"
    assert data["category_label"] == "Machine / Instrument Breakdown"
    assert data["priority"] == "P1"
    assert data["priority_label"]
    assert data["team"] == "SERVICE"
    assert data["team_label"]


def test_ticket_resolve_dispatches_status_changed(client, echo_server):
    url, received = echo_server
    client.post("/cccapi/admin/webhooks/config", json={
        "url": url, "enabled": True, "events": webhook_service.WEBHOOK_EVENTS,
    }, headers=MGR)

    tid = make_ticket(client)
    client.post("/cccapi/ticket/action", json={"id": tid, "action": "acknowledge"}, headers=SVC)
    r = client.post("/cccapi/ticket/action", json={"id": tid, "action": "resolve", "resolution": "fixed"}, headers=SVC)
    assert r.status_code == 200

    assert _wait_for(lambda: any(
        d["event"] == "ticket.status_changed" and json.loads(d["body"])["data"]["status"] == "RESOLVED"
        for d in received
    ))
    delivery = next(d for d in received if json.loads(d["body"])["data"].get("status") == "RESOLVED")
    data = json.loads(delivery["body"])["data"]
    assert data["old_status"] == "ACKNOWLEDGED"
    assert data["resolution"] == "fixed"


def test_ticket_close_dispatches_status_changed(client, echo_server):
    url, received = echo_server
    client.post("/cccapi/admin/webhooks/config", json={
        "url": url, "enabled": True, "events": webhook_service.WEBHOOK_EVENTS,
    }, headers=MGR)

    tid = make_ticket(client)
    for action, extra in [("acknowledge", {}), ("resolve", {"resolution": "fixed"}), ("confirm", {"confirmed_by": "x"})]:
        client.post("/cccapi/ticket/action", json={"id": tid, "action": action, **extra}, headers=SVC)
    r = client.post("/cccapi/ticket/action", json={"id": tid, "action": "close"}, headers=SVC)
    assert r.status_code == 200

    assert _wait_for(lambda: any(
        json.loads(d["body"])["data"].get("status") == "CLOSED" for d in received
    ))


def test_disabled_webhook_does_not_dispatch(client, echo_server):
    url, received = echo_server
    client.post("/cccapi/admin/webhooks/config", json={
        "url": url, "enabled": False, "events": webhook_service.WEBHOOK_EVENTS,
    }, headers=MGR)
    make_ticket(client)
    time.sleep(0.3)
    assert received == []


def test_unsubscribed_event_does_not_dispatch(client, echo_server):
    url, received = echo_server
    client.post("/cccapi/admin/webhooks/config", json={
        "url": url, "enabled": True, "events": ["ticket.escalated"],
    }, headers=MGR)
    make_ticket(client)
    time.sleep(0.3)
    assert received == []


# ---------- delivery failures never block/fail the local ticket transaction ----------

def test_unreachable_webhook_does_not_block_or_fail_ticket_creation(client):
    client.post("/cccapi/admin/webhooks/config", json={
        "url": "http://127.0.0.1:9/nowhere", "enabled": True,
        "events": webhook_service.WEBHOOK_EVENTS, "timeout_seconds": 1,
    }, headers=MGR)

    started = time.monotonic()
    tid = make_ticket(client)
    elapsed = time.monotonic() - started
    assert elapsed < 2.0  # request returned immediately - dispatch is backgrounded

    r = client.get(f"/cccapi/ticket/{tid}", headers=SVC)
    assert r.status_code == 200
    assert r.json()["ticket"]["status"] == "ASSIGNED"


def test_5xx_webhook_response_does_not_interrupt_ticket_action(client, echo_server):
    url, received = echo_server
    _EchoHandler.response_status = 500
    client.post("/cccapi/admin/webhooks/config", json={
        "url": url, "enabled": True, "events": webhook_service.WEBHOOK_EVENTS, "timeout_seconds": 1,
    }, headers=MGR)

    tid = make_ticket(client)

    r = client.get(f"/cccapi/ticket/{tid}", headers=SVC)
    assert r.status_code == 200
    assert r.json()["ticket"]["status"] == "ASSIGNED"

    # The dispatcher still tried delivering (and will keep retrying) despite the 500 -
    # the ticket transaction itself is unaffected either way.
    assert _wait_for(lambda: len(received) >= 1)


# ---------- every ticket entry point / update path dispatches ----------

def test_lt_portal_ticket_creation_dispatches_webhook(client, echo_server):
    url, received = echo_server
    configure_webhook(client, url)

    tid = make_lt_ticket(client)

    assert _wait_for(lambda: any(d["event"] == "ticket.created" for d in received))
    data = json.loads(next(d for d in received if d["event"] == "ticket.created")["body"])["data"]
    assert data["ticket_id"] == tid
    assert data["category"] == LT_CATEGORY
    assert data["team"] == LT_CDA_TEAM


def test_repriority_dispatches_note_added(client, echo_server):
    url, received = echo_server
    configure_webhook(client, url)

    tid = make_ticket(client, priority="P2")
    r = client.post("/cccapi/ticket/action", json={"id": tid, "action": "repriority", "priority": "P1"}, headers=MGR)
    assert r.status_code == 200, r.text

    assert _wait_for(lambda: any(
        d["event"] == "ticket.note_added" and json.loads(d["body"])["data"]["priority"] == "P1" for d in received
    ))


def test_log_call_dispatches_note_added(client, echo_server):
    url, received = echo_server
    configure_webhook(client, url)

    tid = make_lt_ticket(client)
    r = client.post(f"/cccapi/ticket/{tid}/log-call",
                     json={"caller_name": "Ravi", "caller_phone": "9876543210", "note": "checking status"},
                     headers=CT)
    assert r.status_code == 200, r.text

    assert _wait_for(lambda: any(
        d["event"] == "ticket.note_added" and "checking status" in (json.loads(d["body"])["data"].get("note") or "")
        for d in received
    ))


def test_attachment_upload_dispatches_note_added(client, echo_server):
    url, received = echo_server
    configure_webhook(client, url)

    tid = make_ticket(client)
    png = ("photo.png", io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"0" * 100), "image/png")
    r = client.post(f"/cccapi/ticket/{tid}/attachments", data={"note": "before photo"}, files={"file": png}, headers=SVC)
    assert r.status_code == 200, r.text

    assert _wait_for(lambda: any(
        d["event"] == "ticket.note_added" and "photo.png" in (json.loads(d["body"])["data"].get("note") or "")
        for d in received
    ))


# ---------- master-data events: category/priority CRUD ----------

def test_category_created_dispatches_webhook(client, echo_server):
    url, received = echo_server
    configure_webhook(client, url)

    r = client.post("/cccapi/admin/categories", json={
        "code": "WEBHOOKCAT", "label": "Webhook Test Category", "team_code": "SERVICE",
    }, headers=MGR)
    assert r.status_code == 200, r.text

    assert _wait_for(lambda: any(d["event"] == "category.created" for d in received))
    data = json.loads(next(d for d in received if d["event"] == "category.created")["body"])["data"]
    assert data["code"] == "WEBHOOKCAT"
    assert data["label"] == "Webhook Test Category"
    assert data["team_code"] == "SERVICE"


def test_category_updated_dispatches_webhook(client, echo_server):
    url, received = echo_server
    client.post("/cccapi/admin/categories", json={
        "code": "WEBHOOKCAT2", "label": "Original Label", "team_code": "SERVICE",
    }, headers=MGR)
    configure_webhook(client, url)

    r = client.put("/cccapi/admin/categories/WEBHOOKCAT2", json={"label": "Updated Label"}, headers=MGR)
    assert r.status_code == 200, r.text

    assert _wait_for(lambda: any(d["event"] == "category.updated" for d in received))
    data = json.loads(next(d for d in received if d["event"] == "category.updated")["body"])["data"]
    assert data["code"] == "WEBHOOKCAT2"
    assert data["label"] == "Updated Label"


def test_priority_tat_update_dispatches_webhook(client, echo_server):
    url, received = echo_server
    configure_webhook(client, url)

    r = client.put("/cccapi/admin/sla", json={"tat": {"P1": 180}}, headers=MGR)
    assert r.status_code == 200, r.text

    assert _wait_for(lambda: any(d["event"] == "priority.updated" for d in received))
    data = json.loads(next(d for d in received if d["event"] == "priority.updated")["body"])["data"]
    assert data["priority"] == "P1"
    assert data["tat_minutes"] == 180
    assert data["priority_label"]


# ---------- admin test-ping endpoint ----------

def test_admin_test_ping_endpoint(client, echo_server):
    url, received = echo_server
    r = client.post("/cccapi/admin/webhooks/config", json={"url": url, "secret": "pingsecret"}, headers=MGR)
    assert r.status_code == 200, r.text

    r = client.post("/cccapi/admin/webhooks/test", headers=MGR)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["status_code"] == 200

    assert len(received) == 1
    delivery = received[0]
    assert delivery["event"] == "webhook.ping"
    assert webhook_service.verify_signature("pingsecret", delivery["body"], delivery["signature"])
    envelope = json.loads(delivery["body"])
    assert envelope["event"] == "webhook.ping"


def test_test_ping_requires_url_configured(client):
    r = client.post("/cccapi/admin/webhooks/test", headers=MGR)
    assert r.status_code == 400


def test_test_ping_reports_failure_for_unreachable_url(client):
    r = client.post("/cccapi/admin/webhooks/config", json={
        "url": "http://127.0.0.1:9/nowhere", "timeout_seconds": 1,
    }, headers=MGR)
    assert r.status_code == 200, r.text

    r = client.post("/cccapi/admin/webhooks/test", headers=MGR)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert "error" in body
