import datetime
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.ticket import Ticket
from app.crud.crud_event import create_event
from app.core.config import PRIORITY
from app.crud.crud_ticket import get_tat_map
from app.crud.crud_team import get_team_map, get_active_team_map
from app.crud.crud_settings import get_sla_config, get_dispatch_config
from app.schemas.ticket import ActionIn
from app.services.notifications import notify_escalated, notify_assigned
from app.services.webhooks import dispatch_ticket_event

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
    # LT self-service: the LT who raised this ticket may confirm-fixed or
    # reopen-still-broken on it themselves (see the "confirm"/"reopen"
    # branches below), even though they're not "own" (not a member of
    # whichever team the ticket is currently routed to).
    is_originating_lt = role == "LT" and ticket.created_by == user["username"]

    def setf(action_name: str, detail: str, webhook_event: str = None, **kwargs):
        old_status = ticket.status
        # SLA-pausing PENDING: whenever an action moves a ticket OUT of PENDING
        # into any other status, credit back the time it sat waiting (e.g. on
        # the customer) by pushing due_at out by the elapsed pending duration -
        # otherwise a customer callback delay counts against the team's TAT.
        new_status_kw = kwargs.get("status")
        if old_status == "PENDING" and new_status_kw and new_status_kw != "PENDING" and ticket.pending_since:
            elapsed_min = (now - ticket.pending_since).total_seconds() / 60.0
            if ticket.due_at:
                ticket.due_at = ticket.due_at + datetime.timedelta(minutes=elapsed_min)
            ticket.paused_minutes = (ticket.paused_minutes or 0) + round(elapsed_min)
            ticket.pending_since = None
        for k, v in kwargs.items():
            setattr(ticket, k, v)
        db.commit()
        db.refresh(ticket)
        new_status = ticket.status
        changed = old_status if old_status != new_status else None
        create_event(db, ticket.id, user, action_name, detail,
                     old_status=changed,
                     new_status=new_status if changed else None)
        # Outbound webhook (see app/services/webhooks.py): fire-and-forget,
        # never blocks or fails this action even if the external receiver is
        # down - dispatch_webhook_event swallows its own errors.
        if webhook_event:
            dispatch_ticket_event(db, webhook_event, ticket, user.get("username", "system"),
                                   old_status=changed, note=detail)

    now = datetime.datetime.now()

    if act == "acknowledge":
        if not own:
            raise HTTPException(403, "Only the assigned team may acknowledge")
        _require_transition(ticket, act)
        setf("ACKNOWLEDGED", f"Acknowledged by {user['name']} ({get_team_map(db).get(ticket.team, ticket.team)})",
             "ticket.status_changed",
             status=TARGET_STATUS[act], acknowledged_at=now, first_response_at=ticket.first_response_at or now, assignee=user['username'])

    elif act == "start":
        if not own:
            raise HTTPException(403, "Only the assigned team may work this ticket")
        _require_transition(ticket, act)
        setf("IN_PROGRESS", action_in.note or "Investigation started",
             "ticket.status_changed",
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
             "ticket.note_added",
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
             "ticket.status_changed",
             status=TARGET_STATUS[act], pending_reason=action_in.pending_reason,
             pending_since=(ticket.pending_since or now))

    elif act == "resolve":
        if not own:
            raise HTTPException(403, "Only the assigned team may resolve")
        _require_transition(ticket, act)
        if not (action_in.resolution or "").strip():
            raise HTTPException(400, "SOP: resolution details are mandatory before resolving")
        setf("RESOLVED", f"Resolution: {action_in.resolution}",
             "ticket.status_changed",
             status=TARGET_STATUS[act], resolved_at=now, resolution=action_in.resolution,
             diagnosis=action_in.diagnosis or ticket.diagnosis,
             action_taken=action_in.action_taken or ticket.action_taken,
             root_cause=action_in.root_cause or ticket.root_cause,
             parts=action_in.parts or ticket.parts)

    elif act == "confirm":
        if not (own or is_originating_lt):
            raise HTTPException(403, "Only the assigned team, or the LT who raised this ticket, may confirm the resolution")
        _require_transition(ticket, act)
        if not (action_in.confirmed_by or "").strip():
            raise HTTPException(400, "SOP: record who at the MMU/field team confirmed the resolution")
        setf("CONFIRMED", f"Resolution confirmed with {action_in.confirmed_by}",
             "ticket.status_changed",
             status=TARGET_STATUS[act], confirmed_by=action_in.confirmed_by, confirmed_at=now)

    elif act == "close":
        if not own:
            raise HTTPException(403, "Only the assigned team may close this ticket")
        _require_transition(ticket, act)
        if not (ticket.resolution or action_in.resolution):
            raise HTTPException(400, "SOP: resolution must be documented before closure")
        breached = bool(ticket.due_at and now > ticket.due_at)
        setf("CLOSED", f"Closed by {user['name']}{' (TAT BREACHED)' if breached else ' within TAT'}",
             "ticket.status_changed",
             status=TARGET_STATUS[act], closed_at=now, breached=breached, resolution=action_in.resolution or ticket.resolution)

    elif act == "escalate":
        if role == "CC_MANAGER":
            raise HTTPException(403, "The Global Team Executive is the escalation target - this ticket cannot be escalated to yourself")
        if not own:
            raise HTTPException(403, "Only the assigned team may escalate this ticket")
        if ticket.status == "CLOSED":
            raise HTTPException(409, "SOP: only an open ticket may be escalated")
        reason = (action_in.note or "").strip()
        if not reason:
            raise HTTPException(400, "SOP: a reason is required to escalate this ticket")
        setf("ESCALATED", f"Escalated to Global Team Executive: {reason}",
             "ticket.escalated",
             escalated=True, escalated_at=now, escalated_to='CC_MANAGER', escalation_note=reason,
             escalation_count=(ticket.escalation_count or 0) + 1)
        notify_escalated(db, ticket, reason)

    elif act == "assign":
        # Directive, not an access-control gate: a Team Executive points a
        # ticket at a named engineer on their own team (or the Global Team
        # Executive can, on any team). Anyone on the team can still act on it
        # exactly as before - this doesn't lock the ticket to that person, it
        # just tells the team (via a personal notification) who's expected to
        # run with it.
        is_this_teams_manager = role == ticket.team and bool(user.get("is_team_manager"))
        if not (is_this_teams_manager or role == "CC_MANAGER"):
            raise HTTPException(403, "Only this team's Team Executive or the Global Team Executive may assign tickets to a named engineer")
        if is_this_teams_manager and get_dispatch_config(db)["local_team_lead_enabled"]:
            # Local Team Lead routing (future, dormant until enabled): a
            # Team Executive with no district set is statewide and keeps
            # full assign rights; one with a district set is a Local Team
            # Lead and may only assign tickets inside their own district.
            from app.crud.crud_user import get_user_by_username as _get_actor
            actor = _get_actor(db, user["username"])
            if actor and actor.district_id and ticket.district_id and actor.district_id != ticket.district_id:
                raise HTTPException(403, "This ticket is outside your district - only a statewide Team Executive "
                                          "or the Global Team Executive may assign it")
        if ticket.status == "CLOSED":
            raise HTTPException(409, "SOP: a closed ticket must be reopened before it can be assigned")
        target_username = (action_in.assignee or "").strip().lower()
        if not target_username:
            raise HTTPException(400, "Choose an engineer to assign this ticket to")
        from app.crud.crud_user import get_user_by_username
        target = get_user_by_username(db, target_username)
        if not target or target.role != ticket.team:
            raise HTTPException(400, f"'{target_username}' is not an active member of {ticket.team}")
        setf("ASSIGNED_TO", f"{user['name']} assigned this to {target.name}", "ticket.assigned", assignee=target.username)
        notify_assigned(db, ticket, target.username, user['name'])

    elif act == "reassign":
        if role not in ("CC_MANAGER", "CALL_TAKER"):
            raise HTTPException(403, "Only the Global Team Executive or Call Taker may re-route a ticket")
        if ticket.status == "CLOSED":
            raise HTTPException(409, "SOP: a closed ticket must be reopened before it can be re-routed")
        nt = (action_in.team or "").upper()
        active_teams = get_active_team_map(db)
        if nt not in active_teams:
            raise HTTPException(400, "Unknown or inactive team")
        setf("REASSIGNED", f"Re-routed to {active_teams[nt]}. {action_in.note or ''}",
             "ticket.assigned",
             team=nt, owner=active_teams[nt], status='ASSIGNED', assigned_at=now, assignee=None)

    elif act == "repriority":
        if role not in ("CC_MANAGER", "CALL_TAKER"):
            raise HTTPException(403, "Only the Global Team Executive or Call Taker may change priority")
        if ticket.status == "CLOSED":
            raise HTTPException(409, "SOP: a closed ticket must be reopened before its priority can change")
        if action_in.priority not in PRIORITY:
            raise HTTPException(400, "Priority must be P1-P4")
        nt_mins = get_tat_map(db).get(action_in.priority, 1440)
        # Preserve any SLA pause already credited (see setf) - otherwise a
        # priority change would silently wipe out paused time from an earlier
        # PENDING period.
        new_due = ticket.created_at + datetime.timedelta(minutes=nt_mins + (ticket.paused_minutes or 0))
        setf("PRIORITY", f"Priority set to {action_in.priority} (TAT {nt_mins} min)",
             "ticket.note_added",
             priority=action_in.priority, tat_mins=nt_mins, due_at=new_due)

    elif act == "reopen":
        if role not in ("CC_MANAGER", "CALL_TAKER") and not is_originating_lt:
            raise HTTPException(403, "Only the Global Team Executive, Call Taker, or the LT who raised this ticket may reopen")
        _require_transition(ticket, act)
        if not (action_in.note or "").strip():
            raise HTTPException(400, "SOP: reopening a ticket must record the reason")
        window_hours = get_sla_config(db)["reopen_window_hours"]
        if ticket.closed_at and (now - ticket.closed_at) > datetime.timedelta(hours=window_hours):
            raise HTTPException(409, f"SOP: this ticket closed over {window_hours}h ago and can no longer be "
                                      "reopened - register a new ticket instead so history stays accurate")
        setf("REOPENED", action_in.note,
             "ticket.status_changed",
             status=TARGET_STATUS[act], closed_at=None, reopened=ticket.reopened + 1)
    else:
        raise HTTPException(400, "Unknown action")

    return {"ok": True, "id": action_in.id, "action": act}
