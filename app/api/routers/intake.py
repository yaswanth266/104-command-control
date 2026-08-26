from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.core.config import ROUTING
from app.crud.crud_ticket import get_tat_map, create_ticket
from app.crud.crud_event import create_event
from app.services.notifications import notify_new_ticket
import datetime

router = APIRouter(prefix="/intake", tags=["intake"])

@router.post("")
def intake(body: dict, db: Session = Depends(get_db)):
    """Unattended intake used by the 104 field application (GOV_EHR) and other external systems."""
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
          
    r = ROUTING.get(cat, ROUTING["OTHER"])
    tat = get_tat_map(db).get(pr, 1440)
    now = datetime.datetime.now()

    detail = " | ".join([x for x in [body.get("detail"), body.get("context")] if x])
    problem = (body.get("subject") or "") + ((" - " + detail) if detail else "")

    # This endpoint serves the 104 field application; source is always GOV_EHR
    # regardless of what the caller sends, so downstream reporting can trust it.
    db_ticket = create_ticket(db, dict(
        source="GOV_EHR",
        mmu_vehicle=body.get("mmu_vehicle") or body.get("vehicle"),
        district=body.get("district"),
        caller_name=body.get("raised_by_name"),
        problem=problem,
        category=cat,
        priority=pr,
        team=r["team"],
        owner=r["owner"],
        status='ASSIGNED',
        tat_mins=tat,
        due_at=now + datetime.timedelta(minutes=tat),
        created_by=(body.get("escalated_by") or body.get("raised_by_name") or "GOV_EHR")[:64],
        assigned_at=now
    ))

    actor_info = {"username": (body.get("escalated_by") or "GOV_EHR"), "role": "SYSTEM"}
    create_event(db, db_ticket.id, actor_info, "CREATED", f"Auto-intake from GOV_EHR; classified {cat} -> {r['team']}",
                 new_status=db_ticket.status)
    notify_new_ticket(db, db_ticket)

    return {"ok": True, "ticket_no": db_ticket.ticket_no, "id": db_ticket.id, "team": r["team"], "priority": pr, "category": cat}
