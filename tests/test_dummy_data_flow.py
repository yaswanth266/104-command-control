"""End-to-end data-flow verification using the client's real escalation
matrix spreadsheet as dummy data (Category / Sub-Category / L1-L4 / Priority
/ Resolution SLA), plus dummy data for Phase 5 stage 2's new master-data
cache tables (ccc_ext_vehicle / ccc_ext_employee / ccc_emp_hierarchy),
synced through the real sync job against a stub roster server (not
hand-inserted) so this also exercises that pipeline end-to-end.

Covers, from the spreadsheet, every distinct L1-L4 pattern it contains:
  - OE / DM / Helpdesk / Development      (Login & Access, most rows)
  - OE / DM / RM / SPH                    (Role Mapping, Vehicle Mapping)
  - OE / Admin / Development / Development (Duplicate Employee - a team
    repeated at two levels)
  - Helpdesk / Development / PM IT / Admin (Patient Health Card, EHR/Clinical)
  - Helpdesk / LIS Support / Development / PM IT (Laboratory/LIS)
plus the edge cases: a Sub-Category overriding its Category's usual pattern,
a role that resolves to a real person with no local account (unmapped), a
caller with no synced hierarchy data at all, and SLA resolution minutes
varying correctly by Sub-Category+Priority (4 Hrs / 2 Hrs / 1 Day / 8 Hrs)."""
import json
import threading
import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from tests.conftest import auth_headers
from app.db.database import SessionLocal
from app.models.emp_hierarchy import EmpHierarchy
from app.models.ticket import Ticket
from app.services.sla_sweep import run_sla_sweep_once

MGR = auth_headers("CC_MANAGER")
CT = auth_headers("CALL_TAKER")

_TEAMS = ["HELPDESK", "DEVELOPMENT", "PM_IT", "ADMIN", "LIS_SUPPORT"]

_CATEGORIES = {
    "LOGIN_ACCESS": ("Login & Access", "HELPDESK"),
    "USER_EMP_MGMT": ("User & Employee Management", "HELPDESK"),
    "PATIENT_REG": ("Patient Registration", "HELPDESK"),
    "PATIENT_HEALTH_CARD": ("Patient Health Card", "HELPDESK"),
    "EHR_CLINICAL": ("EHR / Clinical", "HELPDESK"),
    "LAB_LIS": ("Laboratory / LIS", "LIS_SUPPORT"),
}

# code -> (category_code, label, priority, resolution_mins, L1, L2, L3, L4)
# L-values: a dict with one of role=/team=/username= - mirrors a routing
# rule's lN_role/lN_team_code/lN_username columns directly.
_SUBCATEGORIES = {
    "LOGIN_FAILURE": ("LOGIN_ACCESS", "Login Failure", "P2", 240,
                       {"role": "OE"}, {"role": "DM"}, {"team": "HELPDESK"}, {"team": "DEVELOPMENT"}),
    "FORGOT_PASSWORD": ("LOGIN_ACCESS", "Forgot Password", "P3", 120,
                         {"role": "OE"}, {"role": "DM"}, {"team": "HELPDESK"}, {"team": "DEVELOPMENT"}),
    "ACCOUNT_LOCKED": ("LOGIN_ACCESS", "Account Locked", "P3", 120,
                        {"role": "OE"}, {"role": "DM"}, {"team": "HELPDESK"}, {"team": "DEVELOPMENT"}),
    "EMPLOYEE_MAPPING": ("USER_EMP_MGMT", "Employee Mapping", "P3", 1440,
                          {"role": "OE"}, {"role": "DM"}, {"team": "HELPDESK"}, {"team": "DEVELOPMENT"}),
    "ROLE_MAPPING": ("USER_EMP_MGMT", "Role Mapping", "P3", 1440,
                      {"role": "OE"}, {"role": "DM"}, {"role": "RM"}, {"role": "SPH"}),
    "VEHICLE_MAPPING": ("USER_EMP_MGMT", "Vehicle Mapping", "P2", 480,
                         {"role": "OE"}, {"role": "DM"}, {"role": "RM"}, {"role": "SPH"}),
    "DUPLICATE_EMPLOYEE": ("USER_EMP_MGMT", "Duplicate Employee", "P3", 1440,
                            {"role": "OE"}, {"team": "ADMIN"}, {"team": "DEVELOPMENT"}, {"team": "DEVELOPMENT"}),
    "NEW_REGISTRATION": ("PATIENT_REG", "New Registration", "P2", 480,
                          {"role": "OE"}, {"role": "DM"}, {"team": "HELPDESK"}, {"team": "DEVELOPMENT"}),
    "CARD_GENERATION": ("PATIENT_HEALTH_CARD", "Card Generation", "P3", 1440,
                         {"team": "HELPDESK"}, {"team": "DEVELOPMENT"}, {"team": "PM_IT"}, {"team": "ADMIN"}),
    "PATIENT_HISTORY": ("EHR_CLINICAL", "Patient History", "P2", 480,
                         {"team": "HELPDESK"}, {"team": "DEVELOPMENT"}, {"team": "PM_IT"}, {"team": "ADMIN"}),
    "SAMPLE_COLLECTION": ("LAB_LIS", "Sample Collection", "P2", 480,
                           {"team": "HELPDESK"}, {"team": "LIS_SUPPORT"}, {"team": "DEVELOPMENT"}, {"team": "PM_IT"}),
}


