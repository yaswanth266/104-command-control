import datetime
import io
from tests.conftest import auth_headers, LT_CDA_TEAM, LT_CATEGORY, LT_USERNAME, lt_ids
from app.db.database import SessionLocal
from app.models.ticket import Ticket
from app.services.sla_sweep import run_sla_sweep_once

LT = auth_headers("LT", username=LT_USERNAME)
LT2 = auth_headers("LT", username="lt2")
CDA = auth_headers(LT_CDA_TEAM, username=LT_CDA_TEAM.lower())
MGR = auth_headers("CC_MANAGER")


def _raise_lt_ticket(client, reason_codes="NO_POWER,CALIBRATION", **overrides):
    form = {
        "category": LT_CATEGORY,
        "reason_codes": reason_codes,
        "machine_id": str(lt_ids["machine_id"]),
        "priority": "P1",
        "problem": "Analyzer stopped mid-run",
    }
    form.update(overrides)
    r = client.post("/cccapi/lt/tickets", data=form, headers=LT)
    return r


def test_lt_ticket_routes_to_district_cda_team_via_zone(client):
    r = _raise_lt_ticket(client)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["team"] == LT_CDA_TEAM

    # confirm the zone-routing actually fired (not just the category default)
    db = SessionLocal()
    t = db.query(Ticket).filter(Ticket.id == body["id"]).first()
    assert t.zone_id == lt_ids["zone_id"]
    assert t.district_id == lt_ids["district_id"]
    assert t.mandal_id == lt_ids["mandal_id"]
    assert t.vehicle_id == lt_ids["vehicle_id"]
    assert t.machine_id == lt_ids["machine_id"]
    assert t.reason_codes == ["NO_POWER", "CALIBRATION"]
    assert t.source == "LT_PORTAL"
    assert t.created_by == LT_USERNAME
    db.close()


def test_lt_own_history_excludes_other_lts_tickets(client):
    _raise_lt_ticket(client)
    r = client.get("/cccapi/lt/tickets", headers=LT2)
    assert r.status_code == 200
    assert r.json() == []

    r_own = client.get("/cccapi/lt/tickets", headers=LT)
    assert r_own.status_code == 200
    assert len(r_own.json()) >= 1


def test_lt_cannot_use_department_ticket_queue(client):
    _raise_lt_ticket(client)
    r = client.get("/cccapi/tickets", headers=LT)
    # LT's role isn't CC_MANAGER/CALL_TAKER, so get_tickets scopes by
    # Ticket.team == role - "LT" is not a team, so this just returns nothing,
    # never another team's queue.
    assert r.status_code == 200
    assert r.json()["rows"] == []


def test_reasons_lookup_filters_by_category(client):
    r = client.get(f"/cccapi/reasons?category={LT_CATEGORY}", headers=LT)
    assert r.status_code == 200
    codes = {row["code"] for row in r.json()}
    assert {"NO_POWER", "CALIBRATION"} <= codes


def test_reason_must_belong_to_category(client):
    r = _raise_lt_ticket(client, category="LT_OTHER", reason_codes="NO_POWER")
    # NO_POWER belongs to LT_CATEGORY, not LT_OTHER - rejected even though
    # LT_OTHER is itself a valid, LT-visible category.
    assert r.status_code == 400


def test_priority_restricted_to_p1_p2(client):
    r = _raise_lt_ticket(client, priority="P3")
    assert r.status_code == 400


def test_at_least_one_reason_required(client):
    r = _raise_lt_ticket(client, reason_codes="")
    assert r.status_code == 400


def test_cda_can_acknowledge_and_resolve_with_mandatory_comment(client):
    r = _raise_lt_ticket(client)
    tid = r.json()["id"]

    ack = client.post("/cccapi/ticket/action", json={"id": tid, "action": "acknowledge"}, headers=CDA)
    assert ack.status_code == 200, ack.text

    bad_resolve = client.post("/cccapi/ticket/action", json={"id": tid, "action": "resolve", "resolution": ""}, headers=CDA)
    assert bad_resolve.status_code == 400

    ok_resolve = client.post("/cccapi/ticket/action",
                              json={"id": tid, "action": "resolve", "resolution": "Replaced fuse, powered back on"},
                              headers=CDA)
    assert ok_resolve.status_code == 200, ok_resolve.text


