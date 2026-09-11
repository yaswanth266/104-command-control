"""Phase 5 stage 2: Routing Rule lN_role -> L1-L4 occupant resolution against
the external hierarchy cache (ccc_emp_hierarchy), mixed freely with local
usernames and teams - the client's example config:
    L1 -> OE (API role)   L2 -> DM (API role)
    L3 -> Helpdesk (team) L4 -> Development (team)
Seeds ccc_emp_hierarchy directly via SessionLocal since only the (disabled
by default) sync job writes it in production - see test_master_sync.py for
that path; this file tests _resolve_local()'s consumption of it in
isolation, the same split test_hierarchy.py uses for the default ladder.

Every routing rule created here is scoped to its own fresh Sub-Category
(even where the test doesn't otherwise care about sub-categories) so its
uniqueness tuple never collides with a bare category-only rule some other
test file leaves active for the same category (routing rules, like
Teams/Categories elsewhere in this suite, are never cleaned up between
tests) - see test_routing_precedence.py's module docstring for the same
concern from the other direction."""
from tests.conftest import auth_headers
from app.db.database import SessionLocal
from app.models.emp_hierarchy import EmpHierarchy
from app.models.user import User

MGR = auth_headers("CC_MANAGER")
CT = auth_headers("CALL_TAKER")


def seed_hierarchy_row(emp_code, role_code, holder_emp_code, holder_name, holder_designation=None):
    db = SessionLocal()
    db.add(EmpHierarchy(emp_code=emp_code, role_code=role_code, holder_emp_code=holder_emp_code,
                         holder_name=holder_name, holder_designation=holder_designation))
    db.commit()
    db.close()


def set_hr_emp_code(username, hr_emp_code):
    db = SessionLocal()
    db.query(User).filter(User.username == username).update({"hr_emp_code": hr_emp_code})
    db.commit()
    db.close()


def make_reason(client, code, category_code):
    r = client.post("/cccapi/admin/reasons", json={"code": code, "category_code": category_code, "label": code},
                     headers=MGR)
    assert r.status_code == 200, r.text
    return r.json()["code"]


def make_rule(client, code, category_code, subcategory_code, **kw):
    body = {"code": code, "category_code": category_code, "subcategory_code": subcategory_code}
    body.update(kw)
    r = client.post("/cccapi/admin/routing-rules", json=body, headers=MGR)
    assert r.status_code == 200, r.text
    return r.json()


def raise_ticket(client, category, caller_emp_id, subcategory_code=None):
    body = {
        "mmu_vehicle": "AP1", "district": "D", "problem": "role mapping test", "category": category,
        "priority": "P2", "caller_name": "Test Caller", "caller_phone": "9876543210",
        "caller_emp_id": caller_emp_id,
    }
    if subcategory_code:
        body["subcategory_code"] = subcategory_code
    r = client.post("/cccapi/ticket", json=body, headers=CT)
    assert r.status_code == 200, r.text
    return r.json()


def chain_for(client, tid):
    return client.get(f"/cccapi/ticket/{tid}/assignments", headers=MGR).json()


def test_role_resolves_to_a_local_user_via_hr_emp_code(client):
    set_hr_emp_code("service", "E-OE-1")
    seed_hierarchy_row("CALLER-1", "OE", "E-OE-1", "Service", "Officer Engineer")
    sub = make_reason(client, "ROLE-SUB-1", "APPLICATION")
    make_rule(client, "ROLE-OE-1", "APPLICATION", sub, l1_role="OE")

    result = raise_ticket(client, "APPLICATION", "CALLER-1", subcategory_code=sub)
    chain = chain_for(client, result["id"])
    l1 = next(r for r in chain if r["level"] == "L1")
    assert l1["user_name"] == "Service"
    assert l1["source"] == "LOCAL"


def test_username_takes_precedence_over_role(client):
    set_hr_emp_code("service", "E-OE-2")
    seed_hierarchy_row("CALLER-2", "OE", "E-OE-2", "Service", "Officer Engineer")
    sub = make_reason(client, "ROLE-SUB-2", "APPLICATION")
    make_rule(client, "ROLE-PRECEDENCE", "APPLICATION", sub, l1_role="OE", l1_username="cc_manager")

    result = raise_ticket(client, "APPLICATION", "CALLER-2", subcategory_code=sub)
    chain = chain_for(client, result["id"])
    l1 = next(r for r in chain if r["level"] == "L1")
    assert l1["user_name"] == "Cc Manager"  # explicit username wins over the role


