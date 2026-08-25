from sqlalchemy.orm import Session
from app.models.event import Event

def create_event(db: Session, ticket_id: int, user: dict, action: str, detail: str = ""):
    db_event = Event(
        ticket_id=ticket_id,
        actor=user.get("username", "system") if user else "system",
        actor_role=user.get("role", "SYSTEM") if user else "SYSTEM",
        action=action,
        detail=detail
    )
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event

def get_events_by_ticket(db: Session, ticket_id: int):
    return db.query(Event).filter(Event.ticket_id == ticket_id).order_by(Event.id).all()
