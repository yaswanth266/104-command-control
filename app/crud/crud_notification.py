import datetime
from sqlalchemy.orm import Session
from app.models.notification import Notification

def create_notification(db: Session, audience_role: str, ticket_id: int, type_: str, message: str):
    n = Notification(audience_role=audience_role, ticket_id=ticket_id, type=type_, message=message)
    db.add(n)
    db.commit()
    db.refresh(n)
    return n

def notification_exists(db: Session, ticket_id: int, type_: str, since: datetime.datetime = None):
    q = db.query(Notification).filter(Notification.ticket_id == ticket_id, Notification.type == type_)
    if since:
        q = q.filter(Notification.created_at >= since)
    return db.query(q.exists()).scalar()

def get_notifications(db: Session, role: str, unread_only: bool = False, limit: int = 100):
    q = db.query(Notification)
    if role != "CC_MANAGER":
        q = q.filter(Notification.audience_role == role)
    if unread_only:
        q = q.filter(Notification.read_at.is_(None))
    return q.order_by(Notification.created_at.desc()).limit(limit).all()

def mark_read(db: Session, notification_id: int, role: str):
    n = db.query(Notification).filter(Notification.id == notification_id).first()
    if not n:
        return None
    if role != "CC_MANAGER" and n.audience_role != role:
        return False
    n.read_at = datetime.datetime.now()
    db.commit()
    db.refresh(n)
    return n
