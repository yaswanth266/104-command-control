import datetime
from tests.conftest import auth_headers
from app.db.database import SessionLocal
from app.models.ticket import Ticket
from app.services.sla_sweep import run_sla_sweep_once

CT = auth_headers("CALL_TAKER")
SVC = auth_headers("SERVICE")
MGR = auth_headers("CC_MANAGER")


def make_ticket(client, priority="P2", category="MACHINE", problem="workflow test", vip=False):
    r = client.post("/cccapi/ticket", json={
        "mmu_vehicle": "AP39TEST1", "district": "Test District", "problem": problem,
        "category": category, "priority": priority, "vip": vip,
        "caller_name": "Test Caller", "caller_phone": "9876543210",
    }, headers=CT)
    assert r.status_code == 200, r.text
    return r.json()


def db_get(tid):
    db = SessionLocal()
    t = db.query(Ticket).filter(Ticket.id == tid).first()
    db.close()
    return t


def db_set(tid, **kwargs):
    db = SessionLocal()
    db.query(Ticket).filter(Ticket.id == tid).update(kwargs)
    db.commit()
    db.close()


# ---------- SLA-pausing PENDING ----------

def test_pending_pauses_the_sla_clock(client):
    body = make_ticket(client)
    tid = body["id"]
    client.post("/cccapi/ticket/action", json={"id": tid, "action": "acknowledge"}, headers=SVC)
    client.post("/cccapi/ticket/action", json={"id": tid, "action": "start"}, headers=SVC)

    before = db_get(tid)
    original_due = before.due_at

    r = client.post("/cccapi/ticket/action", json={"id": tid, "action": "pending", "pending_reason": "waiting on hospital callback"}, headers=SVC)
    assert r.status_code == 200
    paused_ticket = db_get(tid)
    assert paused_ticket.pending_since is not None

    # Simulate 90 minutes having elapsed while PENDING
    simulated_start = datetime.datetime.now() - datetime.timedelta(minutes=90)
    db_set(tid, pending_since=simulated_start)

    r = client.post("/cccapi/ticket/action", json={"id": tid, "action": "start"}, headers=SVC)
    assert r.status_code == 200

    after = db_get(tid)
    assert after.pending_since is None
    assert 85 <= after.paused_minutes <= 95
    delta_minutes = (after.due_at - original_due).total_seconds() / 60.0
    assert 85 <= delta_minutes <= 95


def test_pending_reason_update_does_not_reset_pause_clock(client):
    body = make_ticket(client)
    tid = body["id"]
    client.post("/cccapi/ticket/action", json={"id": tid, "action": "acknowledge"}, headers=SVC)
    client.post("/cccapi/ticket/action", json={"id": tid, "action": "start"}, headers=SVC)
    client.post("/cccapi/ticket/action", json={"id": tid, "action": "pending", "pending_reason": "waiting"}, headers=SVC)

    simulated_start = datetime.datetime.now() - datetime.timedelta(minutes=30)
    db_set(tid, pending_since=simulated_start)

    # Updating the pending reason again should NOT push pending_since forward
    client.post("/cccapi/ticket/action", json={"id": tid, "action": "pending", "pending_reason": "still waiting"}, headers=SVC)
    mid = db_get(tid)
    assert abs((mid.pending_since - simulated_start).total_seconds()) < 5

    r = client.post("/cccapi/ticket/action", json={"id": tid, "action": "resolve", "resolution": "fixed"}, headers=SVC)
    assert r.status_code == 200
    after = db_get(tid)
    assert 25 <= after.paused_minutes <= 35


def test_resume_work_moves_pending_ticket_back_to_in_progress(client):
    """The 'Resume work' button (renderT() in app.js) calls the same 'start'
    action - this confirms the backend transition it relies on."""
    body = make_ticket(client)
    tid = body["id"]
    client.post("/cccapi/ticket/action", json={"id": tid, "action": "acknowledge"}, headers=SVC)
    client.post("/cccapi/ticket/action", json={"id": tid, "action": "pending", "pending_reason": "waiting"}, headers=SVC)
    assert db_get(tid).status == "PENDING"

    r = client.post("/cccapi/ticket/action", json={"id": tid, "action": "start"}, headers=SVC)
    assert r.status_code == 200, r.text
    assert db_get(tid).status == "IN_PROGRESS"


def test_stuck_pending_auto_escalates_to_cc_manager(client):
    body = make_ticket(client)
    tid = body["id"]
    client.post("/cccapi/ticket/action", json={"id": tid, "action": "acknowledge"}, headers=SVC)
    client.post("/cccapi/ticket/action", json={"id": tid, "action": "pending", "pending_reason": "waiting"}, headers=SVC)
    db_set(tid, pending_since=datetime.datetime.now() - datetime.timedelta(hours=25))

    run_sla_sweep_once()

    t = db_get(tid)
    assert t.escalated is True
    assert t.escalated_to == "CC_MANAGER"
    assert "Pending" in t.escalation_note


