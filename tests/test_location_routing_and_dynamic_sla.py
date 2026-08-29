"""End-to-end scenario tests tying together three things that are each unit-
tested elsewhere (test_geo_routing.py, test_lt_portal.py, test_tiered_sla.py)
but never proven together in one continuous story:

1. A department ticket raised in one location routes to THAT location's own
   team, and a ticket raised in a different location routes to a DIFFERENT
   team - not just "zone-routing works for some fixed zone" but genuinely
   location-dependent.
2. An LT's ticket routes to the CDA team of the LT's OWN profile location -
   proven with a second, independently-created LT/location pair (distinct
   from conftest's single fixed LT_CDA_TEAM), so the test can't pass just
   because there happens to be only one CDA team configured.
3. A single ticket walked through the real tiered SLA timeline (50% ->
   assignee warning, 80% -> team-manager warning, 100%+ -> breach + auto-
   escalation to the CC Manager) via repeated sweeps against progressively
   aged timestamps, confirming the tiers fire in the right order, at the
   right time, without re-firing or skipping."""
import datetime
from tests.conftest import auth_headers, LT_CATEGORY, LT_REASON_CODES
from app.db.database import SessionLocal
from app.models.ticket import Ticket
from app.models.user import User
from app.services.sla_sweep import run_sla_sweep_once

MGR = auth_headers("CC_MANAGER")
CT = auth_headers("CALL_TAKER")
SVC = auth_headers("SERVICE")


def _make_location(client, tag, team_code):
    """One self-contained District -> Zone(->team_code) -> Mandal chain, i.e.
    a 'location' that zone-routing can dispatch to team_code."""
    d = client.post("/cccapi/admin/districts", json={"name": "Dist-" + tag}, headers=MGR)
    assert d.status_code == 200, d.text
    z = client.post("/cccapi/admin/zones", json={"name": "Zone-" + tag, "team_code": team_code}, headers=MGR)
    assert z.status_code == 200, z.text
    m = client.post("/cccapi/admin/mandals", json={"name": "Mandal-" + tag, "district_id": d.json()["id"], "zone_id": z.json()["id"]}, headers=MGR)
    assert m.status_code == 200, m.text
    return {"district_id": d.json()["id"], "zone_id": z.json()["id"], "mandal_id": m.json()["id"]}


def test_ticket_routes_to_the_team_owning_its_own_location(client):
    """Two different locations, same zone-routed category: each ticket must
    land on ITS OWN location's team, proving routing is location-dependent
    rather than a single hardcoded destination."""
    loc_a = _make_location(client, "RouteA", "TECHNICAL")
    loc_b = _make_location(client, "RouteB", "NETWORK")

    client.put("/cccapi/admin/categories/MACHINE", json={"route_by_zone": True}, headers=MGR)
    try:
        ra = client.post("/cccapi/ticket", json={
            "mmu_vehicle": "AP-SITE-A", "district": "D", "problem": "machine broke at site A",
            "category": "MACHINE", "priority": "P2", "mandal_id": loc_a["mandal_id"],
            "caller_name": "Caller A", "caller_phone": "9876543210",
        }, headers=CT)
        rb = client.post("/cccapi/ticket", json={
            "mmu_vehicle": "AP-SITE-B", "district": "D", "problem": "machine broke at site B",
            "category": "MACHINE", "priority": "P2", "mandal_id": loc_b["mandal_id"],
            "caller_name": "Caller B", "caller_phone": "9876543211",
        }, headers=CT)
        assert ra.status_code == 200, ra.text
        assert rb.status_code == 200, rb.text
        assert ra.json()["team"] == "TECHNICAL"  # site A's own team
        assert rb.json()["team"] == "NETWORK"    # site B's own team, NOT site A's

        # Confirm the snapshotted geography on each ticket also matches its
        # own location, not a mix-up between the two.
        db = SessionLocal()
        ta = db.query(Ticket).filter(Ticket.id == ra.json()["id"]).first()
        tb = db.query(Ticket).filter(Ticket.id == rb.json()["id"]).first()
        assert ta.zone_id == loc_a["zone_id"] and ta.mandal_id == loc_a["mandal_id"]
        assert tb.zone_id == loc_b["zone_id"] and tb.mandal_id == loc_b["mandal_id"]
        db.close()
    finally:
        client.put("/cccapi/admin/categories/MACHINE", json={"route_by_zone": False}, headers=MGR)


def test_lt_ticket_routes_to_the_cda_of_the_lts_own_location(client):
    """A second, independently-created LT profile in a DIFFERENT location must
    route to THAT location's CDA team - distinct from conftest's fixed
    LT_CDA_TEAM/LT_USERNAME pairing used by every other LT test - proving the
    routing follows the LT's own profile location, not a single hardcoded
    team that happens to be the only one configured."""
    loc = _make_location(client, "CDA2", "APPLICATION")

    create = client.post("/cccapi/admin/users", json={
        "username": "lt_site2", "name": "Lab Technician Site 2", "role": "LT",
        "password": "testpass123", "district_id": loc["district_id"], "mandal_id": loc["mandal_id"],
    }, headers=MGR)
    assert create.status_code == 200, create.text

    lt2 = auth_headers("LT", username="lt_site2")
    r = client.post("/cccapi/lt/tickets", data={
        "category": LT_CATEGORY, "reason_codes": ",".join(LT_REASON_CODES),
        "priority": "P1", "problem": "Analyzer down at site 2",
    }, headers=lt2)
    assert r.status_code == 200, r.text
    assert r.json()["team"] == "APPLICATION"  # site 2's own CDA-equivalent team

    db = SessionLocal()
    t = db.query(Ticket).filter(Ticket.id == r.json()["id"]).first()
    assert t.district_id == loc["district_id"]
    assert t.mandal_id == loc["mandal_id"]
    assert t.zone_id == loc["zone_id"]
    db.close()