class _RosterHandler(BaseHTTPRequestHandler):
    bodies = {"vehicles": [], "employees": [], "hierarchy": []}

    def do_GET(self):
        key = self.path.strip("/").rsplit("/", 1)[-1]
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(_RosterHandler.bodies.get(key, [])).encode("utf-8"))

    def log_message(self, *a):
        pass


@pytest.fixture(scope="module")
def roster_server():
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


@pytest.fixture(scope="module", autouse=True)
def _seed_matrix(client):
    """Seeds the whole spreadsheet-derived matrix once for this file: Teams,
    Categories, Sub-Categories, SLA Policies, Routing Rules, local
    role-holder accounts, and the master-data cache (synced through the real
    job against a stub roster server, not hand-inserted)."""
    for code in _TEAMS:
        r = client.post("/cccapi/admin/teams", json={"code": code, "name": code.replace("_", " ").title()}, headers=MGR)
        assert r.status_code in (200, 409), r.text

    for code, (label, team_code) in _CATEGORIES.items():
        r = client.post("/cccapi/admin/categories", json={"code": code, "label": label, "team_code": team_code}, headers=MGR)
        assert r.status_code in (200, 409), r.text

    for code, (cat, label, *_rest) in _SUBCATEGORIES.items():
        r = client.post("/cccapi/admin/reasons", json={"code": code, "category_code": cat, "label": label}, headers=MGR)
        assert r.status_code in (200, 409), r.text

    for code, (cat, _label, priority, mins, *_levels) in _SUBCATEGORIES.items():
        r = client.post("/cccapi/admin/sla-policies", json={
            "code": f"{code}-{priority}", "priority_code": priority, "resolution_mins": mins,
            "category_code": cat, "subcategory_code": code, "calendar_code": "DEFAULT-24X7",
        }, headers=MGR)
        assert r.status_code in (200, 409), r.text

    for code, (cat, _label, _pr, _mins, l1, l2, l3, l4) in _SUBCATEGORIES.items():
        body = {"code": f"RULE-{code}", "category_code": cat, "subcategory_code": code}
        for n, level in zip(("1", "2", "3", "4"), (l1, l2, l3, l4)):
            if "role" in level:
                body[f"l{n}_role"] = level["role"]
            elif "team" in level:
                body[f"l{n}_team_code"] = level["team"]
        r = client.post("/cccapi/admin/routing-rules", json=body, headers=MGR)
        assert r.status_code in (200, 409), r.text

    # Local accounts for the role holders we want RESOLVED (mapped case).
    # "E-OE-GHOST" is deliberately left WITHOUT a local account - the
    # unmapped-role-holder edge case.
    role_holders = [
        ("oe_officer", "E-OE-01", "OE"), ("dm_officer", "E-DM-01", "DM"),
        ("rm_officer", "E-RM-01", "RM"), ("sph_officer", "E-SPH-01", "SPH"),
    ]
    for username, emp_code, _role in role_holders:
        r = client.post("/cccapi/admin/users", json={
            "username": username, "name": username.replace("_", " ").title(), "role": "HELPDESK",
            "password": "testpass123", "hr_emp_code": emp_code,
        }, headers=MGR)
        assert r.status_code in (200, 409), r.text

    # Caller "EMP-CALLER-1" is who raises tickets in the "mapped" tests -
    # their OE/DM/RM/SPH all resolve to real, locally-accounted people.
    # "EMP-CALLER-GHOST" resolves OE to a real person with NO local account.
    # "EMP-CALLER-NONE" has no hierarchy data synced for them at all.
    hierarchy_rows = [
        {"emp_code": "EMP-CALLER-1", "role_code": "OE", "holder_emp_code": "E-OE-01", "holder_name": "Oe Officer", "holder_designation": "Officer Engineer"},
        {"emp_code": "EMP-CALLER-1", "role_code": "DM", "holder_emp_code": "E-DM-01", "holder_name": "Dm Officer", "holder_designation": "District Manager"},
        {"emp_code": "EMP-CALLER-1", "role_code": "RM", "holder_emp_code": "E-RM-01", "holder_name": "Rm Officer", "holder_designation": "Regional Manager"},
        {"emp_code": "EMP-CALLER-1", "role_code": "SPH", "holder_emp_code": "E-SPH-01", "holder_name": "Sph Officer", "holder_designation": "State Program Head"},
        {"emp_code": "EMP-CALLER-GHOST", "role_code": "OE", "holder_emp_code": "E-OE-GHOST", "holder_name": "Ghost Officer", "holder_designation": "Officer Engineer"},
    ]
    dummy_employees = [
        {"emp_code": "E-OE-01", "name": "Oe Officer", "designation": "Officer Engineer", "role_code": "OE"},
        {"emp_code": "E-DM-01", "name": "Dm Officer", "designation": "District Manager", "role_code": "DM"},
        {"emp_code": "E-RM-01", "name": "Rm Officer", "designation": "Regional Manager", "role_code": "RM"},
        {"emp_code": "E-SPH-01", "name": "Sph Officer", "designation": "State Program Head", "role_code": "SPH"},
        {"emp_code": "E-OE-GHOST", "name": "Ghost Officer", "designation": "Officer Engineer", "role_code": "OE"},
    ]
    dummy_vehicles = [
        {"registration_no": "AP39DUMMY1", "segment_number": "SEG-100", "district": "Krishna",
         "mandal": "Machilipatnam", "secretariat": "Ward-12", "village": "Peddana"},
        {"registration_no": "AP39DUMMY2", "segment_number": "SEG-200", "district": "Guntur",
         "mandal": "Tenali", "secretariat": "Ward-3", "village": "Kollipara"},
    ]
    yield {"role_holders": role_holders, "hierarchy_rows": hierarchy_rows,
           "dummy_employees": dummy_employees, "dummy_vehicles": dummy_vehicles}


