from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.api.deps import get_current_user
from app.schemas.ticket import TicketIn, ActionIn, LogCallIn
from app.crud.crud_ticket import get_tickets, get_ticket, get_tat_map, create_ticket as insert_ticket
from app.models.ticket import Ticket
from app.crud.crud_event import get_events_by_ticket, create_event
from app.crud.crud_category import get_category_map, resolve_team, get_category
from app.crud.crud_reason import get_reason
from app.crud.crud_ticket_type import get_ticket_type
from app.crud.crud_team import get_team_map
from app.crud.crud_settings import get_sla_config, detect_vip
from app.crud.crud_attachment import create_attachment, get_attachments_by_ticket
from app.services.ticket_service import process_ticket_action
from app.services.formatting import enrich, get_chronic_breakdowns_map
from app.services.notifications import notify_new_ticket
from app.services.photos import save_ticket_attachment
from app.services.webhooks import dispatch_ticket_event
from app.core.config import PRIORITY
import datetime
import re

_PHONE_RE = re.compile(r"^[6-9]\d{9}$")

router = APIRouter(prefix="/ticket", tags=["tickets"])
collection_router = APIRouter(prefix="/tickets", tags=["tickets"])

def _can_view_ticket(ticket: Ticket, current_user: dict) -> bool:
    """Own team, the Global Team Executive/Call Taker, or the LT who raised
    it (mirrors ticket_service.py's is_originating_lt) - viewing-adjacent
    access, not a workflow-gated action, so attachments reuse this rather
    than ticket_service.py's stricter per-action permission checks."""
    role = current_user["role"]
    if role in ("CC_MANAGER", "CALL_TAKER") or role == ticket.team:
        return True
    return role == "LT" and ticket.created_by == current_user["username"]

