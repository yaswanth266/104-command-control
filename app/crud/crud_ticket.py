import json
import datetime
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc
from app.models.ticket import Ticket
from app.models.config import Config
from app.core.config import TAT_DEFAULT

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

def get_ticket(db: Session, ticket_id: int):
    return db.query(Ticket).filter(Ticket.id == ticket_id).first()

def get_tickets(db: Session, user: dict, status: str = "", team: str = "", scope: str = "", q: str = ""):
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
        query = query.filter(and_(
            Ticket.status != "CLOSED", 
            Ticket.due_at >= datetime.datetime.now(), 
            Ticket.due_at <= datetime.datetime.now() + datetime.timedelta(minutes=60)
        ))
    elif scope == "escalated":
        query = query.filter(Ticket.escalated == True)
        
    if q:
        search_pattern = f"%{q}%"
        query = query.filter(or_(
            Ticket.ticket_no.like(search_pattern),
            Ticket.mmu_vehicle.like(search_pattern),
            Ticket.problem.like(search_pattern),
            Ticket.district.like(search_pattern)
        ))
        
    # Order by priority P1..P4 and then due_at. SQLAlchemy text is best for FIELD
    from sqlalchemy import text
    query = query.order_by(text("FIELD(priority, 'P1', 'P2', 'P3', 'P4')"), Ticket.due_at.asc())
    
    return query.limit(500).all()
