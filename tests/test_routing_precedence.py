"""Phase 5 stage 1: Sub-Category + District routing rule precedence.

Covers each rung of match_rule()'s specificity ladder (category+sub+district
> category+sub+zone > category+sub > category+district > category+zone >
category-only), tie-break determinism, and that route_ticket()'s matched
rule.l1_team_code now drives ticket.team (not just the L1 hierarchy
occupant, closing the old ticket.team vs L1 disagreement).

Each test picks a category the rest of the suite never gives a bare
(unscoped) Routing Rule - tests/test_hierarchy.py permanently activates one
for MACHINE ("MACHINE-NAMED") and one for QC ("DUP1"), and since routing
rules are never cleaned up between tests (like Teams/Categories elsewhere in
this suite), a bare rule created here for either of those categories would
either 409 against theirs or silently change their expected routing. Zone
scoping additionally requires the category to be routed by zone (like
test_geo_routing.py's toggle) since a ticket only ever gets a non-null
zone_id when Category.route_by_zone matched a Mandal->Zone at creation."""
from tests.conftest import auth_headers
from tests.test_geo_routing import make_district, make_mandal, make_zone

MGR = auth_headers("CC_MANAGER")
CT = auth_headers("CALL_TAKER")


def make_reason(client, code, category_code, label=None):
    r = client.post("/cccapi/admin/reasons", json={
        "code": code, "category_code": category_code, "label": label or code,
    }, headers=MGR)
    assert r.status_code == 200, r.text
    return r.json()["code"]


def make_rule(client, code, category_code, **kw):
    body = {"code": code, "category_code": category_code}
    body.update(kw)
    r = client.post("/cccapi/admin/routing-rules", json=body, headers=MGR)
    assert r.status_code == 200, r.text
    return r.json()


def raise_ticket(client, category, subcategory_code=None, district_id=None, mandal_id=None):
    body = {
        "mmu_vehicle": "AP1", "district": "D", "problem": "precedence test", "category": category,
        "priority": "P2", "caller_name": "Test Caller", "caller_phone": "9876543210",
    }
    if subcategory_code:
        body["subcategory_code"] = subcategory_code
    if district_id:
        body["district_id"] = district_id
    if mandal_id:
        body["mandal_id"] = mandal_id
    r = client.post("/cccapi/ticket", json=body, headers=CT)
    assert r.status_code == 200, r.text
    return r.json()


def test_category_only_rule_is_the_floor(client):
    make_rule(client, "PREC-CATONLY", "APPLICATION", l1_team_code="APPLICATION")
    result = raise_ticket(client, "APPLICATION")
    assert result["team"] == "APPLICATION"


def test_district_rule_beats_category_only(client):
    d = make_district(client, "PrecDistrictBeatsCat")
    make_rule(client, "PREC-CAT2", "TECHNICAL", l1_team_code="TECHNICAL")
    make_rule(client, "PREC-DIST2", "TECHNICAL", district_id=d, l1_team_code="NETWORK")
    result = raise_ticket(client, "TECHNICAL", district_id=d)
    assert result["team"] == "NETWORK"


def test_zone_rule_beats_category_only_but_loses_to_district(client):
    z = make_zone(client, "PrecZoneVsDistrict", "NETWORK")
    d = make_district(client, "PrecZoneVsDistrictD")
    m = make_mandal(client, "PrecZoneVsDistrictM", d, zone_id=z)
    client.put("/cccapi/admin/categories/LIS", json={"route_by_zone": True}, headers=MGR)
    try:
        make_rule(client, "PREC-CAT3", "LIS", l1_team_code="NETWORK")
        make_rule(client, "PREC-ZONE3", "LIS", zone_id=z, l1_team_code="FIELD_OPS")
        make_rule(client, "PREC-DIST3", "LIS", district_id=d, l1_team_code="TECHNICAL")
        result = raise_ticket(client, "LIS", district_id=d, mandal_id=m)
        assert result["team"] == "TECHNICAL"  # district (score 2) beats zone (score 1)
    finally:
        client.put("/cccapi/admin/categories/LIS", json={"route_by_zone": False}, headers=MGR)


