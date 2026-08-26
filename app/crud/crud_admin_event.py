from sqlalchemy.orm import Session
from app.models.admin_event import AdminEvent

def log_admin_event(db: Session, user: dict, action: str, entity_type: str, entity_id: str, detail: str = ""):
    e = AdminEvent(
        actor=user.get("username", "system") if user else "system",
        actor_role=user.get("role", "SYSTEM") if user else "SYSTEM",
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        detail=detail,
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return e

def get_admin_events(db: Session, limit: int = 100):
    return db.query(AdminEvent).order_by(AdminEvent.id.desc()).limit(limit).all()