def test_lt_can_confirm_own_resolved_ticket_but_not_someone_elses(client):
    r = _raise_lt_ticket(client)
    tid = r.json()["id"]
    client.post("/cccapi/ticket/action", json={"id": tid, "action": "acknowledge"}, headers=CDA)
    client.post("/cccapi/ticket/action", json={"id": tid, "action": "resolve", "resolution": "Fixed it"}, headers=CDA)

    other_lt_confirm = client.post("/cccapi/ticket/action",
                                    json={"id": tid, "action": "confirm", "confirmed_by": "someone"}, headers=LT2)
    assert other_lt_confirm.status_code == 403

    own_confirm = client.post("/cccapi/ticket/action",
                               json={"id": tid, "action": "confirm", "confirmed_by": LT_USERNAME}, headers=LT)
    assert own_confirm.status_code == 200, own_confirm.text


def test_lt_can_reopen_own_closed_ticket(client):
    r = _raise_lt_ticket(client)
    tid = r.json()["id"]
    client.post("/cccapi/ticket/action", json={"id": tid, "action": "acknowledge"}, headers=CDA)
    client.post("/cccapi/ticket/action", json={"id": tid, "action": "resolve", "resolution": "Fixed it"}, headers=CDA)
    client.post("/cccapi/ticket/action", json={"id": tid, "action": "confirm", "confirmed_by": LT_USERNAME}, headers=LT)
    client.post("/cccapi/ticket/action", json={"id": tid, "action": "close", "resolution": "Fixed it"}, headers=CDA)

    reopen = client.post("/cccapi/ticket/action",
                          json={"id": tid, "action": "reopen", "note": "Broke again same day"}, headers=LT)
    assert reopen.status_code == 200, reopen.text


def test_lt_ticket_auto_escalates_to_cc_manager_after_cda_timeout(client):
    r = _raise_lt_ticket(client)
    tid = r.json()["id"]

    db = SessionLocal()
    t = db.query(Ticket).filter(Ticket.id == tid).first()
    t.assigned_at = datetime.datetime.now() - datetime.timedelta(minutes=120)
    db.commit()
    db.close()

    run_sla_sweep_once()

    detail = client.get(f"/cccapi/ticket/{tid}", headers=MGR).json()["ticket"]
    assert detail["escalated"] is True
    assert detail["escalated_to"] == "CC_MANAGER"

    dash = client.get("/cccapi/dashboard", headers=MGR).json()
    assert dash["today"]["escalated_from_field"] >= 1

    reassign = client.post("/cccapi/ticket/action",
                            json={"id": tid, "action": "reassign", "team": "SERVICE", "note": "Routing to Service"},
                            headers=MGR)
    assert reassign.status_code == 200, reassign.text


def test_photo_upload_rejects_bad_content_type(client):
    bad_file = ("note.txt", io.BytesIO(b"not a photo"), "text/plain")
    form = {
        "category": LT_CATEGORY,
        "reason_codes": "NO_POWER",
        "priority": "P1",
        "problem": "test",
    }
    r = client.post("/cccapi/lt/tickets", data=form, files={"photo": bad_file}, headers=LT)
    assert r.status_code == 400


def test_photo_upload_accepts_jpeg(client):
    fake_jpeg = ("photo.jpg", io.BytesIO(b"\xff\xd8\xff" + b"0" * 100), "image/jpeg")
    form = {
        "category": LT_CATEGORY,
        "reason_codes": "NO_POWER",
        "priority": "P1",
        "problem": "test with photo",
    }
    r = client.post("/cccapi/lt/tickets", data=form, files={"photo": fake_jpeg}, headers=LT)
    assert r.status_code == 200, r.text
    tid = r.json()["id"]
    db = SessionLocal()
    t = db.query(Ticket).filter(Ticket.id == tid).first()
    assert t.photo_path
    db.close()


