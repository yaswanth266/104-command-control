import datetime
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.ticket import Ticket
from app.crud.crud_event import create_event
from app.core.config import TEAMS, PRIORITY
from app.crud.crud_ticket import get_tat_map
from app.schemas.ticket import ActionIn
from app.services.notifications import notify_escalated

# Centralized workflow contract: the ticket statuses each lifecycle action may
# be applied from, and the status it lands on. This is the single place that
# encodes "Registered -> Assigned -> Acknowledged -> Investigated -> Resolved ->
# MMU Confirmed -> Closed" so no action can skip or reorder a mandatory stage.
ALLOWED_FROM = {
    "acknowledge": {"NEW", "ASSIGNED"},
    "start":       {"ACKNOWLEDGED", "IN_PROGRESS", "PENDING"},
    "pending":     {"ACKNOWLEDGED", "IN_PROGRESS", "PENDING"},
    "resolve":     {"ACKNOWLEDGED", "IN_PROGRESS", "PENDING"},
    "confirm":     {"RESOLVED"},
    "close":       {"CLOSURE_CONFIRMATION"},
    "reopen":      {"CLOSED"},
}
TARGET_STATUS = {
    "acknowledge": "ACKNOWLEDGED",
    "start":       "IN_PROGRESS",
    "pending":     "PENDING",
    "resolve":     "RESOLVED",
    "confirm":     "CLOSURE_CONFIRMATION",
    "close":       "CLOSED",
    "reopen":      "IN_PROGRESS",
}

def _require_transition(ticket: Ticket, action: str):
    allowed = ALLOWED_FROM[action]
    if ticket.status not in allowed:
        raise HTTPException(409, f"SOP: '{action}' is not valid while the ticket is {ticket.status}")

