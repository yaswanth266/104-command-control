from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.core.config import ROUTING
from app.crud.crud_ticket import get_tat_map, get_next_ticket_no
from app.crud.crud_event import create_event
from app.models.ticket import Ticket
import datetime

router = APIRouter(prefix="/intake", tags=["intake"])

@router.post("")
def intake(body: dict, request: Request, db: Session = Depends(get_db)):
    """Unattended intake used by external systems."""
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
    no = get_next_ticket_no(db)
    
    detail = " | ".join([x for x in [body.get("detail"), body.get("context")] if x])
    problem = (body.get("subject") or "") + ((" - " + detail) if detail else "")
    
    db_ticket = Ticket(
        ticket_no=no,
        source=(body.get("source") or "SYSTEM")[:24],
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
        due_at=datetime.datetime.now() + datetime.timedelta(minutes=tat),
        created_by=(body.get("escalated_by") or body.get("raised_by_name") or "system")[:64],
        assigned_at=datetime.datetime.now()
    )
    
    db.add(db_ticket)
    db.commit()
    db.refresh(db_ticket)
    
    actor_info = {"username": (body.get("escalated_by") or "system"), "role": "SYSTEM"}
    create_event(db, db_ticket.id, actor_info, "CREATED", f"Auto-intake from {body.get('source') or 'SYSTEM'}; classified {cat} -> {r['team']}")
    
    return {"ok": True, "ticket_no": no, "id": db_ticket.id, "team": r["team"], "priority": pr, "category": cat}
