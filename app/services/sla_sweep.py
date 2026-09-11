import asyncio
import datetime
import logging
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.models.ticket import Ticket
from app.models.sla_policy import SlaPolicy
from app.crud.crud_event import create_event
from app.crud.crud_notification import create_notification, notification_exists
from app.crud.crud_settings import get_sla_config
from app.crud.crud_user import get_user
from app.crud.crud_assignment import get_active_for_level
from app.crud.crud_assignment_exception import create_exception
from app.crud.crud_calendar import get_calendar_config
from app.services.notifications import notify_escalated
from app.services.webhooks import dispatch_ticket_event
from app.core.config import SLA_SWEEP_SECONDS
from app.services.formatting import sla_tier
from app.services.calendar import working_minutes_between

logger = logging.getLogger("ccc.sla_sweep")

_SYSTEM_ACTOR = {"username": "sla-sweep", "role": "SYSTEM", "name": "SLA monitor"}
_ESCALATION_LEVELS = ("L1", "L2", "L3", "L4")

def _calendar_for_ticket(db: Session, t: Ticket, cal_cache: dict) -> dict:
    """Calendar config for `t`'s pct_used math, cached per sla_policy_code
    for the duration of one sweep pass (get_calendar_config runs a holidays
    query per call, and every open ticket on the same policy shares one).
    Falls back to 24x7 (pure wall-clock - identical to the arithmetic this
    replaces) when the ticket has no policy, which shouldn't happen
    post-migration but must never crash the sweep either way."""
    key = t.sla_policy_code or ""
    if key not in cal_cache:
        calendar_code = None
        if t.sla_policy_code:
            policy = db.query(SlaPolicy).filter(SlaPolicy.code == t.sla_policy_code).first()
            calendar_code = policy.calendar_code if policy else None
        cal_cache[key] = get_calendar_config(db, calendar_code) if calendar_code else \
            {"is_24x7": True, "working_hours": None, "holidays": []}
    return cal_cache[key]

def _pct_used(db: Session, t: Ticket, now: datetime.datetime, cal_cache: dict) -> float:
    """Business-calendar-correct fraction of `t`'s Resolution SLA consumed:
    1 - (working minutes remaining until due_at) / tat_mins. Anchored on
    due_at rather than created_at so a PENDING-pause credit already baked
    into due_at (see ticket_service.py's setf()) doesn't need separate
    handling here. The bug this replaces: the old formula divided a
    wall-clock mins_left by a *business-minutes* tat_mins, which under any
    non-24x7 Business Calendar could go wildly negative (e.g. a ticket
    raised just before closing time). On the seeded DEFAULT-24x7 calendar
    the arithmetic is identical to before - only a configured non-24x7
    policy changes the result."""
    if not t.tat_mins or not t.due_at:
        return 1.0
    cal = _calendar_for_ticket(db, t, cal_cache)
    mins_left = working_minutes_between(now, t.due_at, cal)
    return 1 - (mins_left / t.tat_mins)

def _escalate_level(db: Session, t: Ticket, level: str, pct_used: float) -> bool:
    """Fires level `level`'s auto-escalation if it hasn't already (idempotent
    via a per-level notification type). Returns True if a REAL occupant
    (a person or a team) was notified - the caller uses this to stop
    walking further levels; a no-occupant dead level returns False so the
    caller can keep cascading up rather than leaving the ticket stuck."""
    notif_type = f"ESCALATED_{level}"
    if notification_exists(db, t.id, notif_type):
        return False
    occupant = get_active_for_level(db, t.id, level)
    audience_user = get_user(db, occupant.user_id) if (occupant and occupant.user_id) else None
    pct_label = round(pct_used * 100)
    msg = f"Ticket {t.ticket_no} has used {pct_label}% of its Resolution SLA - escalated to {level}"

    had_occupant = True
    if audience_user:
        create_notification(db, None, t.id, notif_type, msg, audience_username=audience_user.username)
    elif occupant and occupant.team_code:
        create_notification(db, occupant.team_code, t.id, notif_type, msg)
    else:
        had_occupant = False
        create_notification(db, t.team, t.id, notif_type,
                             msg + " (no one assigned at this level - notifying the team)")
        create_exception(db, t.id, "NO_OCCUPANT_AT_LEVEL",
                          f"{level} has no local user or team to notify for ticket {t.ticket_no}")

    t.current_level = level
    if audience_user:
        t.current_assignee_username = audience_user.username
    t.escalation_count = (t.escalation_count or 0) + 1
    db.commit()
    note = f"Auto-escalated to {level} at {pct_label}% of Resolution SLA"
    create_event(db, t.id, _SYSTEM_ACTOR, "AUTO_ESCALATED", note)
    dispatch_ticket_event(db, "ticket.escalated", t, _SYSTEM_ACTOR["username"], note=note)
    return had_occupant

