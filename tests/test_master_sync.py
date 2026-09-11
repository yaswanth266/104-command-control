"""Phase 5 stage 2: the 5-minute master-data sync (vehicle/employee/hierarchy
roster cache). Exercises app/services/master_sync.py directly (like
sla_sweep.py's own tests call run_sla_sweep_once() rather than waiting for
the loop) and the admin Sync Status/Run endpoints, against a real loopback
HTTP server standing in for the external roster API - same pattern as
tests/test_vehicle_employee_lookup.py and test_assignment_exceptions.py."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from tests.conftest import auth_headers
from app.db.database import SessionLocal
from app.models.config import Config
from app.services.master_sync import run_master_sync_once

MGR = auth_headers("CC_MANAGER")
CT = auth_headers("CALL_TAKER")
SVC = auth_headers("SERVICE")


class _RosterHandler(BaseHTTPRequestHandler):
    """One handler standing in for all three roster endpoints, branching on
    path suffix (…/vehicles, …/employees, …/hierarchy)."""
    bodies = {"vehicles": [], "employees": [], "hierarchy": []}
    status = 200

    def do_GET(self):
        key = self.path.strip("/").rsplit("/", 1)[-1]
        self.send_response(_RosterHandler.status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(_RosterHandler.bodies.get(key, [])).encode("utf-8"))

    def log_message(self, *a):
        pass


@pytest.fixture
def roster_server():
    _RosterHandler.bodies = {"vehicles": [], "employees": [], "hierarchy": []}
    _RosterHandler.status = 200
    server = HTTPServer(("127.0.0.1", 0), _RosterHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{port}"
        yield {"vehicles": f"{base}/vehicles", "employees": f"{base}/employees", "hierarchy": f"{base}/hierarchy"}
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
    from app.models.ext_vehicle import ExtVehicle
    from app.models.ext_employee import ExtEmployee
    from app.models.emp_hierarchy import EmpHierarchy
    from app.models.sync_run import SyncRun
    db = SessionLocal()
    db.query(ExtVehicle).delete()
    db.query(ExtEmployee).delete()
    db.query(EmpHierarchy).delete()
    db.query(SyncRun).delete()
    db.commit()
    db.close()


def _configure(client, urls, enabled=True):
    r = client.put("/cccapi/admin/hierarchy/config", json={
        "vehicle_roster_url": urls["vehicles"], "employee_roster_url": urls["employees"],
        "hierarchy_roster_url": urls["hierarchy"], "sync_enabled": enabled,
    }, headers=MGR)
    assert r.status_code == 200, r.text
    return r.json()


def test_sync_disabled_by_default_does_nothing(client, roster_server):
    """Asserts no NEW sync run happens while disabled, rather than that the
    'vehicles' job has never run at all - job history is global (ccc_sync_run
    has no per-test scoping, like Teams/Categories elsewhere in this suite),
    so another test file may have already run a real sync before this one."""
    before = client.get("/cccapi/admin/sync/status", headers=MGR).json()["vehicles"]
    _RosterHandler.bodies["vehicles"] = [{"registration_no": "AP1", "segment_number": "S1"}]
    # roster URLs configured but sync left disabled
    client.put("/cccapi/admin/hierarchy/config", json={
        "vehicle_roster_url": roster_server["vehicles"], "sync_enabled": False,
    }, headers=MGR)
    run_master_sync_once()
    after = client.get("/cccapi/admin/sync/status", headers=MGR).json()["vehicles"]
    # Compare identity fields only - age_minutes is recomputed from "now" on
    # every call and could tick over a minute boundary between the two reads.
    assert after["finished_at"] == before["finished_at"]
    assert after["status"] == before["status"]
    assert after["rows_upserted"] == before["rows_upserted"]


def test_sync_enabled_populates_all_three_caches(client, roster_server):
    _RosterHandler.bodies["vehicles"] = [
        {"registration_no": "AP39SYNC1", "segment_number": "SEG-1", "district": "Krishna",
         "mandal": "Machilipatnam", "secretariat": "Ward-7", "village": "Peddana"},
    ]
    _RosterHandler.bodies["employees"] = [
        {"emp_code": "E900", "name": "Sync Employee", "designation": "OE Officer", "role_code": "OE"},
    ]
    _RosterHandler.bodies["hierarchy"] = [
        {"emp_code": "E100", "role_code": "OE", "holder_emp_code": "E900", "holder_name": "Sync Employee",
         "holder_designation": "OE Officer"},
    ]
    _configure(client, roster_server)
    run_master_sync_once()

    status = client.get("/cccapi/admin/sync/status", headers=MGR).json()
    assert status["vehicles"]["status"] == "SUCCESS"
    assert status["vehicles"]["rows_upserted"] == 1
    assert status["employees"]["status"] == "SUCCESS"
    assert status["hierarchy"]["status"] == "SUCCESS"

    # Cache-first vehicle lookup now serves from the synced cache
    r = client.get("/cccapi/tickets/lookup/vehicle?registration_no=AP39SYNC1", headers=CT)
    body = r.json()
    assert body["source"] == "CACHE"
    assert body["data"]["segment_number"] == "SEG-1"
    assert body["data"]["village"] == "Peddana"

    r = client.get("/cccapi/tickets/lookup/employees?q=Sync", headers=CT)
    body = r.json()
    assert body["source"] == "CACHE"
    assert any(e["emp_id"] == "E900" for e in body["results"])


def test_truncated_response_aborts_and_keeps_existing_cache(client, roster_server):
    _RosterHandler.bodies["vehicles"] = [
        {"registration_no": f"AP39TRUNC{i}", "segment_number": f"SEG-{i}"} for i in range(10)
    ]
    _configure(client, roster_server)
    run_master_sync_once()
    status = client.get("/cccapi/admin/sync/status", headers=MGR).json()
    assert status["vehicles"]["status"] == "SUCCESS"
    assert status["vehicles"]["rows_upserted"] == 10

    # Second sync returns far fewer rows than currently cached - must abort,
    # not wipe the roster down to 1 active vehicle.
    _RosterHandler.bodies["vehicles"] = [{"registration_no": "AP39TRUNC0", "segment_number": "SEG-0"}]
    run_master_sync_once()
    status = client.get("/cccapi/admin/sync/status", headers=MGR).json()
    assert status["vehicles"]["status"] == "ERROR"

    r = client.get("/cccapi/tickets/lookup/vehicle?registration_no=AP39TRUNC5", headers=CT)
    assert r.json()["found"] is True  # still cached from the first, successful sync


def test_manual_sync_run_works_even_when_sync_disabled(client, roster_server):
    _RosterHandler.bodies["employees"] = [{"emp_code": "E901", "name": "Manual Sync", "designation": "DM"}]
    client.put("/cccapi/admin/hierarchy/config", json={
        "employee_roster_url": roster_server["employees"], "sync_enabled": False,
    }, headers=MGR)
    r = client.post("/cccapi/admin/sync/run", headers=MGR)
    assert r.status_code == 200, r.text
    assert r.json()["employees"]["status"] == "SUCCESS"


def test_non_admin_cannot_view_or_trigger_sync(client):
    assert client.get("/cccapi/admin/sync/status", headers=SVC).status_code == 403
    assert client.post("/cccapi/admin/sync/run", headers=SVC).status_code == 403


def test_cannot_enable_sync_without_any_roster_url(client):
    r = client.put("/cccapi/admin/hierarchy/config", json={"sync_enabled": True}, headers=MGR)
    assert r.status_code == 400
