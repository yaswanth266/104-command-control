import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from tests.conftest import auth_headers
from app.db.database import SessionLocal
from app.models.config import Config

MGR = auth_headers("CC_MANAGER")
CT = auth_headers("CALL_TAKER")
SVC = auth_headers("SERVICE")


def _make_ticket(client):
    r = client.post("/cccapi/ticket", json={
        "mmu_vehicle": "AP39TEST1", "district": "Test District", "problem": "external hierarchy test",
        "category": "MACHINE", "priority": "P2", "caller_name": "Test Caller", "caller_phone": "9876543210",
    }, headers=CT)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _chain(client, tid):
    return client.get(f"/cccapi/ticket/{tid}/assignments", headers=MGR).json()


class _HierarchyHandler(BaseHTTPRequestHandler):
    """Stands in for a real external hierarchy/organization API."""
    response_body = {}
    response_status = 200

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        self.send_response(_HierarchyHandler.response_status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(_HierarchyHandler.response_body).encode("utf-8"))

    def log_message(self, *a):
        pass


@pytest.fixture
def hierarchy_server():
    _HierarchyHandler.response_body = {}
    _HierarchyHandler.response_status = 200
    server = HTTPServer(("127.0.0.1", 0), _HierarchyHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}/hierarchy"
    finally:
        server.shutdown()
        thread.join(timeout=2)


@pytest.fixture(autouse=True)
def _reset_hierarchy_config():
    yield
    db = SessionLocal()
    db.query(Config).filter(Config.k == "hierarchy").delete()
    db.commit()
    db.close()


def _configure_external(client, url, **extra):
    r = client.put("/cccapi/admin/hierarchy/config", json={"mode": "EXTERNAL_API", "url": url, **extra}, headers=MGR)
    assert r.status_code == 200, r.text
    return r.json()


def test_default_config_is_local_mode(client):
    r = client.get("/cccapi/admin/hierarchy/config", headers=MGR)
    assert r.status_code == 200
    assert r.json()["mode"] == "LOCAL"


def test_cannot_switch_to_external_api_without_a_url(client):
    r = client.put("/cccapi/admin/hierarchy/config", json={"mode": "EXTERNAL_API"}, headers=MGR)
    assert r.status_code == 400


def test_auth_token_is_never_echoed_back(client, hierarchy_server):
    _configure_external(client, hierarchy_server, auth_header="Authorization", auth_token="Bearer secret123")
    r = client.get("/cccapi/admin/hierarchy/config", headers=MGR)
    assert r.json()["auth_token"] is None
    assert r.json()["auth_token_set"] is True


def test_non_admin_cannot_manage_hierarchy_config(client):
    r = client.put("/cccapi/admin/hierarchy/config", json={"mode": "LOCAL"}, headers=SVC)
    assert r.status_code == 403


def test_external_api_success_produces_a_chain_with_that_source(client, hierarchy_server):
    _HierarchyHandler.response_body = {
        "hierarchy": [
            {"level": "L1", "username": "service", "teamId": "SERVICE", "teamName": "Service Team"},
            {"level": "L2", "username": "cc_manager"},
        ]
    }
    _configure_external(client, hierarchy_server)

    tid = _make_ticket(client)
    chain = _chain(client, tid)
    l1 = next(r for r in chain if r["level"] == "L1")
    l2 = next(r for r in chain if r["level"] == "L2")
    assert l1["source"] == "EXTERNAL_API"
    assert l1["user_name"] == "Service"
    assert l2["user_name"] == "Cc Manager"

    r = client.get("/cccapi/admin/assignment-exceptions", headers=MGR)
    assert not any(e["ticket_id"] == tid for e in r.json())


def test_external_api_flat_user_list_is_assigned_in_order(client, hierarchy_server):
    _HierarchyHandler.response_body = {"users": [{"username": "service"}, {"username": "cc_manager"}]}
    _configure_external(client, hierarchy_server)

    tid = _make_ticket(client)
    chain = _chain(client, tid)
    l1 = next(r for r in chain if r["level"] == "L1")
    l2 = next(r for r in chain if r["level"] == "L2")
    assert l1["user_name"] == "Service"
    assert l2["user_name"] == "Cc Manager"


def test_external_api_failure_falls_back_to_local_and_creates_exception(client, hierarchy_server):
    _HierarchyHandler.response_status = 500
    _configure_external(client, hierarchy_server)

    tid = _make_ticket(client)
    chain = _chain(client, tid)
    l1 = next(r for r in chain if r["level"] == "L1")
    assert l1["source"] == "LOCAL"  # fell back
    assert l1["team_code"] == "SERVICE"

    r = client.get("/cccapi/admin/assignment-exceptions?status=OPEN", headers=MGR)
    assert any(e["ticket_id"] == tid and e["reason"] == "API_FAILURE" for e in r.json())


def test_external_api_unreachable_falls_back_and_creates_exception(client):
    _configure_external(client, "http://127.0.0.1:1/unreachable", timeout_seconds=1)
    tid = _make_ticket(client)
    chain = _chain(client, tid)
    l1 = next(r for r in chain if r["level"] == "L1")
    assert l1["source"] == "LOCAL"

    r = client.get("/cccapi/admin/assignment-exceptions", headers=MGR)
    assert any(e["ticket_id"] == tid for e in r.json())


def test_admin_can_resolve_an_assignment_exception(client):
    _configure_external(client, "http://127.0.0.1:1/unreachable", timeout_seconds=1)
    tid = _make_ticket(client)
    r = client.get("/cccapi/admin/assignment-exceptions?status=OPEN", headers=MGR)
    exc = next(e for e in r.json() if e["ticket_id"] == tid)

    r = client.post(f"/cccapi/admin/assignment-exceptions/{exc['id']}/resolve", headers=MGR)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "RESOLVED"
    assert r.json()["resolved_by"] == "cc_manager"

    r = client.get("/cccapi/admin/assignment-exceptions?status=OPEN", headers=MGR)
    assert not any(e["id"] == exc["id"] for e in r.json())


def test_hierarchy_test_endpoint_reports_connectivity(client, hierarchy_server):
    _configure_external(client, hierarchy_server)
    r = client.post("/cccapi/admin/hierarchy/test", headers=MGR)
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_hierarchy_test_endpoint_requires_external_mode_configured(client):
    r = client.post("/cccapi/admin/hierarchy/test", headers=MGR)
    assert r.status_code == 400
