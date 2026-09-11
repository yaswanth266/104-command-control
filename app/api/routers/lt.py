import json
import datetime
from typing import Optional
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.api.deps import get_current_user
from app.models.ticket import Ticket
from app.crud.crud_ticket import create_ticket as insert_ticket
from app.services.sla_engine import resolve_ticket_sla
from app.crud.crud_event import create_event
from app.crud.crud_attachment import create_attachment
from app.crud.crud_category import resolve_team, get_category, get_category_map
from app.crud.crud_team import get_team_map
from app.crud.crud_user import get_user_by_username
from app.crud.crud_vehicle import get_vehicle
from app.crud.crud_geo import get_district
from app.crud.crud_reason import get_reason
from app.crud.crud_settings import get_sla_config
from app.services.formatting import enrich
from app.services.notifications import notify_new_ticket
from app.services.photos import save_ticket_photo
from app.services.photos import save_ticket_photo, save_ticket_attachment
from app.services.webhooks import dispatch_ticket_event
from app.services.hierarchy import resolve_and_apply

# Isolated from the main ticket router (tickets.py), same as intake.py is
# isolated for its own caller type - an LT never touches the department-facing
# queue endpoints; this router is their entire world.
router = APIRouter(prefix="/lt", tags=["lt"])

def _require_lt(current_user: dict):
    if current_user["role"] != "LT":
        raise HTTPException(403, "This endpoint is for Lab Technicians only")

def _parse_reason_codes(raw: str) -> list:
    raw = (raw or "").strip()
    if not raw:
        return []
    try:
        codes = json.loads(raw) if raw.startswith("[") else [x.strip() for x in raw.split(",")]
    except Exception:
        raise HTTPException(400, "reason_codes must be a JSON list or comma-separated codes")
    return [str(c).strip().upper() for c in codes if str(c).strip()]

@router.post("/tickets")
def create_lt_ticket(
    category: str = Form(...),
    reason_codes: str = Form(""),
    machine_id: Optional[int] = Form(None),
    priority: str = Form("P2"),
    problem: str = Form(""),
    photo: Optional[UploadFile] = File(None),
    photos: Optional[List[UploadFile]] = File(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    _require_lt(current_user)
    lt_user = get_user_by_username(db, current_user["username"])
    if not lt_user:
        raise HTTPException(404, "User profile not found")
    if not lt_user.district_id or not lt_user.mandal_id:
        raise HTTPException(400, "Your profile has no District/Mandal set - ask the CC Manager to "
                                  "configure it before you can raise a ticket")

    cat = (category or "").strip().upper()
    c = get_category(db, cat)
    if not c or not c.is_active or not c.visible_to_lt:
        raise HTTPException(400, "Unknown or unavailable issue category")

    codes = _parse_reason_codes(reason_codes)
    if not codes:
        raise HTTPException(400, "Select at least one reason")
    reasons = []
    for code in codes:
        r = get_reason(db, code)
        if not r or not r.is_active or r.category_code != cat:
            raise HTTPException(400, f"'{code}' is not a valid reason for this category")
        reasons.append(r)

    if priority not in ("P1", "P2"):
        raise HTTPException(400, "Priority must be P1 or P2 for field-raised tickets")

    route = resolve_team(db, cat, lt_user.mandal_id)
    if route is None:
        raise HTTPException(400, "Unknown issue category")

    all_uploads = []
    if photos:
        for p in photos:
            if p and p.filename:
                all_uploads.append(p)
    if photo and photo.filename and photo not in all_uploads:
        all_uploads.insert(0, photo)

    photo_path = None
    if all_uploads:
        photo_path = save_ticket_photo(all_uploads[0])

    vehicle = get_vehicle(db, lt_user.vehicle_id) if lt_user.vehicle_id else None
    district = get_district(db, lt_user.district_id)
    now = datetime.datetime.now()
    sla = resolve_ticket_sla(db, "INCIDENT", cat, reasons[0].code, priority, now=now)
    problem_text = (problem or "").strip() or "; ".join(r.label for r in reasons)

    db_ticket = insert_ticket(db, dict(
        source='LT_PORTAL',
        mmu_vehicle=vehicle.registration_no if vehicle else None,
        vehicle_id=lt_user.vehicle_id,
        district=district.name if district else None,
        district_id=lt_user.district_id,
        mandal_id=lt_user.mandal_id,
        zone_id=route["zone_id"],
        machine_id=machine_id,
        reason_codes=codes,
        photo_path=photo_path,
        problem=problem_text,
        category=cat,
        # LT field reports are always Incidents; the (possibly several)
        # selected reasons are still kept in reason_codes for backward
        # compatibility, with the first one snapshotted as the ticket's
        # single Sub-Category, consistent with the other intake paths.
        ticket_type="INCIDENT",
        subcategory_code=reasons[0].code,
        category_label_snapshot=c.label,
        subcategory_label_snapshot=reasons[0].label,
        priority=priority,
        original_priority=priority,
        team=route["team"],
        owner=route["owner"],
        status='ASSIGNED',
        tat_mins=sla["tat_mins"],
        due_at=sla["due_at"],
        sla_policy_code=sla["policy_code"],
        response_due_at=sla["response_due_at"],
        created_by=current_user["username"],
        assigned_at=now,
    ))

    # Record all uploaded images as permanent attachments
    for idx, p in enumerate(all_uploads):
        try:
            if idx == 0 and photo_path:
                create_attachment(
                    db=db,
                    ticket_id=db_ticket.id,
                    filename=photo_path,
                    original_name=p.filename,
                    content_type=p.content_type or "image/jpeg",
                    size_bytes=getattr(p, "size", 0) or 0,
                    uploaded_by=current_user["username"],
                    uploaded_by_role="LT",
                    note=f"Initial field photo #{idx+1}"
                )
            else:
                saved = save_ticket_attachment(p)
                create_attachment(
                    db=db,
                    ticket_id=db_ticket.id,
                    filename=saved["filename"],
                    original_name=p.filename,
                    content_type=p.content_type or "image/jpeg",
                    size_bytes=saved["size_bytes"],
                    uploaded_by=current_user["username"],
                    uploaded_by_role="LT",
                    note=f"Initial field photo #{idx+1}"
                )
        except Exception:
            pass

    create_event(db, db_ticket.id, current_user, "CREATED",
                 f"Reported from the field by {current_user['name']}; classified {cat} -> {route['team']}"
                 + (f" [zone-routed]" if route["zone_id"] else ""),
                 new_status=db_ticket.status)
    notify_new_ticket(db, db_ticket)
    dispatch_ticket_event(db, "ticket.created", db_ticket, current_user["username"])
    resolve_and_apply(db, db_ticket)

    return {"ok": True, "ticket_no": db_ticket.ticket_no, "id": db_ticket.id, "team": route["team"], "priority": priority}

@router.get("/tickets")
def list_lt_tickets(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """The LT's own submission history only - a dedicated lightweight query
    rather than bolting another role-branch onto crud_ticket.get_tickets,
    which already carries department-team scoping logic that doesn't apply
    to a field caller who owns no team."""
    _require_lt(current_user)
    rows = (db.query(Ticket)
              .filter(Ticket.created_by == current_user["username"], Ticket.source == "LT_PORTAL")
              .order_by(Ticket.created_at.desc())
              .all())
    category_map, team_map, sla_cfg = get_category_map(db), get_team_map(db), get_sla_config(db)
    return [enrich(t, category_map, team_map, sla_cfg) for t in rows]