def _make_ticket_for_sla_walk(client, tat_mins=240):
    r = client.post("/cccapi/ticket", json={
        "mmu_vehicle": "AP-SLA", "district": "D", "problem": "dynamic sla walk-through",
        "category": "MACHINE", "priority": "P1", "caller_name": "Test Caller", "caller_phone": "9876543210",
    }, headers=CT)
    assert r.status_code == 200, r.text
    tid = r.json()["id"]
    db = SessionLocal()
    t = db.query(Ticket).filter(Ticket.id == tid).first()
    t.tat_mins = tat_mins
    t.due_at = datetime.datetime.now() + datetime.timedelta(minutes=tat_mins)
    db.commit()
    db.close()
    return tid


def _age_to(tid, pct_used, tat_mins=240):
    """Back-date created_at/due_at so the ticket looks like pct_used of its
    TAT has elapsed, without needing to wait in real time."""
    db = SessionLocal()
    t = db.query(Ticket).filter(Ticket.id == tid).first()
    now = datetime.datetime.now()
    elapsed = tat_mins * pct_used
    t.created_at = now - datetime.timedelta(minutes=elapsed)
    t.due_at = now + datetime.timedelta(minutes=tat_mins - elapsed)
    db.commit()
    db.close()


def _notif_types(client, headers, ticket_id):
    rows = client.get("/cccapi/notifications", headers=headers).json()["rows"]
    return [n["type"] for n in rows if n["ticket_id"] == ticket_id]


def test_dynamic_sla_tiers_fire_in_order_without_skipping_or_repeating(client):
    """One ticket, walked forward through its whole TAT timeline with repeated
    sweeps - confirms the tiers activate progressively (nothing fires early),
    each fires exactly once (no duplicate warnings on later sweeps), and the
    final breach correctly reaches the CC Manager and auto-escalates."""
    db = SessionLocal()
    db.query(User).filter(User.username == "service").update({"is_team_manager": True})
    db.commit()
    db.close()
    try:
        tid = _make_ticket_for_sla_walk(client)
        client.post("/cccapi/ticket/action", json={"id": tid, "action": "acknowledge"}, headers=SVC)  # sets assignee

        # --- Well within TAT: nothing should have fired yet ---
        _age_to(tid, 0.30, tat_mins=240)
        run_sla_sweep_once()
        types = _notif_types(client, SVC, tid)
        assert "TAT_ASSIGNEE_WARN" not in types
        assert "TAT_TEAM_MANAGER_WARN" not in types
        detail = client.get(f"/cccapi/ticket/{tid}", headers=MGR).json()["ticket"]
        assert detail["escalated"] is False

        # --- Past 50%: assignee warned, manager/CC still silent ---
        _age_to(tid, 0.55, tat_mins=240)
        run_sla_sweep_once()
        types = _notif_types(client, SVC, tid)
        assert types.count("TAT_ASSIGNEE_WARN") == 1
        assert "TAT_TEAM_MANAGER_WARN" not in types
        assert "BREACHED" not in _notif_types(client, MGR, tid)

        # --- Sweeping again at the SAME age must not re-fire the same tier ---
        run_sla_sweep_once()
        assert _notif_types(client, SVC, tid).count("TAT_ASSIGNEE_WARN") == 1

        # --- Past 80%: team manager warned too, assignee warn not duplicated ---
        _age_to(tid, 0.85, tat_mins=240)
        run_sla_sweep_once()
        types = _notif_types(client, SVC, tid)
        assert types.count("TAT_ASSIGNEE_WARN") == 1
        assert types.count("TAT_TEAM_MANAGER_WARN") == 1
        assert "BREACHED" not in _notif_types(client, MGR, tid)
        detail = client.get(f"/cccapi/ticket/{tid}", headers=MGR).json()["ticket"]
        assert detail["escalated"] is False

        # --- Past 100%: breach reaches the CC Manager and auto-escalates ---
        _age_to(tid, 1.15, tat_mins=240)
        run_sla_sweep_once()
        types_after_breach = _notif_types(client, MGR, tid)
        # CC_MANAGER's feed sees everything unfiltered (crud_notification.
        # get_notifications), so a breach produces two BREACHED rows - one
        # broadcast to the team, one addressed to CC_MANAGER - both created
        # in the same guarded block the first time the tier is crossed.
        breached_count = types_after_breach.count("BREACHED")
        assert breached_count >= 1
        assert "ESCALATED" in types_after_breach
        detail = client.get(f"/cccapi/ticket/{tid}", headers=MGR).json()["ticket"]
        assert detail["escalated"] is True
        assert detail["tat_state"] == "BREACHED"

        # --- Breach sweep is idempotent: repeat sweeps must not add more ---
        run_sla_sweep_once()
        run_sla_sweep_once()
        types_after_extra_sweeps = _notif_types(client, MGR, tid)
        assert types_after_extra_sweeps.count("BREACHED") == breached_count
        assert types_after_extra_sweeps.count("ESCALATED") == 1
    finally:
        db = SessionLocal()
        db.query(User).filter(User.username == "service").update({"is_team_manager": False})
        db.commit()
        db.close()