def test_pending_not_yet_stuck_is_not_escalated(client):
    body = make_ticket(client)
    tid = body["id"]
    client.post("/cccapi/ticket/action", json={"id": tid, "action": "acknowledge"}, headers=SVC)
    client.post("/cccapi/ticket/action", json={"id": tid, "action": "pending", "pending_reason": "waiting"}, headers=SVC)
    db_set(tid, pending_since=datetime.datetime.now() - datetime.timedelta(hours=2))

    run_sla_sweep_once()

    assert db_get(tid).escalated is False


def test_repriority_preserves_accumulated_pause(client):
    body = make_ticket(client, priority="P3")
    tid = body["id"]
    client.post("/cccapi/ticket/action", json={"id": tid, "action": "acknowledge"}, headers=SVC)
    client.post("/cccapi/ticket/action", json={"id": tid, "action": "pending", "pending_reason": "waiting"}, headers=SVC)
    db_set(tid, pending_since=datetime.datetime.now() - datetime.timedelta(minutes=60))
    client.post("/cccapi/ticket/action", json={"id": tid, "action": "start"}, headers=SVC)
    paused = db_get(tid).paused_minutes
    assert paused >= 55

    r = client.post("/cccapi/ticket/action", json={"id": tid, "action": "repriority", "priority": "P1"}, headers=MGR)
    assert r.status_code == 200
    t = db_get(tid)
    expected_due = t.created_at + datetime.timedelta(minutes=240 + paused)
    assert abs((t.due_at - expected_due).total_seconds()) < 5


# ---------- time-limited reopen ----------

def _close_ticket(client, tid):
    for action, extra in [("acknowledge", {}), ("resolve", {"resolution": "x"}),
                           ("confirm", {"confirmed_by": "x"}), ("close", {})]:
        r = client.post("/cccapi/ticket/action", json={"id": tid, "action": action, **extra}, headers=SVC)
        assert r.status_code == 200, (action, r.text)


def test_reopen_blocked_after_window_expires(client):
    body = make_ticket(client)
    tid = body["id"]
    _close_ticket(client, tid)
    db_set(tid, closed_at=datetime.datetime.now() - datetime.timedelta(hours=30))

    r = client.post("/cccapi/ticket/action", json={"id": tid, "action": "reopen", "note": "recurred"}, headers=MGR)
    assert r.status_code == 409


def test_reopen_allowed_within_window(client):
    body = make_ticket(client)
    tid = body["id"]
    _close_ticket(client, tid)
    db_set(tid, closed_at=datetime.datetime.now() - datetime.timedelta(hours=1))

    r = client.post("/cccapi/ticket/action", json={"id": tid, "action": "reopen", "note": "recurred"}, headers=MGR)
    assert r.status_code == 200


def test_reopen_window_is_admin_configurable(client):
    r = client.put("/cccapi/admin/sla", json={"sla": {"reopen_window_hours": 1}}, headers=MGR)
    assert r.status_code == 200
    assert r.json()["sla"]["reopen_window_hours"] == 1

    body = make_ticket(client)
    tid = body["id"]
    _close_ticket(client, tid)
    db_set(tid, closed_at=datetime.datetime.now() - datetime.timedelta(hours=2))
    r = client.post("/cccapi/ticket/action", json={"id": tid, "action": "reopen", "note": "recurred"}, headers=MGR)
    assert r.status_code == 409

    # restore default for other tests
    client.put("/cccapi/admin/sla", json={"sla": {"reopen_window_hours": 24}}, headers=MGR)


def test_reopen_window_rejects_non_positive(client):
    r = client.put("/cccapi/admin/sla", json={"sla": {"reopen_window_hours": 0}}, headers=MGR)
    assert r.status_code == 400


# ---------- VIP / keyword auto-escalation ----------

def test_vip_flag_forces_p1(client):
    body = make_ticket(client, priority="P4", vip=True)
    assert body["priority"] == "P1"
    assert body["vip"] is True


def test_keyword_match_forces_p1(client):
    body = make_ticket(client, priority="P4", problem="The CEO's office reported the analyzer is down")
    assert body["priority"] == "P1"
    assert body["vip"] is True


def test_no_vip_no_keyword_keeps_submitted_priority(client):
    body = make_ticket(client, priority="P3", problem="routine calibration issue")
    assert body["priority"] == "P3"
    assert body["vip"] is False


def test_admin_can_manage_vip_keywords(client):
    r = client.put("/cccapi/admin/sla", json={"vip_keywords": ["magistrate"]}, headers=MGR)
    assert r.status_code == 200
    assert r.json()["vip_keywords"] == ["magistrate"]

    body = make_ticket(client, priority="P4", problem="the district magistrate called about this")
    assert body["priority"] == "P1"

    body2 = make_ticket(client, priority="P4", problem="ceo mentioned but keyword list no longer includes it")
    assert body2["priority"] == "P4"

    # restore defaults for other tests
    client.put("/cccapi/admin/sla", json={"vip_keywords": ["ceo", "collector", "director", "minister", "total shutdown"]}, headers=MGR)
