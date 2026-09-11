from typing import Optional
import hmac
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.core.config import INTAKE_API_KEY
from app.crud.crud_ticket import create_ticket
from app.crud.crud_category import resolve_team, get_category
from app.crud.crud_settings import detect_vip
from app.crud.crud_ticket_type import get_ticket_type
from app.crud.crud_event import create_event
from app.services.notifications import notify_new_ticket
from app.services.webhooks import dispatch_ticket_event
from app.services.sla_engine import resolve_ticket_sla
from app.services.hierarchy import resolve_and_apply
import datetime

router = APIRouter(prefix="/intake", tags=["intake"])

def _check_intake_key(x_intake_key: Optional[str]):
    if not INTAKE_API_KEY:
        raise HTTPException(503, "Intake is not configured: set CCC_INTAKE_KEY")
    if not x_intake_key or not hmac.compare_digest(x_intake_key, INTAKE_API_KEY):
        raise HTTPException(401, "Invalid or missing intake key")

def _safe_int(v):
    """body is an untrusted raw dict (no Pydantic coercion) - a field-app
    sending a stringly-typed id shouldn't 500 the insert."""
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None

@router.post("")
def intake(body: dict, db: Session = Depends(get_db), x_intake_key: Optional[str] = Header(None)):
    """Unattended intake used by the 104 field application (GOV_EHR) and other external systems.
    Requires the X-Intake-Key header (see CCC_INTAKE_KEY) - coordinate that value
    with whoever operates the field-app/EHR side before deploying this."""
    _check_intake_key(x_intake_key)
    cat = (body.get("category") or "").strip().upper()
    _MAP = {"DEVICE": "MACHINE", "MACHINE": "MACHINE", "INSTRUMENT": "MACHINE", "QC": "QC", "QUALITY": "QC",
            "APP": "APPLICATION", "APPLICATION": "APPLICATION", "SOFTWARE": "APPLICATION",
            "TECHNICAL": "TECHNICAL", "LIS": "LIS", "NETWORK": "NETWORK", "DATA": "LIS",
            "FIELD": "FIELD", "OPERATIONS": "FIELD", "FLEET": "FLEET", "VEHICLE": "FLEET",
            "SUPPLY": "FIELD", "ABHA": "APPLICATION", "GENERAL": "OTHER"}
    cat = _MAP.get(cat, "OTHER")
    
    pr = (body.get("priority") or "").strip().upper()
    pr = {"CRITICAL": "P1", "HIGH": "P2", "NORMAL": "P3", "MEDIUM": "P3", "LOW": "P4",
          "P1": "P1", "P2": "P2", "P3": "P3", "P4": "P4"}.get(pr, "P3")
          
    mandal_id = _safe_int(body.get("mandal_id"))
    r = resolve_team(db, cat, mandal_id) or resolve_team(db, "OTHER", mandal_id)
    now = datetime.datetime.now()

    # ticket_type is optional and best-effort here - an external caller that
    # doesn't know our taxonomy still gets a ticket, just classified INCIDENT.
    ticket_type = (body.get("ticket_type") or "INCIDENT").strip().upper()
    tt = get_ticket_type(db, ticket_type)
    if not tt or not tt.is_active:
        ticket_type = "INCIDENT"
    cat_row = get_category(db, cat) or get_category(db, "OTHER")

    detail = " | ".join([x for x in [body.get("detail"), body.get("context")] if x])
    problem = (body.get("subject") or "") + ((" - " + detail) if detail else "")

    is_vip, vip_reason = detect_vip(db, bool(body.get("vip")), problem, body.get("impact"))
    pr = "P1" if is_vip else pr
    sla = resolve_ticket_sla(db, ticket_type, cat, None, pr, now=now)

    # This endpoint serves the 104 field application; source is always GOV_EHR
    # regardless of what the caller sends, so downstream reporting can trust it.
    db_ticket = create_ticket(db, dict(
        source="GOV_EHR",
        mmu_vehicle=body.get("mmu_vehicle") or body.get("vehicle"),
        vehicle_id=_safe_int(body.get("vehicle_id")),
        district=body.get("district"),
        district_id=_safe_int(body.get("district_id")),
        mandal_id=mandal_id,
        zone_id=r["zone_id"],
        caller_name=body.get("raised_by_name"),
        problem=problem,
        category=cat,
        ticket_type=ticket_type,
        category_label_snapshot=cat_row.label if cat_row else None,
        priority=pr,
        original_priority=pr,
        vip=is_vip,
        team=r["team"],
        owner=r["owner"],
        status='ASSIGNED',
        tat_mins=sla["tat_mins"],
        due_at=sla["due_at"],
        sla_policy_code=sla["policy_code"],
        response_due_at=sla["response_due_at"],
        created_by=(body.get("escalated_by") or body.get("raised_by_name") or "GOV_EHR")[:64],
        assigned_at=now
    ))

    actor_info = {"username": (body.get("escalated_by") or "GOV_EHR"), "role": "SYSTEM"}
    ev_detail = f"Auto-intake from GOV_EHR; classified {cat} -> {r['team']}"
    if is_vip:
        ev_detail += f" - VIP escalation ({vip_reason})"
    create_event(db, db_ticket.id, actor_info, "CREATED", ev_detail, new_status=db_ticket.status)
    notify_new_ticket(db, db_ticket)
    # Outbound webhook (see app/services/webhooks.py): reflects the ticket back
    # out using CCC's OWN category/priority master data (cat/pr above, already
    # mapped from whatever terminology this external caller used), so a
    # subscribed external system consumes CCC's classification directly rather
    # than maintaining its own inbound mapping.
    dispatch_ticket_event(db, "ticket.created", db_ticket, actor_info["username"])
    resolve_and_apply(db, db_ticket)

    return {"ok": True, "ticket_no": db_ticket.ticket_no, "id": db_ticket.id, "team": r["team"], "priority": pr, "category": cat, "vip": is_vip}
