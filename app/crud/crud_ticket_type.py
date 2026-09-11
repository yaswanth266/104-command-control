from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.ticket_type import TicketType

def get_ticket_types(db: Session, include_inactive: bool = False):
    q = db.query(TicketType)
    if not include_inactive:
        q = q.filter(TicketType.is_active == True)
    return q.order_by(TicketType.code).all()

def get_ticket_type(db: Session, code: str):
    return db.query(TicketType).filter(TicketType.code == code).first()

def get_ticket_type_map(db: Session):
    """{code: {label, requires_approval}} for active ticket types - the /meta shape."""
    return {t.code: {"label": t.label, "requires_approval": t.requires_approval}
            for t in get_ticket_types(db)}

def create_ticket_type(db: Session, code: str, label: str, requires_approval: bool = False) -> TicketType:
    code = (code or "").strip().upper()
    if not code or not (label or "").strip():
        raise HTTPException(400, "Ticket type code and label are required")
    if db.query(TicketType).filter(TicketType.code == code).first():
        raise HTTPException(409, f"Ticket type code '{code}' already exists")
    t = TicketType(code=code, label=label.strip(), requires_approval=bool(requires_approval), is_active=True)
    db.add(t)
    db.commit()
    db.refresh(t)
    return t

def update_ticket_type(db: Session, code: str, label: str = None, requires_approval: bool = None,
                        is_active: bool = None) -> TicketType:
    t = get_ticket_type(db, code)
    if not t:
        raise HTTPException(404, "Ticket type not found")
    if label is not None:
        if not label.strip():
            raise HTTPException(400, "Ticket type label cannot be blank")
        t.label = label.strip()
    if requires_approval is not None:
        t.requires_approval = requires_approval
    if is_active is not None:
        t.is_active = is_active
    db.commit()
    db.refresh(t)
    return t
