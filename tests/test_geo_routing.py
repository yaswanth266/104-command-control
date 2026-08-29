from tests.conftest import auth_headers

MGR = auth_headers("CC_MANAGER")
CT = auth_headers("CALL_TAKER")


def make_district(client, name):
    r = client.post("/cccapi/admin/districts", json={"name": name}, headers=MGR)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def make_mandal(client, name, district_id, zone_id=None):
    r = client.post("/cccapi/admin/mandals", json={"name": name, "district_id": district_id, "zone_id": zone_id}, headers=MGR)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def make_zone(client, name, team_code):
    r = client.post("/cccapi/admin/zones", json={"name": name, "team_code": team_code}, headers=MGR)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_duplicate_district_name_rejected(client):
    make_district(client, "TestDistrictDup")
    r = client.post("/cccapi/admin/districts", json={"name": "TestDistrictDup"}, headers=MGR)
    assert r.status_code == 409


def test_mandal_requires_active_district(client):
    r = client.post("/cccapi/admin/mandals", json={"name": "GhostMandal", "district_id": 999999}, headers=MGR)
    assert r.status_code == 400


def test_zone_requires_active_team(client):
    r = client.post("/cccapi/admin/zones", json={"name": "GhostZone", "team_code": "NOT_A_TEAM"}, headers=MGR)
    assert r.status_code == 400


def test_deactivate_district_blocked_with_active_mandal(client):
    d = make_district(client, "TestDistrictBlock")
    make_mandal(client, "TestMandalBlock", d)
    r = client.put(f"/cccapi/admin/districts/{d}", json={"is_active": False}, headers=MGR)
    assert r.status_code == 409


def test_deactivate_zone_blocked_with_active_mandal(client):
    z = make_zone(client, "TestZoneBlock", "SERVICE")
    d = make_district(client, "TestDistrictForZoneBlock")
    make_mandal(client, "TestMandalForZoneBlock", d, zone_id=z)
    r = client.put(f"/cccapi/admin/zones/{z}", json={"is_active": False}, headers=MGR)
    assert r.status_code == 409


def test_category_without_route_by_zone_ignores_zone(client):
    """Use Case 4: a category can simply not be flagged route_by_zone to stay
    centrally routed regardless of geography."""
    z = make_zone(client, "TestZoneIgnored", "TECHNICAL")
    d = make_district(client, "TestDistrictIgnored")
    m = make_mandal(client, "TestMandalIgnored", d, zone_id=z)
    r = client.post("/cccapi/ticket", json={
        "mmu_vehicle": "AP1", "district": "D", "problem": "software bug", "category": "APPLICATION",
        "priority": "P2", "mandal_id": m, "caller_name": "Test Caller", "caller_phone": "9876543210",
    }, headers=CT)
    assert r.status_code == 200, r.text
    assert r.json()["team"] == "APPLICATION"  # category default, NOT the zone's TECHNICAL team


def test_category_with_route_by_zone_uses_zone_team(client):
    z = make_zone(client, "TestZoneUsed", "TECHNICAL")
    d = make_district(client, "TestDistrictUsed")
    m = make_mandal(client, "TestMandalUsed", d, zone_id=z)
    client.put("/cccapi/admin/categories/MACHINE", json={"route_by_zone": True}, headers=MGR)
    try:
        r = client.post("/cccapi/ticket", json={
            "mmu_vehicle": "AP1", "district": "D", "problem": "machine broke", "category": "MACHINE",
            "priority": "P2", "mandal_id": m, "caller_name": "Test Caller", "caller_phone": "9876543210",
        }, headers=CT)
        assert r.status_code == 200, r.text
        assert r.json()["team"] == "TECHNICAL"  # zone's team wins over MACHINE's own SERVICE default
    finally:
        client.put("/cccapi/admin/categories/MACHINE", json={"route_by_zone": False}, headers=MGR)


