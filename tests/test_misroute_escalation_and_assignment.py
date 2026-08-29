"""Two real-world correction paths for a ticket that landed on the wrong
team, both starting from the same setup: a ticket is filed under a category
that ignores its own location's zone-routing (a plain human mis-classification
- e.g. the call taker picked "Machine issue", which always defaults to
SERVICE, even though this particular Mandal's Zone is dedicated to NETWORK),
so it lands on SERVICE by mistake.

Path A: SERVICE realizes it isn't theirs and escalates to the Global Team
Executive (CC Manager); the CC Manager, using the ticket's own (unchanged)
location, re-routes it to the team that location is actually mandated to -
the Zone's team, NETWORK.

Path B: instead of escalating, SERVICE's own Team Executive decides the
ticket genuinely IS a SERVICE issue and assigns it to a named engineer on
their team - no re-route happens, and that engineer ends up owning it."""
from starlette.testclient import TestClient
from tests.conftest import auth_headers
from app.db.database import SessionLocal
from app.models.user import User
from app.models.ticket import Ticket

MGR = auth_headers("CC_MANAGER")
CT = auth_headers("CALL_TAKER")
SVC = auth_headers("SERVICE")  # plain SERVICE member, not the Team Executive


def _make_location(client, tag, team_code):
    d = client.post("/cccapi/admin/districts", json={"name": "Dist-" + tag}, headers=MGR)
    assert d.status_code == 200, d.text
    z = client.post("/cccapi/admin/zones", json={"name": "Zone-" + tag, "team_code": team_code}, headers=MGR)
    assert z.status_code == 200, z.text
    m = client.post("/cccapi/admin/mandals", json={"name": "Mandal-" + tag, "district_id": d.json()["id"], "zone_id": z.json()["id"]}, headers=MGR)
    assert m.status_code == 200, m.text
    return {"district_id": d.json()["id"], "zone_id": z.json()["id"], "mandal_id": m.json()["id"]}


def _set_team_manager(username, is_manager=True):
    db = SessionLocal()
    db.query(User).filter(User.username == username).update({"is_team_manager": is_manager})
    db.commit()
    db.close()