def process_ticket_action(db: Session, ticket: Ticket, user: dict, action_in: ActionIn):
    act = action_in.action.lower()
    role = user["role"]
    own = (role == ticket.team) or role in ("CC_MANAGER", "CALL_TAKER")

    def setf(action_name: str, detail: str, **kwargs):
        old_status = ticket.status
        for k, v in kwargs.items():
            setattr(ticket, k, v)
        db.commit()
        db.refresh(ticket)
        new_status = ticket.status
        create_event(db, ticket.id, user, action_name, detail,
                     old_status=old_status if old_status != new_status else None,
                     new_status=new_status if old_status != new_status else None)

    now = datetime.datetime.now()

    if act == "acknowledge":
        if not own:
            raise HTTPException(403, "Only the assigned team may acknowledge")
        _require_transition(ticket, act)
        setf("ACKNOWLEDGED", f"Acknowledged by {user['name']} ({TEAMS.get(ticket.team, ticket.team)})",
             status=TARGET_STATUS[act], acknowledged_at=now, first_response_at=ticket.first_response_at or now, assignee=user['username'])

    elif act == "start":
        if not own:
            raise HTTPException(403, "Only the assigned team may work this ticket")
        _require_transition(ticket, act)
        setf("IN_PROGRESS", action_in.note or "Investigation started",
             status=TARGET_STATUS[act], first_response_at=ticket.first_response_at or now, assignee=ticket.assignee or user['username'])

    elif act == "update":
        if not own:
            raise HTTPException(403, "Only the assigned team may update this ticket")
        if ticket.status == "CLOSED":
            raise HTTPException(409, "SOP: a closed ticket must be reopened before it can be edited")

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
        _require_transition(ticket, act)
        if not (action_in.pending_reason or "").strip():
            raise HTTPException(400, "SOP: a pending/waiting ticket must record the reason")
        setf("PENDING", f"Waiting: {action_in.pending_reason}",
             status=TARGET_STATUS[act], pending_reason=action_in.pending_reason)

    elif act == "resolve":
        if not own:
            raise HTTPException(403, "Only the assigned team may resolve")
        _require_transition(ticket, act)
        if not (action_in.resolution or "").strip():
            raise HTTPException(400, "SOP: resolution details are mandatory before resolving")
        setf("RESOLVED", f"Resolution: {action_in.resolution}",
             status=TARGET_STATUS[act], resolved_at=now, resolution=action_in.resolution,
             diagnosis=action_in.diagnosis or ticket.diagnosis,
             action_taken=action_in.action_taken or ticket.action_taken,
             root_cause=action_in.root_cause or ticket.root_cause,
             parts=action_in.parts or ticket.parts)

    elif act == "confirm":
        if not own:
            raise HTTPException(403, "Only the assigned team may confirm resolution with the MMU")
        _require_transition(ticket, act)
        if not (action_in.confirmed_by or "").strip():
            raise HTTPException(400, "SOP: record who at the MMU/field team confirmed the resolution")
        setf("CONFIRMED", f"Resolution confirmed with {action_in.confirmed_by}",
             status=TARGET_STATUS[act], confirmed_by=action_in.confirmed_by, confirmed_at=now)

    elif act == "close":
        if not own:
            raise HTTPException(403, "Only the assigned team may close this ticket")
        _require_transition(ticket, act)
        if not (ticket.resolution or action_in.resolution):
            raise HTTPException(400, "SOP: resolution must be documented before closure")
        breached = bool(ticket.due_at and now > ticket.due_at)
        setf("CLOSED", f"Closed by {user['name']}{' (TAT BREACHED)' if breached else ' within TAT'}",
             status=TARGET_STATUS[act], closed_at=now, breached=breached, resolution=action_in.resolution or ticket.resolution)

    elif act == "escalate":
        if not own:
            raise HTTPException(403, "Only the assigned team may escalate this ticket")
        if ticket.status == "CLOSED":
            raise HTTPException(409, "SOP: only an open ticket may be escalated")
        setf("ESCALATED", f"Escalated to CC Manager: {action_in.note or 'TAT risk'}",
             escalated=True, escalated_at=now, escalated_to='CC_MANAGER', escalation_note=action_in.note or "TAT risk")
        notify_escalated(db, ticket, action_in.note or "TAT risk")

    elif act == "reassign":
        if role not in ("CC_MANAGER", "CALL_TAKER"):
            raise HTTPException(403, "Only the CC Manager or Call Taker may re-route a ticket")
        if ticket.status == "CLOSED":
            raise HTTPException(409, "SOP: a closed ticket must be reopened before it can be re-routed")
        nt = (action_in.team or "").upper()
        if nt not in TEAMS:
            raise HTTPException(400, "Unknown team")
        setf("REASSIGNED", f"Re-routed to {TEAMS[nt]}. {action_in.note or ''}",
             team=nt, owner=TEAMS[nt], status='ASSIGNED', assigned_at=now, assignee=None)

    elif act == "repriority":
        if role not in ("CC_MANAGER", "CALL_TAKER"):
            raise HTTPException(403, "Only the CC Manager or Call Taker may change priority")
        if ticket.status == "CLOSED":
            raise HTTPException(409, "SOP: a closed ticket must be reopened before its priority can change")
        if action_in.priority not in PRIORITY:
            raise HTTPException(400, "Priority must be P1-P4")
        nt_mins = get_tat_map(db).get(action_in.priority, 1440)
        setf("PRIORITY", f"Priority set to {action_in.priority} (TAT {nt_mins} min)",
             priority=action_in.priority, tat_mins=nt_mins, due_at=ticket.created_at + datetime.timedelta(minutes=nt_mins))

    elif act == "reopen":
        if role not in ("CC_MANAGER", "CALL_TAKER"):
            raise HTTPException(403, "Only the CC Manager or Call Taker may reopen")
        _require_transition(ticket, act)
        if not (action_in.note or "").strip():
            raise HTTPException(400, "SOP: reopening a ticket must record the reason")
        setf("REOPENED", action_in.note,
             status=TARGET_STATUS[act], closed_at=None, reopened=ticket.reopened + 1)
    else:
        raise HTTPException(400, "Unknown action")

    return {"ok": True, "id": action_in.id, "action": act}
