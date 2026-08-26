import json
import datetime
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc, text
from sqlalchemy.exc import IntegrityError
from app.models.ticket import Ticket
from app.models.config import Config
from app.core.config import TAT_DEFAULT, AT_RISK_MINUTES, AT_RISK_FRACTION, CRITICAL_MINUTES, CRITICAL_FRACTION

def get_tat_map(db: Session):
    config = db.query(Config).filter(Config.k == 'tat').first()
    if config:
        try:
            return json.loads(config.v)
        except Exception:
            return dict(TAT_DEFAULT)
    return dict(TAT_DEFAULT)

def get_next_ticket_no(db: Session) -> str:
    d = datetime.datetime.now().strftime("%Y%m%d")
    count = db.query(Ticket).filter(Ticket.ticket_no.like(f"CCC-{d}-%")).count()
    return f"CCC-{d}-{count + 1:04d}"

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

# Same GREATEST(floor, tat_mins*fraction) window as formatting.sla_tier(), so the
# queue's "At risk"/"Critical" filters never disagree with a ticket's own pill.
_RISK_WINDOW_SQL = f"due_at <= DATE_ADD(NOW(), INTERVAL GREATEST({AT_RISK_MINUTES}, tat_mins * {AT_RISK_FRACTION}) MINUTE)"
_CRITICAL_WINDOW_SQL = f"due_at <= DATE_ADD(NOW(), INTERVAL GREATEST({CRITICAL_MINUTES}, tat_mins * {CRITICAL_FRACTION}) MINUTE)"

def get_tickets(db: Session, user: dict, status: str = "", team: str = "", scope: str = "", q: str = "",
                 priority: str = "", category: str = "", mmu_vehicle: str = "", district: str = "",
                 date_from: str = "", date_to: str = "", page: int = 1, page_size: int = 50):
    query = db.query(Ticket)

    role = user.get("role")
    if role not in ("CC_MANAGER", "CALL_TAKER"):
        query = query.filter(Ticket.team == role)

    if team:
        query = query.filter(Ticket.team == team)

    if status == "open":
        query = query.filter(Ticket.status != "CLOSED")
    elif status:
        query = query.filter(Ticket.status == status)

    if scope == "breach":
        query = query.filter(and_(Ticket.status != "CLOSED", Ticket.due_at < datetime.datetime.now()))
    elif scope == "risk":
        query = query.filter(and_(Ticket.status != "CLOSED", Ticket.due_at >= datetime.datetime.now(), text(_RISK_WINDOW_SQL)))
    elif scope == "critical":
        query = query.filter(and_(Ticket.status != "CLOSED", Ticket.due_at >= datetime.datetime.now(), text(_CRITICAL_WINDOW_SQL)))
    elif scope == "escalated":
        query = query.filter(Ticket.escalated == True)

    if priority:
        query = query.filter(Ticket.priority == priority)
    if category:
        query = query.filter(Ticket.category == category)
    if mmu_vehicle:
        query = query.filter(Ticket.mmu_vehicle.like(f"%{mmu_vehicle}%"))
    if district:
        query = query.filter(Ticket.district.like(f"%{district}%"))
    if date_from:
        query = query.filter(Ticket.created_at >= date_from)
    if date_to:
        query = query.filter(Ticket.created_at < f"{date_to} 23:59:59")

    if q:
        search_pattern = f"%{q}%"
        query = query.filter(or_(
            Ticket.ticket_no.like(search_pattern),
            Ticket.mmu_vehicle.like(search_pattern),
            Ticket.problem.like(search_pattern),
            Ticket.district.like(search_pattern)
        ))

    # Order by priority P1..P4 and then due_at. SQLAlchemy text is best for FIELD
    query = query.order_by(text("FIELD(priority, 'P1', 'P2', 'P3', 'P4')"), Ticket.due_at.asc())

    total = query.count()
    page = max(1, page)
    page_size = max(1, min(page_size, 200))
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return rows, total