def _run_sync(client, roster_server, seed):
    _RosterHandler.bodies = {
        "vehicles": seed["dummy_vehicles"], "employees": seed["dummy_employees"], "hierarchy": seed["hierarchy_rows"],
    }
    r = client.put("/cccapi/admin/hierarchy/config", json={
        "vehicle_roster_url": roster_server["vehicles"], "employee_roster_url": roster_server["employees"],
        "hierarchy_roster_url": roster_server["hierarchy"], "sync_enabled": True,
    }, headers=MGR)
    assert r.status_code == 200, r.text
    r = client.post("/cccapi/admin/sync/run", headers=MGR)
    assert r.status_code == 200, r.text
    return r.json()


def raise_ticket(client, category, subcategory_code, caller_emp_id, priority):
    r = client.post("/cccapi/ticket", json={
        "mmu_vehicle": "AP1", "district": "D", "problem": f"dummy data flow: {subcategory_code}",
        "category": category, "subcategory_code": subcategory_code, "priority": priority,
        "caller_name": "Dummy Caller", "caller_phone": "9876543210", "caller_emp_id": caller_emp_id,
    }, headers=CT)
    assert r.status_code == 200, r.text
    return r.json()


def chain_for(client, tid):
    return client.get(f"/cccapi/ticket/{tid}/assignments", headers=MGR).json()


def by_level(chain, level):
    return next(r for r in chain if r["level"] == level)


# ---------- master-data sync: the real pipeline, not hand-inserted rows ----------

def test_master_data_sync_ingests_the_dummy_roster(client, roster_server, _seed_matrix):
    result = _run_sync(client, roster_server, _seed_matrix)
    assert result["vehicles"]["status"] == "SUCCESS"
    assert result["vehicles"]["rows_upserted"] == 2
    assert result["employees"]["status"] == "SUCCESS"
    assert result["employees"]["rows_upserted"] == 5
    assert result["hierarchy"]["status"] == "SUCCESS"
    assert result["hierarchy"]["rows_upserted"] == 5

    r = client.get("/cccapi/tickets/lookup/vehicle?registration_no=AP39DUMMY1", headers=CT)
    body = r.json()
    assert body["source"] == "CACHE"
    assert body["data"]["segment_number"] == "SEG-100"
    assert body["data"]["village"] == "Peddana"

    r = client.get("/cccapi/tickets/lookup/employees?q=Officer", headers=CT)
    assert r.json()["source"] == "CACHE"
    assert len(r.json()["results"]) >= 4


