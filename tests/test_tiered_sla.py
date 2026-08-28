import datetime
from tests.conftest import auth_headers
from app.db.database import SessionLocal
from app.models.ticket import Ticket
from app.models.user import User
from app.services.sla_sweep import run_sla_sweep_once

CT = auth_headers("CALL_TAKER")
SVC = auth_headers("SERVICE")
MGR = auth_headers("CC_MANAGER")


def make_ticket(client, tat_mins=240):
    r = client.post("/cccapi/ticket", json={
        "mmu_vehicle": "AP1", "district": "D", "problem": "tiered sla test",
        "category": "MACHINE", "priority": "P1",
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


def test_50pct_warns_the_assignee_only(client):
    tid = make_ticket(client)
    client.post("/cccapi/ticket/action", json={"id": tid, "action": "acknowledge"}, headers=SVC)  # sets assignee
    age_ticket(tid, 0.55)
    run_sla_sweep_once()

    assert "TAT_ASSIGNEE_WARN" in notif_types_for(client, SVC, tid)
    other = auth_headers("SERVICE", username="unrelated_service_person")
    assert "TAT_ASSIGNEE_WARN" not in notif_types_for(client, other, tid)


def test_50pct_broadcasts_to_team_when_unassigned(client):
    tid = make_ticket(client)  # never acknowledged - no assignee
    age_ticket(tid, 0.55)
    run_sla_sweep_once()
    assert "TAT_ASSIGNEE_WARN" in notif_types_for(client, SVC, tid)


def test_80pct_warns_team_manager_not_cc_manager(client):
    db = SessionLocal()
    db.query(User).filter(User.username == "service").update({"is_team_manager": True})
    db.commit()
    db.close()
    try:
        tid = make_ticket(client)
        age_ticket(tid, 0.85)
        run_sla_sweep_once()

        assert "TAT_TEAM_MANAGER_WARN" in notif_types_for(client, SVC, tid)
        # CC Manager should NOT be paged yet - only an actual breach reaches them
        cc_types = notif_types_for(client, MGR, tid)
        assert "BREACHED" not in cc_types and "ESCALATED" not in cc_types
    finally:
        db = SessionLocal()
        db.query(User).filter(User.username == "service").update({"is_team_manager": False})
        db.commit()
        db.close()


def test_breach_reaches_cc_manager_and_auto_escalates(client):
    tid = make_ticket(client)
    age_ticket(tid, 1.1)
    run_sla_sweep_once()

    assert "BREACHED" in notif_types_for(client, MGR, tid)
    r = client.get(f"/cccapi/ticket/{tid}", headers=MGR)
    assert r.json()["ticket"]["escalated"] is True


def test_sweep_is_idempotent(client):
    tid = make_ticket(client)
    age_ticket(tid, 0.55)
    run_sla_sweep_once()
    run_sla_sweep_once()
    types = notif_types_for(client, SVC, tid)
    assert types.count("TAT_ASSIGNEE_WARN") == 1


def test_assignee_warn_pct_must_be_below_manager_pct(client):
    r = client.put("/cccapi/admin/sla", json={"sla": {"assignee_warn_pct": 0.9, "team_manager_warn_pct": 0.5}}, headers=MGR)
    assert r.status_code == 400
