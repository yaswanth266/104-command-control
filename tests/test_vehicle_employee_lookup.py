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


class _LookupHandler(BaseHTTPRequestHandler):
    """Stands in for the real vehicle/employee lookup API."""
    response_body = {}
    response_status = 200

    def do_GET(self):
        self.send_response(_LookupHandler.response_status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(_LookupHandler.response_body).encode("utf-8"))

    def log_message(self, *a):
        pass


@pytest.fixture
def lookup_server():
    _LookupHandler.response_body = {}
    _LookupHandler.response_status = 200
    server = HTTPServer(("127.0.0.1", 0), _LookupHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
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


def test_vehicle_lookup_unconfigured_returns_not_configured(client):
    r = client.get("/cccapi/tickets/lookup/vehicle?registration_no=AP39TEST1", headers=CT)
    assert r.status_code == 200
    assert r.json() == {"configured": False, "found": False, "data": None, "error": None}


def test_employee_lookup_unconfigured_returns_not_configured(client):
    r = client.get("/cccapi/tickets/lookup/employees?q=ravi", headers=CT)
    assert r.status_code == 200
    assert r.json() == {"configured": False, "results": [], "error": None}


def test_non_call_registering_role_cannot_use_vehicle_lookup(client):
    r = client.get("/cccapi/tickets/lookup/vehicle?registration_no=AP39TEST1", headers=SVC)
    assert r.status_code == 403


def test_vehicle_lookup_found_normalizes_snake_case_response(client, lookup_server):
    r = client.put("/cccapi/admin/hierarchy/config", json={"vehicle_lookup_url": lookup_server}, headers=MGR)
    assert r.status_code == 200, r.text
    assert r.json()["vehicle_lookup_url"] == lookup_server

    _LookupHandler.response_body = {
        "segment_number": "SEG-42", "district": "Krishna", "mandal": "Machilipatnam",
        "secretariat": "Ward-7", "village": "Peddana",
    }
    r = client.get("/cccapi/tickets/lookup/vehicle?registration_no=AP39TEST1", headers=CT)
    assert r.status_code == 200
    body = r.json()
    assert body["configured"] is True
    assert body["found"] is True
    assert body["data"]["segment_number"] == "SEG-42"
    assert body["data"]["secretariat"] == "Ward-7"
    assert body["data"]["village"] == "Peddana"


def test_vehicle_lookup_tolerates_camel_case_and_nested_shape(client, lookup_server):
    client.put("/cccapi/admin/hierarchy/config", json={"vehicle_lookup_url": lookup_server}, headers=MGR)
    _LookupHandler.response_body = {"vehicle": {"segmentNumber": "SEG-9", "villageName": "Gudivada"}}
    r = client.get("/cccapi/tickets/lookup/vehicle?registration_no=AP39TEST2", headers=CT)
    data = r.json()["data"]
    assert data["segment_number"] == "SEG-9"
    assert data["village"] == "Gudivada"


def test_vehicle_lookup_empty_response_is_not_found(client, lookup_server):
    client.put("/cccapi/admin/hierarchy/config", json={"vehicle_lookup_url": lookup_server}, headers=MGR)
    _LookupHandler.response_body = {}
    r = client.get("/cccapi/tickets/lookup/vehicle?registration_no=UNKNOWN", headers=CT)
    body = r.json()
    assert body["configured"] is True
    assert body["found"] is False


def test_vehicle_lookup_failure_degrades_gracefully(client):
    client.put("/cccapi/admin/hierarchy/config",
               json={"vehicle_lookup_url": "http://127.0.0.1:1/unreachable", "timeout_seconds": 1}, headers=MGR)
    r = client.get("/cccapi/tickets/lookup/vehicle?registration_no=AP39TEST1", headers=CT)
    assert r.status_code == 200
    body = r.json()
    assert body["configured"] is True
    assert body["found"] is False
    assert body["error"]


def test_employee_lookup_normalizes_flat_list(client, lookup_server):
    client.put("/cccapi/admin/hierarchy/config", json={"employee_lookup_url": lookup_server}, headers=MGR)
    _LookupHandler.response_body = [
        {"employeeId": "E100", "employeeName": "Ravi Kumar", "designation": "Field Engineer"},
    ]
    r = client.get("/cccapi/tickets/lookup/employees?q=ravi", headers=CT)
    body = r.json()
    assert body["configured"] is True
    assert body["results"] == [{"emp_id": "E100", "name": "Ravi Kumar", "designation": "Field Engineer"}]


def test_employee_lookup_normalizes_wrapped_list(client, lookup_server):
    client.put("/cccapi/admin/hierarchy/config", json={"employee_lookup_url": lookup_server}, headers=MGR)
    _LookupHandler.response_body = {"employees": [{"emp_id": "E200", "name": "Anita", "designation": "Supervisor"}]}
    r = client.get("/cccapi/tickets/lookup/employees?q=anita", headers=CT)
    assert r.json()["results"] == [{"emp_id": "E200", "name": "Anita", "designation": "Supervisor"}]


def test_ticket_creation_persists_segment_and_caller_lookup_fields(client):
    r = client.post("/cccapi/ticket", json={
        "mmu_vehicle": "AP39TEST1", "district": "Test District", "problem": "lookup fields test",
        "category": "MACHINE", "priority": "P2", "caller_name": "Ravi Kumar", "caller_phone": "9876543210",
        "segment_number": "SEG-42", "secretariat": "Ward-7", "village": "Peddana",
        "caller_emp_id": "E100", "caller_designation": "Field Engineer",
    }, headers=CT)
    assert r.status_code == 200, r.text
    tid = r.json()["id"]
    r = client.get(f"/cccapi/ticket/{tid}", headers=MGR)
    body = r.json()["ticket"]
    assert body["segment_number"] == "SEG-42"
    assert body["secretariat"] == "Ward-7"
    assert body["village"] == "Peddana"
    assert body["caller_emp_id"] == "E100"
    assert body["caller_designation"] == "Field Engineer"


def test_admin_can_configure_and_test_vehicle_lookup_url(client, lookup_server):
    r = client.put("/cccapi/admin/hierarchy/config", json={"vehicle_lookup_url": lookup_server}, headers=MGR)
    assert r.status_code == 200
    r = client.post("/cccapi/admin/hierarchy/test-vehicle-lookup", headers=MGR)
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_admin_test_vehicle_lookup_requires_url_configured(client):
    r = client.post("/cccapi/admin/hierarchy/test-vehicle-lookup", headers=MGR)
    assert r.status_code == 400


def test_admin_can_configure_and_test_employee_lookup_url(client, lookup_server):
    r = client.put("/cccapi/admin/hierarchy/config", json={"employee_lookup_url": lookup_server}, headers=MGR)
    assert r.status_code == 200
    r = client.post("/cccapi/admin/hierarchy/test-employee-lookup", headers=MGR)
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_lookup_urls_rejected_without_scheme(client):
    r = client.put("/cccapi/admin/hierarchy/config", json={"vehicle_lookup_url": "not-a-url"}, headers=MGR)
    assert r.status_code == 400


def test_non_admin_cannot_configure_lookup_urls(client, lookup_server):
    r = client.put("/cccapi/admin/hierarchy/config", json={"vehicle_lookup_url": lookup_server}, headers=SVC)
    assert r.status_code == 403
