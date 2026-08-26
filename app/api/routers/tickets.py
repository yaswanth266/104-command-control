from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.api.deps import get_current_user
from app.schemas.ticket import TicketIn, ActionIn
from app.crud.crud_ticket import get_tickets, get_ticket, get_tat_map, create_ticket as insert_ticket
from app.crud.crud_event import get_events_by_ticket, create_event
from app.services.ticket_service import process_ticket_action
from app.services.formatting import enrich
from app.services.notifications import notify_new_ticket
from app.core.config import ROUTING, PRIORITY
import datetime

router = APIRouter(prefix="/ticket", tags=["tickets"])
collection_router = APIRouter(prefix="/tickets", tags=["tickets"])

@router.post("")
def create_ticket(b: TicketIn, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ("CALL_TAKER", "CC_MANAGER"):
        raise HTTPException(403, "Only the Call Taker or CC Manager may register a call")
    cat = b.category.strip().upper()
    if cat not in ROUTING:
        raise HTTPException(400, "Unknown issue category")
    if b.priority not in PRIORITY:
        raise HTTPException(400, "Priority must be P1-P4")
    if not (b.problem or "").strip():
        raise HTTPException(400, "Nature of the problem is required")
        
    r = ROUTING[cat]
    tat = get_tat_map(db).get(b.priority, 1440)
    now = datetime.datetime.now()

    db_ticket = insert_ticket(db, dict(
        source='CALL',
        mmu_vehicle=b.mmu_vehicle,
        district=b.district,
        location=b.location,
        caller_name=b.caller_name,
        caller_phone=b.caller_phone,
        called_at=now,
        equipment=b.equipment,
        problem=b.problem,
        error_code=b.error_code,
        impact=b.impact,
        category=cat,
        priority=b.priority,
        team=r["team"],
        owner=r["owner"],
        status='ASSIGNED',
        tat_mins=tat,
        due_at=now + datetime.timedelta(minutes=tat),
        created_by=current_user["username"],
        assigned_at=now
    ))

    create_event(db, db_ticket.id, current_user, "CREATED", f"Call registered; classified {cat} -> {r['team']} ({b.priority})",
                 new_status=db_ticket.status)
    notify_new_ticket(db, db_ticket)

    return {"ok": True, "ticket_no": db_ticket.ticket_no, "id": db_ticket.id, "team": r["team"], "owner": r["owner"], "tat_mins": tat}

@collection_router.get("")
def list_tickets(status: str = "", team: str = "", scope: str = "", q_: str = "",
                 priority: str = "", category: str = "", mmu_vehicle: str = "", district: str = "",
                 date_from: str = "", date_to: str = "", page: int = 1, page_size: int = 50,
                 db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    tickets, total = get_tickets(db, current_user, status=status, team=team, scope=scope, q=q_,
                                  priority=priority, category=category, mmu_vehicle=mmu_vehicle, district=district,
                                  date_from=date_from, date_to=date_to, page=page, page_size=page_size)
    return {"count": len(tickets), "total": total, "page": page, "page_size": page_size, "rows": [enrich(t) for t in tickets]}

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
        
    return {"ticket": enrich(t), "events": evs_out}

@router.post("/action")
def ticket_action(b: ActionIn, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    ticket = get_ticket(db, b.id)
    if not ticket:
        raise HTTPException(404, "Ticket not found")
    
    return process_ticket_action(db, ticket, current_user, b)
