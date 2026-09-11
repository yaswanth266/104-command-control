"""Phase 5 stage 3: the L1-L4 escalation ladder's cross-cutting behaviors
that test_tiered_sla.py and test_location_routing_and_dynamic_sla.py don't
already cover in depth - the "no occupant at a level" cascade, and a
belt-and-suspenders idempotency check at the ccc_event level (not just
notifications)."""
import json
import threading
import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from tests.conftest import auth_headers
from app.db.database import SessionLocal
from app.models.ticket import Ticket
from app.models.config import Config
from app.services.sla_sweep import run_sla_sweep_once

MGR = auth_headers("CC_MANAGER")
CT = auth_headers("CALL_TAKER")
SVC = auth_headers("SERVICE")


class _HierarchyHandler(BaseHTTPRequestHandler):
    response_body = {}

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(_HierarchyHandler.response_body).encode("utf-8"))

    def log_message(self, *a):
        pass


@pytest.fixture
def hierarchy_server():
    _HierarchyHandler.response_body = {}
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


def _make_ticket(client, tat_mins=240):
    r = client.post("/cccapi/ticket", json={
        "mmu_vehicle": "AP1", "district": "D", "problem": "escalation chain test",
        "category": "MACHINE", "priority": "P1", "caller_name": "Test Caller", "caller_phone": "9876543210",
    }, headers=CT)
    assert r.status_code == 200, r.text
    tid = r.json()["id"]
    db = SessionLocal()
    t = db.query(Ticket).filter(Ticket.id == tid).first()
    now = datetime.datetime.now()
    t.tat_mins = tat_mins
    t.due_at = now + datetime.timedelta(minutes=tat_mins)
    db.commit()
    db.close()
    return tid


def _age_to(tid, pct_used, tat_mins=240):
    db = SessionLocal()
    t = db.query(Ticket).filter(Ticket.id == tid).first()
    now = datetime.datetime.now()
    elapsed = tat_mins * pct_used
    t.created_at = now - datetime.timedelta(minutes=elapsed)
    t.due_at = now + datetime.timedelta(minutes=tat_mins - elapsed)
    db.commit()
    db.close()


def _events_for(client, tid):
    r = client.get(f"/cccapi/ticket/{tid}", headers=MGR)
    assert r.status_code == 200, r.text
    return r.json()["events"]


def _notif_types(client, headers, tid):
    rows = client.get("/cccapi/notifications", headers=headers).json()["rows"]
    return [n["type"] for n in rows if n["ticket_id"] == tid]


def test_no_occupant_at_level_raises_exception_and_cascades_to_next_level(client, hierarchy_server):
    """L2 has neither a named user nor a team in the external hierarchy
    response - the sweep must not get stuck there: it records an Assignment
    Exception and, in the SAME pass, keeps walking up to L3 (which does have
    a real occupant) rather than leaving the ticket stalled at L2 until an
    admin notices and the next threshold happens to be crossed."""
    _HierarchyHandler.response_body = {
        "hierarchy": [
            {"level": "L1", "username": "service"},
            {"level": "L2"},  # no username, no teamId - nobody to notify
            {"level": "L3", "username": "cc_manager"},
            {"level": "L4", "teamId": "CC_MANAGER"},
        ]
    }
    r = client.put("/cccapi/admin/hierarchy/config", json={"mode": "EXTERNAL_API", "url": hierarchy_server}, headers=MGR)
    assert r.status_code == 200, r.text

    tid = _make_ticket(client)
    # L1 already handled by the ticket's own creation-time hierarchy chain
    # only tracks occupancy, not escalation - explicitly fire L1 first so
    # this test isolates the L2 (empty) -> L3 (real) cascade.
    _age_to(tid, 0.35)
    run_sla_sweep_once()
    assert "ESCALATED_L1" in _notif_types(client, SVC, tid)

    _age_to(tid, 0.75)  # past L2 (50%) and L3 (70%)
    run_sla_sweep_once()

    types_cc = _notif_types(client, MGR, tid)
    assert "ESCALATED_L3" in types_cc  # cc_manager is the L3 occupant here

    r = client.get("/cccapi/admin/assignment-exceptions?status=OPEN", headers=MGR)
    assert any(e["ticket_id"] == tid and e["reason"] == "NO_OCCUPANT_AT_LEVEL" for e in r.json())

    detail = client.get(f"/cccapi/ticket/{tid}", headers=MGR).json()["ticket"]
    assert detail["current_level"] == "L3"  # advanced past the empty L2, not stuck there


def test_sweep_called_twice_produces_no_duplicate_escalation_events(client):
    """Idempotency at the ccc_event level, not just notifications - a second
    sweep at the same age must not write a second AUTO_ESCALATED event."""
    tid = _make_ticket(client)
    _age_to(tid, 0.35)
    run_sla_sweep_once()
    run_sla_sweep_once()

    events = _events_for(client, tid)
    auto_escalated = [e for e in events if e["action"] == "AUTO_ESCALATED"]
    assert len(auto_escalated) == 1


def test_each_threshold_advances_current_level_in_order(client):
    tid = _make_ticket(client)
    for pct, expected_level in ((0.35, "L1"), (0.55, "L2"), (0.75, "L3"), (0.95, "L4")):
        _age_to(tid, pct)
        run_sla_sweep_once()
        detail = client.get(f"/cccapi/ticket/{tid}", headers=MGR).json()["ticket"]
        assert detail["current_level"] == expected_level, f"at {pct}: expected {expected_level}, got {detail['current_level']}"
