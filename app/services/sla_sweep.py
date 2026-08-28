import asyncio
import datetime
import logging
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.models.ticket import Ticket
from app.crud.crud_event import create_event
from app.crud.crud_notification import create_notification, notification_exists
from app.crud.crud_settings import get_sla_config
from app.crud.crud_user import get_team_managers
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
        elif pct_used >= sla_cfg["team_manager_warn_pct"]:
            if not notification_exists(db, t.id, "TAT_TEAM_MANAGER_WARN"):
                managers = get_team_managers(db, t.team)
                msg = f"Ticket {t.ticket_no} has used {round(pct_used*100)}% of its TAT ({round(mins_left)}m left) - needs your attention"
                if managers:
                    # audience_role=None: personal, not a team-wide broadcast
                    # (see notify_assigned's comment for why that matters).
                    for m in managers:
                        create_notification(db, None, t.id, "TAT_TEAM_MANAGER_WARN", msg, audience_username=m.username)
                else:
                    # No Team Manager configured for this team yet - don't let
                    # the warning vanish, fall back to the whole team.
                    create_notification(db, t.team, t.id, "TAT_TEAM_MANAGER_WARN", msg + " (no Team Manager set for this team)")
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
    except Exception:
        logger.exception("SLA sweep pass failed")
        db.rollback()
    finally:
        db.close()

async def sla_sweep_loop():
    while True:
        await asyncio.to_thread(run_sla_sweep_once)
        await asyncio.sleep(SLA_SWEEP_SECONDS)