def test_route_by_zone_falls_back_when_mandal_has_no_zone(client):
    """Use Case 5: rollout gap - a Mandal with no Zone configured yet must not
    break routing."""
    d = make_district(client, "TestDistrictNoZone")
    m = make_mandal(client, "TestMandalNoZone", d, zone_id=None)
    client.put("/cccapi/admin/categories/MACHINE", json={"route_by_zone": True}, headers=MGR)
    try:
        r = client.post("/cccapi/ticket", json={
            "mmu_vehicle": "AP1", "district": "D", "problem": "machine broke", "category": "MACHINE",
            "priority": "P2", "mandal_id": m, "caller_name": "Test Caller", "caller_phone": "9876543210",
        }, headers=CT)
        assert r.status_code == 200, r.text
        assert r.json()["team"] == "SERVICE"  # category default fallback
    finally:
        client.put("/cccapi/admin/categories/MACHINE", json={"route_by_zone": False}, headers=MGR)


def test_ticket_geo_snapshot_survives_mandal_reparenting(client):
    """Use Case 2: district boundary redraw - a ticket's snapshotted
    district_id must not shift when the Mandal is later reparented."""
    d1 = make_district(client, "TestDistrictOld")
    d2 = make_district(client, "TestDistrictNew")
    m = make_mandal(client, "TestMandalReparented", d1)

    r = client.post("/cccapi/ticket", json={
        "mmu_vehicle": "AP1", "district": "D", "problem": "issue", "category": "MACHINE",
        "priority": "P2", "district_id": d1, "mandal_id": m, "caller_name": "Test Caller", "caller_phone": "9876543210",
    }, headers=CT)
    assert r.status_code == 200, r.text
    tid = r.json()["id"]

    # Reorganize: move the Mandal to the new District
    client.put(f"/cccapi/admin/mandals/{m}", json={"district_id": d2}, headers=MGR)

    r2 = client.get(f"/cccapi/ticket/{tid}", headers=MGR)
    assert r2.json()["ticket"]["district_id"] == d1  # unchanged, snapshotted at creation


def test_vehicle_not_tied_to_mandal(client):
    """The user's explicit correction: a vehicle registry entry carries no
    authoritative location - it can be used to register tickets from any
    Mandal without needing to update the vehicle record."""
    r = client.post("/cccapi/admin/vehicles", json={"registration_no": "AP39TESTMOVE"}, headers=MGR)
    assert r.status_code == 200, r.text
    vid = r.json()["id"]
    assert r.json()["last_mandal_id"] is None

    d = make_district(client, "TestDistrictMove1")
    m1 = make_mandal(client, "TestMandalMove1", d)
    m2 = make_mandal(client, "TestMandalMove2", d)

    r1 = client.post("/cccapi/ticket", json={
        "mmu_vehicle": "AP39TESTMOVE", "vehicle_id": vid, "district": "D", "problem": "issue A",
        "category": "MACHINE", "priority": "P3", "mandal_id": m1, "caller_name": "Test Caller", "caller_phone": "9876543210",
    }, headers=CT)
    r2 = client.post("/cccapi/ticket", json={
        "mmu_vehicle": "AP39TESTMOVE", "vehicle_id": vid, "district": "D", "problem": "issue B",
        "category": "MACHINE", "priority": "P3", "mandal_id": m2, "caller_name": "Test Caller", "caller_phone": "9876543210",
    }, headers=CT)
    assert r1.status_code == 200 and r2.status_code == 200
    t1 = client.get(f"/cccapi/ticket/{r1.json()['id']}", headers=MGR).json()["ticket"]
    t2 = client.get(f"/cccapi/ticket/{r2.json()['id']}", headers=MGR).json()["ticket"]
    assert t1["mandal_id"] == m1
    assert t2["mandal_id"] == m2  # same vehicle, two different Mandals, no conflict


def test_vehicle_search(client):
    client.post("/cccapi/admin/vehicles", json={"registration_no": "AP39SEARCHME"}, headers=MGR)
    r = client.get("/cccapi/vehicles/search?q=SEARCHME", headers=CT)
    assert r.status_code == 200
    assert any(v["registration_no"] == "AP39SEARCHME" for v in r.json())


def test_public_lookup_endpoints(client):
    d = make_district(client, "TestDistrictLookup")
    make_mandal(client, "TestMandalLookup", d)
    r = client.get("/cccapi/districts", headers=CT)
    assert any(x["id"] == d for x in r.json())
    r = client.get(f"/cccapi/mandals?district_id={d}", headers=CT)
    assert any(x["name"] == "TestMandalLookup" for x in r.json())