def _sweep_open_tickets(db: Session, now: datetime.datetime, sla_cfg: dict, cal_cache: dict):
    """100% of Resolution SLA (BREACHED) broadcasts to the team and
    auto-escalates to CC_MANAGER, same as before. Below that, the ticket
    walks its own L1-L4 chain (app/services/hierarchy.py) as pct_used
    crosses each configured threshold (sla_cfg['escalation_pcts'], ascending
    - default 30/50/70/90), notifying that level's ACTIVE occupant
    individually, or its team if the occupant has no local user, advancing
    Ticket.current_level as it goes. Replaces the old two-tier
    assignee_warn_pct(50%)/team_manager_warn_pct(80%) scheme."""
    tickets = db.query(Ticket).filter(Ticket.status != "CLOSED", Ticket.due_at.isnot(None)).all()
    pcts = sla_cfg["escalation_pcts"]
    for t in tickets:
        mins_left = (t.due_at - now).total_seconds() / 60.0
        tier = sla_tier(mins_left, t.tat_mins, sla_cfg)

        if tier == "BREACHED":
            if not notification_exists(db, t.id, "BREACHED"):
                create_notification(db, t.team, t.id, "BREACHED", f"Ticket {t.ticket_no} has breached its TAT")
                create_notification(db, "CC_MANAGER", t.id, "BREACHED", f"Ticket {t.ticket_no} ({t.team}) has breached its TAT")
            if not t.escalated:
                t.escalated = True
                t.escalated_at = now
                t.escalated_to = "CC_MANAGER"
                t.escalation_note = "Auto-escalated: TAT breached"
                t.current_level = "L4"
                db.commit()
                create_event(db, t.id, _SYSTEM_ACTOR, "AUTO_ESCALATED", "Auto-escalated to CC Manager: TAT breached")
                create_notification(db, "CC_MANAGER", t.id, "ESCALATED", f"Ticket {t.ticket_no} auto-escalated: TAT breached")
                dispatch_ticket_event(db, "ticket.escalated", t, _SYSTEM_ACTOR["username"], note="Auto-escalated: TAT breached")
            continue

        pct_used = _pct_used(db, t, now, cal_cache)
        for level in _ESCALATION_LEVELS:
            if pct_used < pcts[level]:
                break
            if _escalate_level(db, t, level, pct_used):
                break  # notified a real occupant - stop here for this pass
            # else: that level had nobody to notify (already flagged as an
            # Assignment Exception) - keep walking so the ticket doesn't
            # stall behind an unconfigured level while pct_used keeps rising.