def test_mixed_role_and_team_configuration(client):
    """The client's example: L1->OE, L2->DM (API roles), L3->Helpdesk,
    L4->Development (local teams, no specific user)."""
    set_hr_emp_code("service", "E-OE-3")
    set_hr_emp_code("cc_manager", "E-DM-3")
    seed_hierarchy_row("CALLER-3", "OE", "E-OE-3", "Service")
    seed_hierarchy_row("CALLER-3", "DM", "E-DM-3", "Cc Manager")
    sub = make_reason(client, "ROLE-SUB-3", "TECHNICAL")
    make_rule(client, "ROLE-MIXED", "TECHNICAL", sub, l1_role="OE", l2_role="DM",
              l3_team_code="FIELD_OPS", l4_team_code="NETWORK")

    result = raise_ticket(client, "TECHNICAL", "CALLER-3", subcategory_code=sub)
    chain = chain_for(client, result["id"])
    l1 = next(r for r in chain if r["level"] == "L1")
    l2 = next(r for r in chain if r["level"] == "L2")
    l3 = next(r for r in chain if r["level"] == "L3")
    l4 = next(r for r in chain if r["level"] == "L4")
    assert l1["user_name"] == "Service"
    assert l2["user_name"] == "Cc Manager"
    assert l3["team_code"] == "FIELD_OPS"
    assert l3["user_id"] is None
    assert l4["team_code"] == "NETWORK"
    assert l4["user_id"] is None


def test_unmapped_role_holder_records_name_and_raises_exception(client):
    """A role resolves to a real person via the hierarchy cache, but that
    person has no ccc_user account - the occupant is still recorded (by
    name), and an Assignment Exception is raised for a supervisor to fix."""
    seed_hierarchy_row("CALLER-4", "OE", "E-GHOST", "Ghost Officer", "Officer Engineer")
    sub = make_reason(client, "ROLE-SUB-4", "QC")
    make_rule(client, "ROLE-UNMAPPED", "QC", sub, l1_role="OE")

    result = raise_ticket(client, "QC", "CALLER-4", subcategory_code=sub)
    chain = chain_for(client, result["id"])
    l1 = next(r for r in chain if r["level"] == "L1")
    assert l1["user_id"] is None
    assert l1["user_name"] == "Ghost Officer"

    r = client.get("/cccapi/admin/assignment-exceptions?status=OPEN", headers=MGR)
    assert any(e["ticket_id"] == result["id"] and e["reason"] == "UNMAPPED_ROLE_OCCUPANT" for e in r.json())


def test_role_with_no_synced_hierarchy_data_falls_back_to_team(client):
    """No ccc_emp_hierarchy row for this caller/role at all - not even an
    unmapped-person case, just nothing synced yet. Falls back to the rule's
    lN_team_code if set, else the default ladder - never blocks the ticket."""
    sub = make_reason(client, "ROLE-SUB-5", "FLEET")
    make_rule(client, "ROLE-NODATA", "FLEET", sub, l1_role="OE", l1_team_code="FLEET")

    result = raise_ticket(client, "FLEET", "CALLER-NEVER-SYNCED", subcategory_code=sub)
    chain = chain_for(client, result["id"])
    l1 = next(r for r in chain if r["level"] == "L1")
    assert l1["user_id"] is None
    assert l1["team_code"] == "FLEET"


def test_role_with_no_caller_emp_id_falls_back(client):
    """A ticket raised with no caller_emp_id at all (e.g. caller info typed
    manually, no employee lookup used) can't resolve any role - same
    graceful fallback as the no-synced-data case."""
    sub = make_reason(client, "ROLE-SUB-6", "LIS")
    make_rule(client, "ROLE-NOCALLER", "LIS", sub, l2_role="DM")
    r = client.post("/cccapi/ticket", json={
        "mmu_vehicle": "AP1", "district": "D", "problem": "no caller emp id", "category": "LIS",
        "priority": "P2", "caller_name": "Test Caller", "caller_phone": "9876543210",
        "subcategory_code": sub,
    }, headers=CT)
    assert r.status_code == 200, r.text
    chain = chain_for(client, r.json()["id"])
    l2 = next(row for row in chain if row["level"] == "L2")
    assert l2["source"] == "LOCAL"
