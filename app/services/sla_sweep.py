import asyncio
import datetime
import logging
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.models.ticket import Ticket
from app.crud.crud_event import create_event
from app.crud.crud_notification import create_notification, notification_exists
from app.core.config import SLA_SWEEP_SECONDS, RESOLVED_FOLLOWUP_HOURS
from app.services.formatting import sla_tier

logger = logging.getLogger("ccc.sla_sweep")

_SYSTEM_ACTOR = {"username": "sla-sweep", "role": "SYSTEM", "name": "SLA monitor"}

def _sweep_open_tickets(db: Session, now: datetime.datetime):
    tickets = db.query(Ticket).filter(Ticket.status != "CLOSED", Ticket.due_at.isnot(None)).all()
    for t in tickets:
        mins_left = (t.due_at - now).total_seconds() / 60.0
        tier = sla_tier(mins_left, t.tat_mins)

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
        elif tier == "CRITICAL":
            if not notification_exists(db, t.id, "CRITICAL"):
                create_notification(db, t.team, t.id, "CRITICAL", f"Ticket {t.ticket_no} is critically close to breaching TAT ({round(mins_left)}m left)")
        elif tier == "AT RISK":
            if not notification_exists(db, t.id, "AT_RISK"):
                create_notification(db, t.team, t.id, "AT_RISK", f"Ticket {t.ticket_no} is at risk of breaching TAT ({round(mins_left)}m left)")

def _sweep_pending_confirmations(db: Session, now: datetime.datetime):
    cutoff = now - datetime.timedelta(hours=RESOLVED_FOLLOWUP_HOURS)
    stalled = db.query(Ticket).filter(Ticket.status == "RESOLVED", Ticket.resolved_at.isnot(None), Ticket.resolved_at <= cutoff).all()
    for t in stalled:
        if not notification_exists(db, t.id, "PENDING_CONFIRMATION"):
            create_notification(db, t.team, t.id, "PENDING_CONFIRMATION",
                                 f"Ticket {t.ticket_no} has been awaiting MMU confirmation for over {RESOLVED_FOLLOWUP_HOURS}h")

def run_sla_sweep_once():
    """One sweep pass over all open tickets. Safe to call repeatedly - every
    notification/auto-escalation it emits is idempotent (guarded by
    notification_exists / the escalated flag)."""
    db = SessionLocal()
    try:
        now = datetime.datetime.now()
        _sweep_open_tickets(db, now)
        _sweep_pending_confirmations(db, now)
    except Exception:
        logger.exception("SLA sweep pass failed")
        db.rollback()
    finally:
        db.close()

async def sla_sweep_loop():
    while True:
        await asyncio.to_thread(run_sla_sweep_once)
        await asyncio.sleep(SLA_SWEEP_SECONDS)
