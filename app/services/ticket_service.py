import datetime
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.ticket import Ticket
from app.crud.crud_event import create_event
from app.core.config import TEAMS, PRIORITY
from app.crud.crud_ticket import get_tat_map
from app.schemas.ticket import ActionIn

def process_ticket_action(db: Session, ticket: Ticket, user: dict, action_in: ActionIn):
    act = action_in.action.lower()
    role = user["role"]
    own = (role == ticket.team) or role in ("CC_MANAGER", "CALL_TAKER")
    
    def setf(action_name: str, detail: str, **kwargs):
        for k, v in kwargs.items():
            setattr(ticket, k, v)
        db.commit()
        db.refresh(ticket)
        create_event(db, ticket.id, user, action_name, detail)
        
    now = datetime.datetime.now()

    if act == "acknowledge":
        if not own:
            raise HTTPException(403, "Only the assigned team may acknowledge")
        if ticket.status not in ("NEW", "ASSIGNED"):
            raise HTTPException(409, "Ticket is already acknowledged")
        setf("ACKNOWLEDGED", f"Acknowledged by {user['name']} ({TEAMS.get(ticket.team, ticket.team)})",
             status='ACKNOWLEDGED', acknowledged_at=now, first_response_at=ticket.first_response_at or now, assignee=user['username'])
             
    elif act == "start":
        if not own:
            raise HTTPException(403, "Only the assigned team may work this ticket")
        setf("IN_PROGRESS", action_in.note or "Investigation started",
             status='IN_PROGRESS', first_response_at=ticket.first_response_at or now, assignee=ticket.assignee or user['username'])
             
    elif act == "update":
        if not own:
            raise HTTPException(403, "Only the assigned team may update this ticket")
        
        detail_parts = []
        if action_in.diagnosis: detail_parts.append(f"Diagnosis: {action_in.diagnosis}")
        if action_in.action_taken: detail_parts.append(f"Action: {action_in.action_taken}")
        if action_in.root_cause: detail_parts.append(f"Root cause: {action_in.root_cause}")
        if action_in.parts: detail_parts.append(f"Parts: {action_in.parts}")
        detail = "; ".join(detail_parts) or "Progress update"
        
        new_status = 'IN_PROGRESS' if ticket.status in ('NEW', 'ASSIGNED', 'ACKNOWLEDGED') else ticket.status
        
        setf("UPDATED", detail,
             diagnosis=action_in.diagnosis or ticket.diagnosis,
             action_taken=action_in.action_taken or ticket.action_taken,
             root_cause=action_in.root_cause or ticket.root_cause,
             parts=action_in.parts or ticket.parts,
             status=new_status)
             
    elif act == "pending":
        if not own:
            raise HTTPException(403, "Only the assigned team may hold this ticket")
        if not (action_in.pending_reason or "").strip():
            raise HTTPException(400, "SOP: a pending/waiting ticket must record the reason")
        setf("PENDING", f"Waiting: {action_in.pending_reason}",
             status='PENDING', pending_reason=action_in.pending_reason)
             
    elif act == "resolve":
        if not own:
            raise HTTPException(403, "Only the assigned team may resolve")
        if not (action_in.resolution or "").strip():
            raise HTTPException(400, "SOP: resolution details are mandatory before resolving")
        setf("RESOLVED", f"Resolution: {action_in.resolution}",
             status='RESOLVED', resolved_at=now, resolution=action_in.resolution,
             diagnosis=action_in.diagnosis or ticket.diagnosis,
             action_taken=action_in.action_taken or ticket.action_taken,
             root_cause=action_in.root_cause or ticket.root_cause,
             parts=action_in.parts or ticket.parts)
             
    elif act == "confirm":
        if ticket.status not in ("RESOLVED",):
            raise HTTPException(409, "SOP: confirmation applies to a resolved ticket (reopen it first)")
        if not (action_in.confirmed_by or "").strip():
            raise HTTPException(400, "SOP: record who at the MMU/field team confirmed the resolution")
        setf("CONFIRMED", f"Resolution confirmed with {action_in.confirmed_by}",
             status='CLOSURE_CONFIRMATION', confirmed_by=action_in.confirmed_by, confirmed_at=now)
             
    elif act == "close":
        if ticket.status not in ("RESOLVED", "CLOSURE_CONFIRMATION"):
            raise HTTPException(409, "SOP: a ticket may only be closed after resolution (and confirmation where applicable)")
        if not (ticket.resolution or action_in.resolution):
            raise HTTPException(400, "SOP: resolution must be documented before closure")
        breached = bool(ticket.due_at and now > ticket.due_at)
        setf("CLOSED", f"Closed by {user['name']}{' (TAT BREACHED)' if breached else ' within TAT'}",
             status='CLOSED', closed_at=now, breached=breached, resolution=action_in.resolution or ticket.resolution)
             
    elif act == "escalate":
        setf("ESCALATED", f"Escalated to CC Manager: {action_in.note or 'TAT risk'}",
             escalated=True, escalated_at=now, escalated_to='CC_MANAGER', escalation_note=action_in.note or "TAT risk")
             
    elif act == "reassign":
        if role not in ("CC_MANAGER", "CALL_TAKER"):
            raise HTTPException(403, "Only the CC Manager or Call Taker may re-route a ticket")
        nt = (action_in.team or "").upper()
        if nt not in TEAMS:
            raise HTTPException(400, "Unknown team")
        setf("REASSIGNED", f"Re-routed to {TEAMS[nt]}. {action_in.note or ''}",
             team=nt, owner=TEAMS[nt], status='ASSIGNED', assigned_at=now, assignee=None)
             
    elif act == "repriority":
        if role not in ("CC_MANAGER", "CALL_TAKER"):
            raise HTTPException(403, "Only the CC Manager or Call Taker may change priority")
        if action_in.priority not in PRIORITY:
            raise HTTPException(400, "Priority must be P1-P4")
        nt_mins = get_tat_map(db).get(action_in.priority, 1440)
        setf("PRIORITY", f"Priority set to {action_in.priority} (TAT {nt_mins} min)",
             priority=action_in.priority, tat_mins=nt_mins, due_at=ticket.created_at + datetime.timedelta(minutes=nt_mins))
             
    elif act == "reopen":
        if role not in ("CC_MANAGER", "CALL_TAKER"):
            raise HTTPException(403, "Only the CC Manager or Call Taker may reopen")
        setf("REOPENED", action_in.note or "Reopened",
             status='IN_PROGRESS', closed_at=None, reopened=ticket.reopened + 1)
    else:
        raise HTTPException(400, "Unknown action")
        
    return {"ok": True, "id": action_in.id, "action": act}