def _login_headers(username, password="testpass123"):
    # is_team_manager is baked into the JWT at login (see app/api/routers/auth.py),
    # not re-checked per request - auth_headers() mints a token directly and
    # can't carry that claim, so any test needing "is_team_manager" permissions
    # must actually log in after setting the flag, same as test_dispatch.py does.
    import main
    with TestClient(main.app) as c:
        r = c.post("/cccapi/auth", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


def _raise_misrouted_ticket(client, mandal_id):
    """category=MACHINE is not zone-routed, so it defaults to SERVICE
    regardless of the Mandal's own Zone - a plain, realistic mis-route that
    needs no direct DB tampering to set up."""
    r = client.post("/cccapi/ticket", json={
        "mmu_vehicle": "AP-MISROUTE", "district": "D", "problem": "network drop reported as a machine issue",
        "category": "MACHINE", "priority": "P2", "mandal_id": mandal_id,
        "caller_name": "Test Caller", "caller_phone": "9876543210",
    }, headers=CT)
    assert r.status_code == 200, r.text
    assert r.json()["team"] == "SERVICE"  # confirms the mistake actually happened
    return r.json()["id"]


def test_misrouted_ticket_escalated_then_rerouted_by_cc_manager_to_the_correct_location_team(client):
    loc = _make_location(client, "Correction", "NETWORK")
    tid = _raise_misrouted_ticket(client, loc["mandal_id"])

    # SERVICE (the wrong team) realizes the mistake and escalates to the CC Manager.
    esc = client.post("/cccapi/ticket/action", json={"id": tid, "action": "escalate", "note": "This isn't a Service issue"}, headers=SVC)
    assert esc.status_code == 200, esc.text
    escalated_state = client.get(f"/cccapi/ticket/{tid}", headers=MGR).json()["ticket"]
    assert escalated_state["escalated"] is True
    assert escalated_state["escalated_to"] == "CC_MANAGER"
    assert escalated_state["team"] == "SERVICE"  # escalation alone does not move the ticket

    # A plain SERVICE member (not CC Manager, not this team's Executive) may
    # NOT re-route it themselves - only the CC Manager/Call Taker can.
    forbidden = client.post("/cccapi/ticket/action", json={"id": tid, "action": "reassign", "team": "NETWORK"}, headers=SVC)
    assert forbidden.status_code == 403

    # The CC Manager reads the ticket's own (unchanged) location and re-routes
    # it to the team that location is actually mandated to - NETWORK, the
    # Zone's team - not anything picked freehand.
    db = SessionLocal()
    ticket_row = db.query(Ticket).filter(Ticket.id == tid).first()
    assert ticket_row.mandal_id == loc["mandal_id"]  # location was captured correctly all along
    assert ticket_row.zone_id is None  # MACHINE never consulted the zone in the first place
    db.close()

    reroute = client.post("/cccapi/ticket/action",
                           json={"id": tid, "action": "reassign", "team": "NETWORK", "note": "This Mandal's Zone is dedicated to Network"},
                           headers=MGR)
    assert reroute.status_code == 200, reroute.text

    corrected = client.get(f"/cccapi/ticket/{tid}", headers=MGR).json()["ticket"]
    assert corrected["team"] == "NETWORK"
    assert corrected["status"] == "ASSIGNED"       # reset for the new team to pick up fresh
    assert corrected["assignee"] is None           # any old assignee is cleared, nobody carries over
    assert corrected["mandal_id"] == loc["mandal_id"]  # location itself never changes, only the team
    assert corrected["escalated"] is True          # the earlier escalation stays on the audit trail

    # NETWORK - the correct, location-mandated team - can now genuinely work it.
    net_headers = auth_headers("NETWORK")
    ack = client.post("/cccapi/ticket/action", json={"id": tid, "action": "acknowledge"}, headers=net_headers)
    assert ack.status_code == 200, ack.text
    # SERVICE, no longer the owning team, is locked out again.
    locked_out = client.post("/cccapi/ticket/action", json={"id": tid, "action": "acknowledge"}, headers=SVC)
    assert locked_out.status_code == 403


def test_misrouted_ticket_kept_by_its_team_executive_and_assigned_to_a_member(client):
    loc = _make_location(client, "KeepIt", "NETWORK")
    tid = _raise_misrouted_ticket(client, loc["mandal_id"])

    # A second SERVICE-team engineer to hand the ticket to.
    created = client.post("/cccapi/admin/users", json={
        "username": "service_member2", "name": "Service Engineer Two", "role": "SERVICE", "password": "testpass123",
    }, headers=MGR)
    assert created.status_code == 200, created.text

    _set_team_manager("service", True)
    try:
        svc_exec_headers = _login_headers("service")

        # The Team Executive looks at it and decides it genuinely IS theirs -
        # no escalation, just a direct assignment to a named engineer.
        assign = client.post("/cccapi/ticket/action",
                              json={"id": tid, "action": "assign", "assignee": "service_member2"},
                              headers=svc_exec_headers)
        assert assign.status_code == 200, assign.text

        kept = client.get(f"/cccapi/ticket/{tid}", headers=MGR).json()["ticket"]
        assert kept["team"] == "SERVICE"          # no re-route - stayed exactly where it was
        assert kept["assignee"] == "service_member2"
        assert kept["escalated"] is False          # never escalated down this path

        # The assigned engineer sees a personal notification and can genuinely
        # act on the ticket - they now "have" it.
        member_headers = auth_headers("SERVICE", username="service_member2")
        notifs = client.get("/cccapi/notifications", headers=member_headers).json()["rows"]
        assert any(n["type"] == "ASSIGNED" and n["ticket_id"] == tid for n in notifs)

        ack = client.post("/cccapi/ticket/action", json={"id": tid, "action": "acknowledge"}, headers=member_headers)
        assert ack.status_code == 200, ack.text
        acked = client.get(f"/cccapi/ticket/{tid}", headers=MGR).json()["ticket"]
        assert acked["status"] == "ACKNOWLEDGED"
        assert acked["assignee"] == "service_member2"  # acknowledging keeps the same assignee

        # A bystander on the same team, who wasn't assigned, gets no personal
        # ASSIGNED notification of their own for this ticket.
        bystander_headers = auth_headers("SERVICE", username="service_bystander")
        bystander_notifs = client.get("/cccapi/notifications", headers=bystander_headers).json()["rows"]
        assert not any(n["type"] == "ASSIGNED" and n["ticket_id"] == tid for n in bystander_notifs)
    finally:
        _set_team_manager("service", False)