# ---------- the five distinct L1-L4 patterns from the spreadsheet ----------

def test_login_failure_pattern_oe_dm_helpdesk_development(client, roster_server, _seed_matrix):
    _run_sync(client, roster_server, _seed_matrix)
    result = raise_ticket(client, "LOGIN_ACCESS", "LOGIN_FAILURE", "EMP-CALLER-1", "P2")
    chain = chain_for(client, result["id"])
    assert by_level(chain, "L1")["user_name"] == "Oe Officer"
    assert by_level(chain, "L2")["user_name"] == "Dm Officer"
    assert by_level(chain, "L3")["team_code"] == "HELPDESK"
    assert by_level(chain, "L3")["user_id"] is None
    assert by_level(chain, "L4")["team_code"] == "DEVELOPMENT"

    t = SessionLocal().query(Ticket).filter(Ticket.id == result["id"]).first()
    assert t.tat_mins == 240  # 4 Hrs, per the spreadsheet


def test_role_mapping_subcategory_overrides_siblings_with_rm_sph(client, roster_server, _seed_matrix):
    """'Role Mapping' breaks from its own Category's usual OE/DM/Helpdesk/
    Development pattern (see test_employee_mapping_shares_the_category_default
    below) by going all the way to RM/SPH at L3/L4 - proving the more
    specific Sub-Category rule wins over whatever the rest of the Category
    does, not just over a bare Category-level default."""
    _run_sync(client, roster_server, _seed_matrix)
    result = raise_ticket(client, "USER_EMP_MGMT", "ROLE_MAPPING", "EMP-CALLER-1", "P3")
    chain = chain_for(client, result["id"])
    assert by_level(chain, "L1")["user_name"] == "Oe Officer"
    assert by_level(chain, "L2")["user_name"] == "Dm Officer"
    assert by_level(chain, "L3")["user_name"] == "Rm Officer"
    assert by_level(chain, "L4")["user_name"] == "Sph Officer"

    t = SessionLocal().query(Ticket).filter(Ticket.id == result["id"]).first()
    assert t.tat_mins == 1440  # 1 Day


def test_employee_mapping_shares_the_category_default(client, roster_server, _seed_matrix):
    _run_sync(client, roster_server, _seed_matrix)
    result = raise_ticket(client, "USER_EMP_MGMT", "EMPLOYEE_MAPPING", "EMP-CALLER-1", "P3")
    chain = chain_for(client, result["id"])
    assert by_level(chain, "L3")["team_code"] == "HELPDESK"
    assert by_level(chain, "L4")["team_code"] == "DEVELOPMENT"


def test_duplicate_employee_repeats_the_same_team_at_two_levels(client, roster_server, _seed_matrix):
    """L3 and L4 are BOTH 'Development' in the spreadsheet - an edge case
    worth confirming explicitly (the same team can occupy consecutive
    levels; nothing about the model assumes each level is distinct)."""
    _run_sync(client, roster_server, _seed_matrix)
    result = raise_ticket(client, "USER_EMP_MGMT", "DUPLICATE_EMPLOYEE", "EMP-CALLER-1", "P3")
    chain = chain_for(client, result["id"])
    assert by_level(chain, "L1")["user_name"] == "Oe Officer"
    assert by_level(chain, "L2")["team_code"] == "ADMIN"
    assert by_level(chain, "L3")["team_code"] == "DEVELOPMENT"
    assert by_level(chain, "L4")["team_code"] == "DEVELOPMENT"


def test_patient_health_card_pattern_all_teams_no_roles(client, roster_server, _seed_matrix):
    """L1 here is a TEAM ('Helpdesk'), not an API role - proving L1 doesn't
    have to be role-based just because Login & Access's L1 always is."""
    _run_sync(client, roster_server, _seed_matrix)
    result = raise_ticket(client, "PATIENT_HEALTH_CARD", "CARD_GENERATION", "EMP-CALLER-1", "P3")
    assert result["team"] == "HELPDESK"
    chain = chain_for(client, result["id"])
    assert by_level(chain, "L1")["team_code"] == "HELPDESK"
    assert by_level(chain, "L1")["user_id"] is None
    assert by_level(chain, "L2")["team_code"] == "DEVELOPMENT"
    assert by_level(chain, "L3")["team_code"] == "PM_IT"
    assert by_level(chain, "L4")["team_code"] == "ADMIN"

    t = SessionLocal().query(Ticket).filter(Ticket.id == result["id"]).first()
    assert t.tat_mins == 1440  # 1 Day


