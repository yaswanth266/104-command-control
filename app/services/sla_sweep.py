import asyncio
import datetime
import logging
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.models.ticket import Ticket
from app.crud.crud_event import create_event
from app.crud.crud_notification import create_notification, notification_exists
from app.crud.crud_settings import get_sla_config, get_dispatch_config
from app.crud.crud_user import get_team_managers, get_local_team_lead
from app.services.notifications import notify_escalated
from app.services.webhooks import dispatch_ticket_event
from app.core.config import SLA_SWEEP_SECONDS
from app.services.formatting import sla_tier

logger = logging.getLogger("ccc.sla_sweep")

_SYSTEM_ACTOR = {"username": "sla-sweep", "role": "SYSTEM", "name": "SLA monitor"}

def _sweep_open_tickets(db: Session, now: datetime.datetime, sla_cfg: dict):
    """BREACHED (100% of TAT) still broadcasts to the team and auto-escalates
    to CC_MANAGER, unchanged. Below that, notification AUDIENCE is tiered by
    percent-of-TAT-used (separate from the at-risk/critical PILL, which is
    untouched) specifically to avoid paging the CC Manager over every warning
    on every ticket statewide: the assignee is warned first (50%), then that
    team's Team Manager(s) (80%) - the CC Manager only sees an actual breach."""
    tickets = db.query(Ticket).filter(Ticket.status != "CLOSED", Ticket.due_at.isnot(None)).all()
    for t in tickets:
        mins_left = (t.due_at - now).total_seconds() / 60.0
        tier = sla_tier(mins_left, t.tat_mins, sla_cfg)
        pct_used = 1 - (mins_left / t.tat_mins) if t.tat_mins else 1.0

        if tier == "BREACHED":
            if not notification_exists(db, t.id, "BREACHED"):
                create_notification(db, t.team, t.id, "BREACHED", f"Ticket {t.ticket_no} has breached its TAT")
                create_notification(db, "CC_MANAGER", t.id, "BREACHED", f"Ticket {t.ticket_no} ({t.team}) has breached its TAT")
            if not t.escalated:
                t.escalated = True
                t.escalated_at = now
                t.escalated_to = "CC_MANAGER"
                t.escalation_note = "Auto-escalated: TAT breached"
                db.commit()
                create_event(db, t.id, _SYSTEM_ACTOR, "AUTO_ESCALATED", "Auto-escalated to CC Manager: TAT breached")
                create_notification(db, "CC_MANAGER", t.id, "ESCALATED", f"Ticket {t.ticket_no} auto-escalated: TAT breached")
                dispatch_ticket_event(db, "ticket.escalated", t, _SYSTEM_ACTOR["username"], note="Auto-escalated: TAT breached")
        elif pct_used >= sla_cfg["team_manager_warn_pct"]:
            if not notification_exists(db, t.id, "TAT_TEAM_MANAGER_WARN"):
                # Local Team Lead routing (future, dormant until enabled):
                # prefer the district's lead over the statewide Team
                # Executive(s) once the toggle is on and one is configured -
                # falls back to the existing team-wide behavior otherwise.
                local_leads = (get_local_team_lead(db, t.team, t.district_id)
                               if (t.district_id and get_dispatch_config(db)["local_team_lead_enabled"]) else [])
                managers = local_leads or get_team_managers(db, t.team)
                msg = f"Ticket {t.ticket_no} has used {round(pct_used*100)}% of its TAT ({round(mins_left)}m left) - needs your attention"
                if managers:
                    # audience_role=None: personal, not a team-wide broadcast
                    # (see notify_assigned's comment for why that matters).
                    for m in managers:
                        create_notification(db, None, t.id, "TAT_TEAM_MANAGER_WARN", msg, audience_username=m.username)
                else:
                    # No Team Executive configured for this team yet - don't
                    # let the warning vanish, fall back to the whole team.
                    create_notification(db, t.team, t.id, "TAT_TEAM_MANAGER_WARN", msg + " (no Team Executive set for this team)")
        elif pct_used >= sla_cfg["assignee_warn_pct"]:
            if not notification_exists(db, t.id, "TAT_ASSIGNEE_WARN"):
                msg = f"Ticket {t.ticket_no} has used {round(pct_used*100)}% of its TAT ({round(mins_left)}m left)"
                if t.assignee:
                    create_notification(db, None, t.id, "TAT_ASSIGNEE_WARN", msg, audience_username=t.assignee)
                else:
                    # Nobody's picked it up yet - broadcasting to the team is
                    # exactly the right behavior here (see dashboard's
                    # "unassigned" count for the same gap).
                    create_notification(db, t.team, t.id, "TAT_ASSIGNEE_WARN", msg + " (unassigned)")

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
        _sweep_open_tickets(db, now, sla_cfg)
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
