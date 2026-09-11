import datetime
from sqlalchemy.orm import Session
from app.models.sla_policy import SlaPolicy
from app.core.config import TAT_DEFAULT
from app.crud.crud_calendar import get_calendar_config
from app.services.calendar import add_working_minutes

def resolve_policy(db: Session, ticket_type: str, category_code: str, subcategory_code: str, priority_code: str):
    """Most specific match wins: sub-category -> category -> ticket_type ->
    the scope-less baseline row for this priority. Returns None only if even
    the baseline row is missing (shouldn't happen post-migration - callers
    fall back to TAT_DEFAULT, see resolve_ticket_sla)."""
    base = db.query(SlaPolicy).filter(SlaPolicy.priority_code == priority_code, SlaPolicy.is_active == True)

    if subcategory_code:
        row = base.filter(SlaPolicy.subcategory_code == subcategory_code).first()
        if row:
            return row
    if category_code:
        row = base.filter(SlaPolicy.subcategory_code.is_(None), SlaPolicy.category_code == category_code).first()
        if row:
            return row
    if ticket_type:
        row = base.filter(SlaPolicy.subcategory_code.is_(None), SlaPolicy.category_code.is_(None),
                           SlaPolicy.ticket_type == ticket_type).first()
        if row:
            return row
    return base.filter(SlaPolicy.subcategory_code.is_(None), SlaPolicy.category_code.is_(None),
                        SlaPolicy.ticket_type.is_(None)).first()

def resolve_ticket_sla(db: Session, ticket_type: str, category_code: str, subcategory_code: str,
                        priority_code: str, now: datetime.datetime = None) -> dict:
    """{policy_code, tat_mins, due_at, response_due_at} for a ticket being
    created (or repriced) with this classification, at instant `now`
    (defaults to datetime.now()). With no SLA Policy rows configured at all
    (shouldn't happen post-migration - the baseline rows are seeded) this
    still returns a usable TAT_DEFAULT-based result under a 24x7 calendar,
    identical to pre-phase-3 behavior."""
    now = now or datetime.datetime.now()
    policy = resolve_policy(db, ticket_type, category_code, subcategory_code, priority_code)
    if policy:
        resolution_mins = policy.resolution_mins
        response_mins = policy.response_mins
        calendar_cfg = get_calendar_config(db, policy.calendar_code)
        policy_code = policy.code
    else:
        resolution_mins = TAT_DEFAULT.get(priority_code, 1440)
        response_mins = None
        calendar_cfg = {"is_24x7": True, "working_hours": None, "holidays": []}
        policy_code = None

    return {
        "policy_code": policy_code,
        "tat_mins": resolution_mins,
        "due_at": add_working_minutes(now, resolution_mins, calendar_cfg),
        "response_due_at": add_working_minutes(now, response_mins, calendar_cfg),
    }