def test_multiple_photos_upload_accepts_and_creates_attachments(client):
    from app.models.attachment import Attachment
    fake_jpeg = ("photo1.jpg", io.BytesIO(b"\xff\xd8\xff" + b"1" * 100), "image/jpeg")
    fake_png = ("photo2.png", io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"2" * 100), "image/png")
    form = {
        "category": LT_CATEGORY,
        "reason_codes": "NO_POWER",
        "priority": "P1",
        "problem": "test with multiple photos",
    }
    files = [
        ("photos", fake_jpeg),
        ("photos", fake_png),
    ]
    r = client.post("/cccapi/lt/tickets", data=form, files=files, headers=LT)
    assert r.status_code == 200, r.text
    tid = r.json()["id"]
    db = SessionLocal()
    t = db.query(Ticket).filter(Ticket.id == tid).first()
    assert t.photo_path is not None
    atts = db.query(Attachment).filter(Attachment.ticket_id == tid).all()
    assert len(atts) == 2
    filenames = [a.original_name for a in atts]
    assert "photo1.jpg" in filenames
    assert "photo2.png" in filenames
    db.close()


def test_lt_can_mark_resolved_ticket_as_not_resolved(client):
    from app.models.notification import Notification
    from app.models.event import Event

    r = _raise_lt_ticket(client)
    tid = r.json()["id"]

    client.post("/cccapi/ticket/action", json={"id": tid, "action": "acknowledge"}, headers=CDA)
    client.post("/cccapi/ticket/action", json={"id": tid, "action": "resolve", "resolution": "Replaced fuse"}, headers=CDA)

    # 1. Reject without note fails with 400
    r_empty = client.post("/cccapi/ticket/action", json={"id": tid, "action": "not_resolved", "note": ""}, headers=LT)
    assert r_empty.status_code == 400

    # 2. Another LT cannot reject this ticket
    r_other = client.post("/cccapi/ticket/action", json={"id": tid, "action": "not_resolved", "note": "Still broken"}, headers=LT2)
    assert r_other.status_code == 403

    # 3. Originating LT submits not_resolved with observations
    reason_text = "Fuse replaced but analyzer error 404 still displays on boot"
    r_nr = client.post("/cccapi/ticket/action", json={"id": tid, "action": "not_resolved", "note": reason_text}, headers=LT)
    assert r_nr.status_code == 200, r_nr.text

    db = SessionLocal()
    t = db.query(Ticket).filter(Ticket.id == tid).first()
    assert t.status == "IN_PROGRESS"
    assert t.resolved_at is None
    assert t.confirmed_by is None
    assert t.confirmed_at is None
    assert t.reopened == 1

    # Verify event was recorded
    ev = db.query(Event).filter(Event.ticket_id == tid, Event.action == "NOT_RESOLVED").first()
    assert ev is not None
    assert reason_text in ev.detail

    # Verify notification sent to CDA team
    notif = db.query(Notification).filter(
        Notification.ticket_id == tid,
        Notification.audience_role == LT_CDA_TEAM,
        Notification.type == "NOT_RESOLVED"
    ).first()
    assert notif is not None
    assert "rejected resolution" in notif.message
    assert reason_text in notif.message
    db.close()


def test_not_resolved_rejected_after_confirmation(client):
    r = _raise_lt_ticket(client)
    tid = r.json()["id"]

    client.post("/cccapi/ticket/action", json={"id": tid, "action": "acknowledge"}, headers=CDA)
    client.post("/cccapi/ticket/action", json={"id": tid, "action": "resolve", "resolution": "Cleaned connector"}, headers=CDA)
    # Confirm first (moves to CLOSURE_CONFIRMATION)
    client.post("/cccapi/ticket/action", json={"id": tid, "action": "confirm", "confirmed_by": LT_USERNAME}, headers=LT)

    # not_resolved must now be rejected because ticket is already confirmed
    r_nr = client.post("/cccapi/ticket/action", json={"id": tid, "action": "not_resolved", "note": "Trying to reject after confirm"}, headers=LT)
    assert r_nr.status_code == 409
    assert "not valid while the ticket is CLOSURE_CONFIRMATION" in r_nr.text

