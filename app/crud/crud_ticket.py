import datetime
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc, text
from sqlalchemy.exc import IntegrityError
from app.models.ticket import Ticket
from app.crud.crud_settings import get_sla_config

def get_tat_map(db: Session):
    """{priority_code: minutes} - now backed by ccc_sla_policy's baseline
    rows (see app/crud/crud_sla_policy.py), not ccc_config's old 'tat' key."""
    from app.crud.crud_sla_policy import get_baseline_tat_map
    return get_baseline_tat_map(db)

def get_next_ticket_no(db: Session) -> str:
    d = datetime.datetime.now().strftime("%Y%m%d")
    last_ticket = db.query(Ticket.ticket_no)\
        .filter(Ticket.ticket_no.like(f"CCC-{d}-%"))\
        .order_by(Ticket.ticket_no.desc())\
        .first()
    
    if last_ticket:
        last_seq = int(last_ticket[0].split('-')[-1])
        return f"CCC-{d}-{last_seq + 1:04d}"
    return f"CCC-{d}-0001"

def create_ticket(db: Session, fields: dict, max_attempts: int = 5) -> Ticket:
    """Insert a new ticket, retrying with a fresh ticket_no if a concurrent
    registration already claimed the previously computed number."""
    for attempt in range(max_attempts):
        db_ticket = Ticket(ticket_no=get_next_ticket_no(db), **fields)
        db.add(db_ticket)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            if attempt == max_attempts - 1:
                raise
            continue
        db.refresh(db_ticket)
        return db_ticket

def get_ticket(db: Session, ticket_id: int):
    return db.query(Ticket).filter(Ticket.id == ticket_id).first()

def _risk_window_sql(sla_cfg):
    """Same GREATEST(floor, tat_mins*fraction) window as formatting.sla_tier(),
    built per-call since thresholds are admin-editable (ccc_config), not baked
    in at import time - so the queue's "At risk"/"Critical" filters never
    disagree with a ticket's own pill."""
    return f"due_at <= DATE_ADD(NOW(), INTERVAL GREATEST({sla_cfg['at_risk_minutes']}, tat_mins * {sla_cfg['at_risk_fraction']}) MINUTE)"

def _critical_window_sql(sla_cfg):
    return f"due_at <= DATE_ADD(NOW(), INTERVAL GREATEST({sla_cfg['critical_minutes']}, tat_mins * {sla_cfg['critical_fraction']}) MINUTE)"