def test_laboratory_lis_pattern_includes_lis_support(client, roster_server, _seed_matrix):
    _run_sync(client, roster_server, _seed_matrix)
    result = raise_ticket(client, "LAB_LIS", "SAMPLE_COLLECTION", "EMP-CALLER-1", "P2")
    assert result["team"] == "HELPDESK"
    chain = chain_for(client, result["id"])
    assert by_level(chain, "L2")["team_code"] == "LIS_SUPPORT"

    t = SessionLocal().query(Ticket).filter(Ticket.id == result["id"]).first()
    assert t.tat_mins == 480  # 8 Hrs


# ---------- edge cases ----------

def test_sla_minutes_vary_correctly_by_subcategory_and_priority(client, roster_server, _seed_matrix):
    _run_sync(client, roster_server, _seed_matrix)
    cases = [
        ("LOGIN_ACCESS", "LOGIN_FAILURE", "P2", 240),
        ("LOGIN_ACCESS", "FORGOT_PASSWORD", "P3", 120),
        ("LOGIN_ACCESS", "ACCOUNT_LOCKED", "P3", 120),
        ("USER_EMP_MGMT", "VEHICLE_MAPPING", "P2", 480),
    ]
    for cat, sub, pr, expected_mins in cases:
        result = raise_ticket(client, cat, sub, "EMP-CALLER-1", pr)
        t = SessionLocal().query(Ticket).filter(Ticket.id == result["id"]).first()
        assert t.tat_mins == expected_mins, f"{cat}/{sub}/{pr}: expected {expected_mins}, got {t.tat_mins}"


def test_unmapped_role_holder_is_recorded_by_name_and_flagged(client, roster_server, _seed_matrix):
    """EMP-CALLER-GHOST's OE resolves to a real synced person (Ghost
    Officer) who has no local ccc_user account - the ticket must still be
    created (never blocked), the occupant recorded by name, and an
    Assignment Exception raised for a supervisor to fix."""
    _run_sync(client, roster_server, _seed_matrix)
    result = raise_ticket(client, "LOGIN_ACCESS", "LOGIN_FAILURE", "EMP-CALLER-GHOST", "P2")
    chain = chain_for(client, result["id"])
    l1 = by_level(chain, "L1")
    assert l1["user_id"] is None
    assert l1["user_name"] == "Ghost Officer"

    r = client.get("/cccapi/admin/assignment-exceptions?status=OPEN", headers=MGR)
    assert any(e["ticket_id"] == result["id"] and e["reason"] == "UNMAPPED_ROLE_OCCUPANT" for e in r.json())


def test_caller_with_no_synced_hierarchy_falls_back_to_team_gracefully(client, roster_server, _seed_matrix):
    """No ccc_emp_hierarchy data at all for this caller - the ticket must
    still be created and still route, falling back to whatever the level
    would otherwise resolve to (here, nothing else overrides L1, so it
    falls all the way to the ticket's own routed team)."""
    _run_sync(client, roster_server, _seed_matrix)
    result = raise_ticket(client, "LOGIN_ACCESS", "LOGIN_FAILURE", "EMP-CALLER-NONE", "P2")
    assert result["ok"] is True
    chain = chain_for(client, result["id"])
    l1 = by_level(chain, "L1")
    assert l1["user_id"] is None
    assert l1["team_code"] == result["team"]


def test_escalation_ladder_works_against_the_mixed_role_team_config(client, roster_server, _seed_matrix):
    """The 30% L1 auto-escalation fires correctly for a role-resolved
    occupant on this real-world-shaped config, same as the synthetic
    fixtures in test_role_mapping.py / test_tiered_sla.py."""
    _run_sync(client, roster_server, _seed_matrix)
    result = raise_ticket(client, "LOGIN_ACCESS", "LOGIN_FAILURE", "EMP-CALLER-1", "P2")
    tid = result["id"]

    db = SessionLocal()
    t = db.query(Ticket).filter(Ticket.id == tid).first()
    now = datetime.datetime.now()
    elapsed = t.tat_mins * 0.35
    t.created_at = now - datetime.timedelta(minutes=elapsed)
    t.due_at = now + datetime.timedelta(minutes=t.tat_mins - elapsed)
    db.commit()
    db.close()

    run_sla_sweep_once()

    oe_headers = auth_headers("HELPDESK", username="oe_officer")
    rows = client.get("/cccapi/notifications", headers=oe_headers).json()["rows"]
    types = [n["type"] for n in rows if n["ticket_id"] == tid]
    assert "ESCALATED_L1" in types