def _sweep_lt_cda_timeouts(db: Session, now: datetime.datetime, threshold_minutes: float):
    """LT self-service: if a ticket an LT raised has sat with its (district)
    CDA team this long without being resolved, auto-escalate to CC_MANAGER -
    same mechanics as the BREACHED auto-escalation above (escalated/
    escalated_at/escalation_note + notify_escalated), just a different
    trigger (assigned_at age, not TAT) so a CDA going quiet doesn't leave the
    LT stuck with no path forward before the ticket even breaches its TAT."""
    cutoff = now - datetime.timedelta(minutes=threshold_minutes)
    stuck = db.query(Ticket).filter(
        Ticket.source == "LT_PORTAL",
        Ticket.status.notin_(["RESOLVED", "CLOSURE_CONFIRMATION", "CLOSED"]),
        Ticket.escalated == False,
        Ticket.assigned_at.isnot(None),
        Ticket.assigned_at <= cutoff,
    ).all()
    for t in stuck:
        note = f"Auto-escalated: no resolution from {t.team} within {threshold_minutes} minutes"
        t.escalated = True
        t.escalated_at = now
        t.escalated_to = "CC_MANAGER"
        t.escalation_note = note
        db.commit()
        create_event(db, t.id, _SYSTEM_ACTOR, "AUTO_ESCALATED", note)
        notify_escalated(db, t, note)
        dispatch_ticket_event(db, "ticket.escalated", t, _SYSTEM_ACTOR["username"], note=note)

def _sweep_stuck_pending(db: Session, now: datetime.datetime, threshold_hours: float):
    """A ticket's TAT clock is effectively paused while it's PENDING (see
    ticket_service.py's setf, which credits the elapsed pending time back to
    due_at once it moves again) - which means a ticket someone forgot about
    in PENDING would otherwise never trip the BREACHED auto-escalation above,
    no matter how long it sits. This is a separate trigger (time since
    pending_since, not TAT) so a long-stalled wait-on-someone-else still
    surfaces to the CC Manager."""
    cutoff = now - datetime.timedelta(hours=threshold_hours)
    stuck = db.query(Ticket).filter(
        Ticket.status == "PENDING",
        Ticket.escalated == False,
        Ticket.pending_since.isnot(None),
        Ticket.pending_since <= cutoff,
    ).all()
    for t in stuck:
        note = f"Auto-escalated: stuck in Pending for over {threshold_hours}h"
        t.escalated = True
        t.escalated_at = now
        t.escalated_to = "CC_MANAGER"
        t.escalation_note = note
        db.commit()
        create_event(db, t.id, _SYSTEM_ACTOR, "AUTO_ESCALATED", note)
        notify_escalated(db, t, note)
        dispatch_ticket_event(db, "ticket.escalated", t, _SYSTEM_ACTOR["username"], note=note)

def _sweep_pending_confirmations(db: Session, now: datetime.datetime, followup_hours: float):
    cutoff = now - datetime.timedelta(hours=followup_hours)
    stalled = db.query(Ticket).filter(Ticket.status == "RESOLVED", Ticket.resolved_at.isnot(None), Ticket.resolved_at <= cutoff).all()
    for t in stalled:
        if not notification_exists(db, t.id, "PENDING_CONFIRMATION"):
            create_notification(db, t.team, t.id, "PENDING_CONFIRMATION",
                                 f"Ticket {t.ticket_no} has been awaiting MMU confirmation for over {followup_hours}h")

def run_sla_sweep_once():
    """One sweep pass over all open tickets. Safe to call repeatedly - every
    notification/auto-escalation it emits is idempotent (guarded by
    notification_exists / the escalated flag)."""
    db = SessionLocal()
    try:
        now = datetime.datetime.now()
        sla_cfg = get_sla_config(db)
        cal_cache = {}
        _sweep_open_tickets(db, now, sla_cfg, cal_cache)
        _sweep_pending_confirmations(db, now, sla_cfg["resolved_followup_hours"])
        _sweep_lt_cda_timeouts(db, now, sla_cfg["lt_cda_escalation_minutes"])
        _sweep_stuck_pending(db, now, sla_cfg["pending_escalation_hours"])
    except Exception:
        logger.exception("SLA sweep pass failed")
        db.rollback()
    finally:
        db.close()

async def sla_sweep_loop():
    while True:
        await asyncio.to_thread(run_sla_sweep_once)
        await asyncio.sleep(SLA_SWEEP_SECONDS)