def test_subcategory_rule_beats_category_rule(client):
    sub = make_reason(client, "PREC-SUB1", "NETWORK")
    make_rule(client, "PREC-CAT4", "NETWORK", l1_team_code="QUALITY")
    make_rule(client, "PREC-SUBR4", "NETWORK", subcategory_code=sub, l1_team_code="TECHNICAL")
    result = raise_ticket(client, "NETWORK", subcategory_code=sub)
    assert result["team"] == "TECHNICAL"


def test_subcategory_plus_district_beats_subcategory_plus_zone(client):
    sub = make_reason(client, "PREC-SUB2", "QC")
    z = make_zone(client, "PrecSubZone", "NETWORK")
    d = make_district(client, "PrecSubDistrict")
    m = make_mandal(client, "PrecSubMandal", d, zone_id=z)
    client.put("/cccapi/admin/categories/QC", json={"route_by_zone": True}, headers=MGR)
    try:
        make_rule(client, "PREC-SUBZONE5", "QC", subcategory_code=sub, zone_id=z, l1_team_code="FIELD_OPS")
        make_rule(client, "PREC-SUBDIST5", "QC", subcategory_code=sub, district_id=d, l1_team_code="TECHNICAL")
        result = raise_ticket(client, "QC", subcategory_code=sub, district_id=d, mandal_id=m)
        assert result["team"] == "TECHNICAL"
    finally:
        client.put("/cccapi/admin/categories/QC", json={"route_by_zone": False}, headers=MGR)


def test_a_rule_with_mismatched_narrowing_field_is_not_eligible(client):
    """A district-scoped rule for a DIFFERENT district must not match."""
    d1 = make_district(client, "PrecMismatchD1")
    d2 = make_district(client, "PrecMismatchD2")
    make_rule(client, "PREC-CAT6", "FLEET", l1_team_code="FLEET")
    make_rule(client, "PREC-DIST6", "FLEET", district_id=d1, l1_team_code="TECHNICAL")
    result = raise_ticket(client, "FLEET", district_id=d2)
    assert result["team"] == "FLEET"  # d1's rule doesn't apply to d2's ticket


def test_match_is_deterministic_among_equally_specific_rules(client):
    """Two category-only rules for the same category can't both be active
    (create_rule's uniqueness guard) - this proves that guard is exercised;
    reuses APPLICATION's bare rule from test_category_only_rule_is_the_floor
    rather than claiming a fresh category, since tests in this file run in
    declaration order (pytest's default) and routing rules are never
    cleaned up between tests."""
    r = client.post("/cccapi/admin/routing-rules", json={
        "code": "PREC-TIE-B", "category_code": "APPLICATION", "l1_team_code": "TECHNICAL",
    }, headers=MGR)
    assert r.status_code == 409


def test_subcategory_must_belong_to_the_rules_category(client):
    other_sub = make_reason(client, "PREC-WRONGCAT-SUB", "QC")
    r = client.post("/cccapi/admin/routing-rules", json={
        "code": "PREC-BADSUB", "category_code": "MACHINE", "subcategory_code": other_sub,
    }, headers=MGR)
    assert r.status_code == 400


def test_rule_district_must_be_active(client):
    r = client.post("/cccapi/admin/routing-rules", json={
        "code": "PREC-BADDIST", "category_code": "MACHINE", "district_id": 999999,
    }, headers=MGR)
    assert r.status_code == 400


def test_ticket_team_and_l1_occupant_agree(client):
    """Closes the pre-Phase-5 gap: a matched rule's l1_team_code now drives
    both ticket.team (routing) and the L1 hierarchy occupant's team_code."""
    d = make_district(client, "PrecAgreeDistrict")
    make_rule(client, "PREC-AGREE", "FLEET", district_id=d, l1_team_code="NETWORK")
    result = raise_ticket(client, "FLEET", district_id=d)
    assert result["team"] == "NETWORK"
    chain = client.get(f"/cccapi/ticket/{result['id']}/assignments", headers=MGR).json()
    l1 = next(r for r in chain if r["level"] == "L1" and r["status"] == "ACTIVE")
    assert l1["team_code"] == "NETWORK"