@router.post("")
def create_ticket(b: TicketIn, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ("CALL_TAKER", "CC_MANAGER"):
        raise HTTPException(403, "Only the Call Taker or Global Team Executive may register a call")
    cat = b.category.strip().upper()
    r = resolve_team(db, cat, b.mandal_id)
    if r is None:
        raise HTTPException(400, "Unknown issue category")
    if b.priority not in PRIORITY:
        raise HTTPException(400, "Priority must be P1-P4")
    if not (b.problem or "").strip():
        raise HTTPException(400, "Nature of the problem is required")
    if not (b.caller_name or "").strip():
        raise HTTPException(400, "Caller name is required")
    if not _PHONE_RE.match((b.caller_phone or "").strip()):
        raise HTTPException(400, "Caller contact must be a valid 10-digit mobile number")

    is_vip, vip_reason = detect_vip(db, b.vip, b.problem, b.impact)
    priority = "P1" if is_vip else b.priority
    tat = get_tat_map(db).get(priority, 1440)
    now = datetime.datetime.now()

    ticket_type = (b.ticket_type or "INCIDENT").strip().upper()
    tt = get_ticket_type(db, ticket_type)
    if not tt or not tt.is_active:
        raise HTTPException(400, "Unknown or inactive ticket type")

    subcat = None
    if b.subcategory_code:
        subcat = get_reason(db, b.subcategory_code.strip().upper())
        if not subcat or not subcat.is_active or subcat.category_code != cat:
            raise HTTPException(400, "That sub-category does not belong to the selected category")

    cat_row = get_category(db, cat)

    db_ticket = insert_ticket(db, dict(
        source='CALL',
        mmu_vehicle=b.mmu_vehicle,
        vehicle_id=b.vehicle_id,
        district=b.district,
        district_id=b.district_id,
        mandal_id=b.mandal_id,
        zone_id=r["zone_id"],
        machine_id=b.machine_id,
        location=b.location,
        caller_name=b.caller_name,
        caller_phone=b.caller_phone,
        called_at=now,
        equipment=b.equipment,
        problem=b.problem,
        error_code=b.error_code,
        impact=b.impact,
        category=cat,
        ticket_type=ticket_type,
        subcategory_code=subcat.code if subcat else None,
        category_label_snapshot=cat_row.label if cat_row else None,
        subcategory_label_snapshot=subcat.label if subcat else None,
        priority=priority,
        vip=is_vip,
        team=r["team"],
        owner=r["owner"],
        status='ASSIGNED',
        tat_mins=tat,
        due_at=now + datetime.timedelta(minutes=tat),
        created_by=current_user["username"],
        assigned_at=now
    ))

    detail = f"Call registered; classified {cat} -> {r['team']} ({priority})"
    if r["zone_id"]:
        detail += f" [zone-routed]"
    if is_vip:
        detail += f" - VIP escalation ({vip_reason})"
    create_event(db, db_ticket.id, current_user, "CREATED", detail, new_status=db_ticket.status)
    notify_new_ticket(db, db_ticket)
    dispatch_ticket_event(db, "ticket.created", db_ticket, current_user["username"])

    return {"ok": True, "ticket_no": db_ticket.ticket_no, "id": db_ticket.id, "team": r["team"], "owner": r["owner"],
            "tat_mins": tat, "priority": priority, "vip": is_vip}

@collection_router.get("")
def list_tickets(status: str = "", team: str = "", scope: str = "", q_: str = "",
                 priority: str = "", category: str = "", mmu_vehicle: str = "", district: str = "",
                 district_id: Optional[int] = None, mandal_id: Optional[int] = None,
                 date_from: str = "", date_to: str = "", time_from: str = "", time_to: str = "", shift: str = "",
                 page: int = 1, page_size: int = 50,
                 sort_by: str = "", sort_desc: bool = False,
                 db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    tickets, total = get_tickets(db, current_user, status=status, team=team, scope=scope, q=q_,
                                  priority=priority, category=category, mmu_vehicle=mmu_vehicle, district=district,
                                  district_id=district_id, mandal_id=mandal_id,
                                  date_from=date_from, date_to=date_to, time_from=time_from, time_to=time_to, shift=shift,
                                  page=page, page_size=page_size, sort_by=sort_by, sort_desc=sort_desc)
    category_map, team_map, sla_cfg = get_category_map(db), get_team_map(db), get_sla_config(db)
    chronic_map = get_chronic_breakdowns_map(db)
    return {"count": len(tickets), "total": total, "page": page, "page_size": page_size,
            "rows": [enrich(t, category_map, team_map, sla_cfg, chronic_map) for t in tickets]}

@router.get("/{tid}")
def get_one_ticket(tid: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    t = get_ticket(db, tid)
    if not t:
        raise HTTPException(404, "Ticket not found")
    if current_user["role"] not in ("CC_MANAGER", "CALL_TAKER") and t.team != current_user["role"]:
        raise HTTPException(403, "This ticket is not assigned to your department")

    events = get_events_by_ticket(db, tid)
    evs_out = []
    for e in events:
        ev_dict = {c.name: getattr(e, c.name) for c in e.__table__.columns}
        if isinstance(ev_dict.get("at"), datetime.datetime):
            ev_dict["at"] = ev_dict["at"].strftime("%Y-%m-%d %H:%M")
        evs_out.append(ev_dict)

    enriched = enrich(t, get_category_map(db), get_team_map(db), get_sla_config(db), get_chronic_breakdowns_map(db))
    return {"ticket": enriched, "events": evs_out}

@router.post("/action")
def ticket_action(b: ActionIn, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    ticket = get_ticket(db, b.id)
    if not ticket:
        raise HTTPException(404, "Ticket not found")

    return process_ticket_action(db, ticket, current_user, b)

@router.get("/by-number/{ticket_no}")
def get_ticket_by_number(ticket_no: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """Backs Register Call's 'already reported through the LT portal?' lookup
    - a Call Taker looks up an LT's portal ticket by its human-readable number
    (never the raw id) so a follow-up call can be linked to it instead of
    spawning a duplicate ticket."""
    if current_user["role"] not in ("CALL_TAKER", "CC_MANAGER"):
        raise HTTPException(403, "Only the Call Taker or Global Team Executive may look up a ticket this way")
    t = db.query(Ticket).filter(Ticket.ticket_no == ticket_no.strip().upper()).first()
    if not t:
        raise HTTPException(404, "No ticket found with that number")
    if t.source != "LT_PORTAL":
        raise HTTPException(400, "That ticket wasn't raised through the LT portal")
    return enrich(t, get_category_map(db), get_team_map(db), get_sla_config(db))

@router.post("/{tid}/log-call")
def log_call(tid: int, b: LogCallIn, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """A follow-up phone call about an issue already raised through the LT
    portal - logs an event on the EXISTING ticket rather than creating a
    second one, so the two never compete for the same SLA clock."""
    if current_user["role"] not in ("CALL_TAKER", "CC_MANAGER"):
        raise HTTPException(403, "Only the Call Taker or Global Team Executive may log a call")
    t = get_ticket(db, tid)
    if not t:
        raise HTTPException(404, "Ticket not found")
    if t.source != "LT_PORTAL":
        raise HTTPException(400, "That ticket wasn't raised through the LT portal")
    detail = "Follow-up call received"
    if b.caller_name or b.caller_phone:
        detail += f" from {b.caller_name or 'unknown caller'}" + (f" ({b.caller_phone})" if b.caller_phone else "")
    if b.note:
        detail += f": {b.note}"
    create_event(db, t.id, current_user, "CALL_RECEIVED", detail)
    dispatch_ticket_event(db, "ticket.note_added", t, current_user["username"], note=detail)
    return {"ok": True, "ticket_no": t.ticket_no, "id": t.id}

@router.post("/{tid}/attachments")
def upload_attachment(tid: int, note: str = Form(""), file: UploadFile = File(...),
                       db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """Supporting evidence (photos, screenshots, reports) against a ticket at
    any stage - optional, not tied to any one workflow action. See
    save_ticket_attachment for the allowed types/size cap."""
    t = get_ticket(db, tid)
    if not t:
        raise HTTPException(404, "Ticket not found")
    if not _can_view_ticket(t, current_user):
        raise HTTPException(403, "This ticket is not assigned to your department")
    saved = save_ticket_attachment(file)
    a = create_attachment(db, tid, saved["filename"], file.filename, file.content_type, saved["size_bytes"],
                           current_user["username"], current_user["role"], note.strip() or None)
    detail = f"Attached {file.filename}" + (f": {note}" if note else "")
    create_event(db, tid, current_user, "ATTACHMENT_ADDED", detail)
    dispatch_ticket_event(db, "ticket.note_added", t, current_user["username"], note=detail)
    return {"id": a.id, "filename": a.filename, "original_name": a.original_name, "content_type": a.content_type,
            "size_bytes": a.size_bytes, "uploaded_by": a.uploaded_by, "note": a.note}

@router.get("/{tid}/attachments")
def list_attachments(tid: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    t = get_ticket(db, tid)
    if not t:
        raise HTTPException(404, "Ticket not found")
    if not _can_view_ticket(t, current_user):
        raise HTTPException(403, "This ticket is not assigned to your department")
    rows = get_attachments_by_ticket(db, tid)
    out = [{"id": a.id, "filename": a.filename, "original_name": a.original_name, "content_type": a.content_type,
             "size_bytes": a.size_bytes, "uploaded_by": a.uploaded_by, "uploaded_by_role": a.uploaded_by_role,
             "uploaded_at": a.uploaded_at.strftime("%Y-%m-%d %H:%M") if a.uploaded_at else None, "note": a.note}
            for a in rows]
    if t.photo_path:
        out.insert(0, {
            "id": 0, "filename": t.photo_path, "original_name": "LT_Photo.jpg", "content_type": "image/jpeg",
            "size_bytes": 0, "uploaded_by": t.created_by, "uploaded_by_role": "LT",
            "uploaded_at": t.created_at.strftime("%Y-%m-%d %H:%M") if t.created_at else None, "note": "Initial ticket photo"
        })
    return out
