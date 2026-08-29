import io
from tests.conftest import auth_headers, LT_CATEGORY, LT_USERNAME

CT = auth_headers("CALL_TAKER")
SVC = auth_headers("SERVICE")
APP = auth_headers("APPLICATION")
MGR = auth_headers("CC_MANAGER")
LT = auth_headers("LT", username=LT_USERNAME)


def make_ticket(client, category="MACHINE"):
    r = client.post("/cccapi/ticket", json={
        "mmu_vehicle": "AP1ATTACH", "district": "D", "problem": "attachment test",
        "category": category, "priority": "P2", "caller_name": "Test Caller", "caller_phone": "9876543210",
    }, headers=CT)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _png_file(name="photo.png"):
    # Minimal valid-enough PNG header bytes - save_ticket_attachment only checks content-type, not file magic bytes.
    return (name, io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"0" * 100), "image/png")


def test_upload_and_list_attachment(client):
    tid = make_ticket(client)
    r = client.post(f"/cccapi/ticket/{tid}/attachments", data={"note": "before photo"},
                     files={"file": _png_file()}, headers=SVC)
    assert r.status_code == 200, r.text
    assert r.json()["note"] == "before photo"

    r2 = client.get(f"/cccapi/ticket/{tid}/attachments", headers=SVC)
    assert r2.status_code == 200
    rows = r2.json()
    assert len(rows) == 1
    assert rows[0]["original_name"] == "photo.png"


def test_upload_rejects_disallowed_type(client):
    tid = make_ticket(client)
    bad_file = ("clip.mp4", io.BytesIO(b"not really a video"), "video/mp4")
    r = client.post(f"/cccapi/ticket/{tid}/attachments", data={}, files={"file": bad_file}, headers=SVC)
    assert r.status_code == 400


def test_upload_rejects_over_cap_file(client):
    tid = make_ticket(client)
    big_file = ("big.png", io.BytesIO(b"0" * (21 * 1024 * 1024)), "image/png")
    r = client.post(f"/cccapi/ticket/{tid}/attachments", data={}, files={"file": big_file}, headers=SVC)
    assert r.status_code == 400


def test_upload_forbidden_for_other_team(client):
    tid = make_ticket(client, category="MACHINE")  # -> SERVICE
    r = client.post(f"/cccapi/ticket/{tid}/attachments", data={}, files={"file": _png_file()}, headers=APP)
    assert r.status_code == 403


def test_upload_allowed_for_cc_manager_and_call_taker(client):
    tid = make_ticket(client)
    r1 = client.post(f"/cccapi/ticket/{tid}/attachments", data={}, files={"file": _png_file("a.png")}, headers=MGR)
    assert r1.status_code == 200, r1.text
    r2 = client.post(f"/cccapi/ticket/{tid}/attachments", data={}, files={"file": _png_file("b.png")}, headers=CT)
    assert r2.status_code == 200, r2.text


def test_lt_who_raised_portal_ticket_can_upload(client):
    r = client.post("/cccapi/lt/tickets", data={
        "category": LT_CATEGORY, "reason_codes": "NO_POWER", "priority": "P1", "problem": "attachment from LT",
    }, headers=LT)
    assert r.status_code == 200, r.text
    tid = r.json()["id"]
    r2 = client.post(f"/cccapi/ticket/{tid}/attachments", data={}, files={"file": _png_file()}, headers=LT)
    assert r2.status_code == 200, r2.text


def test_resolve_creates_an_attachment_added_event_when_uploaded_separately(client):
    tid = make_ticket(client)
    client.post("/cccapi/ticket/action", json={"id": tid, "action": "acknowledge"}, headers=SVC)
    client.post("/cccapi/ticket/action", json={"id": tid, "action": "resolve", "resolution": "fixed it"}, headers=SVC)
    client.post(f"/cccapi/ticket/{tid}/attachments", data={"note": "resolution evidence"}, files={"file": _png_file()}, headers=SVC)

    events = client.get(f"/cccapi/ticket/{tid}", headers=SVC).json()["events"]
    assert any(e["action"] == "ATTACHMENT_ADDED" for e in events)
