"""Phase 5 stage 3: the 30/50/70/90/100% L1-L4 escalation ladder that
replaces the old two-tier assignee_warn_pct(50%)/team_manager_warn_pct(80%)
scheme. Each level's escalation notifies whoever app/services/hierarchy.py
already resolved as that level's occupant at ticket-creation time (a named
user via a Routing Rule's lN_username, else a team-wide broadcast) - the
sweep itself no longer knows about "the assignee" as a concept; that was
always a different mechanism (Ticket.assignee, set by acknowledge/assign)
from the L1-L4 hierarchy chain (ccc_ticket_assignment).

Only one level fires per sweep pass once it has a real occupant to notify
(see app/services/sla_sweep.py's _escalate_level) - a ticket that has
skipped past several thresholds between sweeps climbs one level per pass,
so tests that need to reach L2 or beyond call run_sla_sweep_once() the
matching number of times."""
import datetime
from tests.conftest import auth_headers
from app.db.database import SessionLocal
from app.models.ticket import Ticket
from app.services.sla_sweep import run_sla_sweep_once

CT = auth_headers("CALL_TAKER")
SVC = auth_headers("SERVICE")
MGR = auth_headers("CC_MANAGER")


def make_ticket(client, tat_mins=240, category="MACHINE", subcategory_code=None):
    body = {
        "mmu_vehicle": "AP1", "district": "D", "problem": "tiered sla test",
        "category": category, "priority": "P1", "caller_name": "Test Caller", "caller_phone": "9876543210",
    }
    if subcategory_code:
        body["subcategory_code"] = subcategory_code
    r = client.post("/cccapi/ticket", json=body, headers=CT)
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


def age_ticket(tid, pct_used, tat_mins=240):
    """Back-date created_at/due_at so the ticket looks like pct_used of its
    TAT has already elapsed, without waiting in real time."""
    db = SessionLocal()
    t = db.query(Ticket).filter(Ticket.id == tid).first()
    now = datetime.datetime.now()
    elapsed = tat_mins * pct_used
    t.created_at = now - datetime.timedelta(minutes=elapsed)
    t.due_at = now + datetime.timedelta(minutes=tat_mins - elapsed)
    db.commit()
    db.close()


def notif_types_for(client, headers, ticket_id=None):
    r = client.get("/cccapi/notifications", headers=headers)
    rows = r.json()["rows"]
    if ticket_id is not None:
        rows = [n for n in rows if n["ticket_id"] == ticket_id]
    return [n["type"] for n in rows]


def make_reason(client, code, category_code):
    r = client.post("/cccapi/admin/reasons", json={"code": code, "category_code": category_code, "label": code},
                     headers=MGR)
    assert r.status_code == 200, r.text
    return r.json()["code"]


def test_l1_broadcasts_to_team_by_default(client):
    """No Routing Rule names an L1 user for plain MACHINE tickets, so L1's
    occupant is the team itself (unchanged default ladder) - the escalation
    broadcasts to the whole team, same as a new-ticket notification would."""
    tid = make_ticket(client)
    age_ticket(tid, 0.35)  # past L1 (30%), not yet L2 (50%)
    run_sla_sweep_once()
    assert "ESCALATED_L1" in notif_types_for(client, SVC, tid)


def test_l1_notifies_a_named_user_when_a_routing_rule_sets_one(client):
    sub = make_reason(client, "TIERED-SUB-L1", "MACHINE")
    r = client.post("/cccapi/admin/routing-rules", json={
        "code": "TIERED-L1-USER", "category_code": "MACHINE", "subcategory_code": sub, "l1_username": "service",
    }, headers=MGR)
    assert r.status_code == 200, r.text

    tid = make_ticket(client, subcategory_code=sub)
    age_ticket(tid, 0.35)
    run_sla_sweep_once()

    assert "ESCALATED_L1" in notif_types_for(client, SVC, tid)
    other = auth_headers("SERVICE", username="unrelated_service_person")
    assert "ESCALATED_L1" not in notif_types_for(client, other, tid)


def test_l2_fires_on_the_second_pass_once_l1_is_already_handled(client):
    tid = make_ticket(client)
    age_ticket(tid, 0.55)  # past both L1 (30%) and L2 (50%)
    run_sla_sweep_once()  # fires L1
    run_sla_sweep_once()  # L1 already handled -> fires L2

    types = notif_types_for(client, SVC, tid)
    assert "ESCALATED_L1" in types
    assert "ESCALATED_L2" in types
    # CC Manager should NOT be paged yet - only an actual breach reaches them
    cc_types = notif_types_for(client, MGR, tid)
    assert "BREACHED" not in cc_types and "ESCALATED" not in cc_types


def test_breach_reaches_cc_manager_and_auto_escalates(client):
    tid = make_ticket(client)
    age_ticket(tid, 1.1)
    run_sla_sweep_once()

    assert "BREACHED" in notif_types_for(client, MGR, tid)
    r = client.get(f"/cccapi/ticket/{tid}", headers=MGR)
    assert r.json()["ticket"]["escalated"] is True
    assert r.json()["ticket"]["current_level"] == "L4"


def test_sweep_is_idempotent(client):
    tid = make_ticket(client)
    age_ticket(tid, 0.35)
    run_sla_sweep_once()
    run_sla_sweep_once()
    types = notif_types_for(client, SVC, tid)
    assert types.count("ESCALATED_L1") == 1


def test_escalation_pcts_must_be_ascending(client):
    r = client.put("/cccapi/admin/sla",
                    json={"sla": {"escalation_pcts": {"L1": 0.9, "L2": 0.7, "L3": 0.5, "L4": 0.3}}}, headers=MGR)
    assert r.status_code == 400


def test_escalation_pcts_must_have_all_four_levels(client):
    r = client.put("/cccapi/admin/sla", json={"sla": {"escalation_pcts": {"L1": 0.3, "L2": 0.5}}}, headers=MGR)
    assert r.status_code == 400


def test_escalation_pcts_are_admin_configurable(client):
    r = client.put("/cccapi/admin/sla",
                    json={"sla": {"escalation_pcts": {"L1": 0.2, "L2": 0.4, "L3": 0.6, "L4": 0.8}}}, headers=MGR)
    assert r.status_code == 200, r.text
    assert r.json()["sla"]["escalation_pcts"] == {"L1": 0.2, "L2": 0.4, "L3": 0.6, "L4": 0.8}
    # restore the default so later tests in the suite see the documented thresholds
    r = client.put("/cccapi/admin/sla",
                    json={"sla": {"escalation_pcts": {"L1": 0.3, "L2": 0.5, "L3": 0.7, "L4": 0.9}}}, headers=MGR)
    assert r.status_code == 200, r.text