def get_tickets(db: Session, user: dict, status: str = "", team: str = "", scope: str = "", q: str = "",
                 priority: str = "", category: str = "", mmu_vehicle: str = "", district: str = "",
                 district_id: Optional[int] = None, mandal_id: Optional[int] = None,
                 date_from: str = "", date_to: str = "", time_from: str = "", time_to: str = "", shift: str = "",
                 page: int = 1, page_size: int = 50,
                 sort_by: str = "", sort_desc: bool = False):
    query = db.query(Ticket)

    role = user.get("role")
    if role not in ("CC_MANAGER", "CALL_TAKER"):
        query = query.filter(Ticket.team == role)
        if user.get("district_id"):
            query = query.filter(Ticket.district_id == user["district_id"])

    if team:
        query = query.filter(Ticket.team == team)

    if status == "open":
        query = query.filter(Ticket.status != "CLOSED")
    elif status:
        query = query.filter(Ticket.status == status)

    if scope == "breach":
        query = query.filter(and_(Ticket.status != "CLOSED", Ticket.due_at < datetime.datetime.now()))
    elif scope == "risk":
        query = query.filter(and_(Ticket.status != "CLOSED", Ticket.due_at >= datetime.datetime.now(), text(_risk_window_sql(get_sla_config(db)))))
    elif scope == "critical":
        query = query.filter(and_(Ticket.status != "CLOSED", Ticket.due_at >= datetime.datetime.now(), text(_critical_window_sql(get_sla_config(db)))))
    elif scope == "escalated":
        query = query.filter(Ticket.escalated == True)
    elif scope == "unassigned":
        query = query.filter(and_(Ticket.status != "CLOSED", or_(Ticket.assignee.is_(None), Ticket.assignee == "")))

    if priority:
        query = query.filter(Ticket.priority == priority)
    if category:
        query = query.filter(Ticket.category == category)
    if mmu_vehicle:
        query = query.filter(Ticket.mmu_vehicle.like(f"%{mmu_vehicle}%"))
    # A precise location pick (district_id, from the Location dropdown) wins
    # over the free-text `district` fallback used by older callers/exports.
    if district_id:
        query = query.filter(Ticket.district_id == district_id)
    elif district:
        query = query.filter(Ticket.district.like(f"%{district}%"))
    if mandal_id:
        query = query.filter(Ticket.mandal_id == mandal_id)

    if date_from:
        d_from = date_from.strip().replace("T", " ")
        if len(d_from) == 10:
            d_from = f"{d_from} 00:00:00"
        elif len(d_from) == 16:
            d_from = f"{d_from}:00"
        query = query.filter(Ticket.created_at >= d_from)
    if date_to:
        d_to = date_to.strip().replace("T", " ")
        if len(d_to) == 10:
            d_to = f"{d_to} 23:59:59"
        elif len(d_to) == 16:
            d_to = f"{d_to}:59"
        query = query.filter(Ticket.created_at <= d_to)

    # Operational shift is just a named time-of-day window; an explicit
    # time_from/time_to (if ever sent) takes precedence over it.
    if shift == "morning":
        time_from, time_to = time_from or "08:00:00", time_to or "14:00:00"
    elif shift == "evening":
        time_from, time_to = time_from or "14:00:00", time_to or "20:00:00"
    elif shift == "night":
        time_from, time_to = time_from or "20:00:00", time_to or "08:00:00"

    # Bound params here, never an f-string into text() - time_from/time_to
    # are raw request query params, and splicing them into SQL text would be
    # a straightforward injection point.
    if time_from and time_to:
        if time_from <= time_to:
            query = query.filter(text("TIME(ccc_ticket.created_at) >= :t_from AND TIME(ccc_ticket.created_at) <= :t_to")
                                  .bindparams(t_from=time_from, t_to=time_to))
        else:
            # Window wraps past midnight (e.g. the night shift) - either side counts.
            query = query.filter(text("(TIME(ccc_ticket.created_at) >= :t_from OR TIME(ccc_ticket.created_at) <= :t_to)")
                                  .bindparams(t_from=time_from, t_to=time_to))
    elif time_from:
        query = query.filter(text("TIME(ccc_ticket.created_at) >= :t_from").bindparams(t_from=time_from))
    elif time_to:
        query = query.filter(text("TIME(ccc_ticket.created_at) <= :t_to").bindparams(t_to=time_to))

    if q:
        search_pattern = f"%{q}%"
        query = query.filter(or_(
            Ticket.ticket_no.like(search_pattern),
            Ticket.mmu_vehicle.like(search_pattern),
            Ticket.problem.like(search_pattern),
            Ticket.district.like(search_pattern)
        ))

    if sort_by == "created_at":
        query = query.order_by(Ticket.created_at.desc() if sort_desc else Ticket.created_at.asc())
    elif sort_by == "due_at":
        query = query.order_by(Ticket.due_at.desc() if sort_desc else Ticket.due_at.asc())
    elif sort_by == "priority":
        p_order = text("FIELD(priority, 'P4', 'P3', 'P2', 'P1')") if sort_desc else text("FIELD(priority, 'P1', 'P2', 'P3', 'P4')")
        query = query.order_by(p_order, Ticket.due_at.asc())
    elif sort_by == "ticket_no":
        query = query.order_by(Ticket.ticket_no.desc() if sort_desc else Ticket.ticket_no.asc())
    else:
        # Default order
        query = query.order_by(text("FIELD(priority, 'P1', 'P2', 'P3', 'P4')"), Ticket.due_at.asc())

    total = query.count()
    page = max(1, page)
    page_size = max(1, min(page_size, 200))
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return rows, total
