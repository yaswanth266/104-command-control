import datetime
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.models.notification import Notification

def create_notification(db: Session, audience_role: str, ticket_id: int, type_: str, message: str, audience_username: str = None):
    n = Notification(audience_role=audience_role, audience_username=audience_username, ticket_id=ticket_id, type=type_, message=message)
    db.add(n)
    db.commit()
    db.refresh(n)
    return n

def notification_exists(db: Session, ticket_id: int, type_: str, since: datetime.datetime = None, audience_username: str = None):
    q = db.query(Notification).filter(Notification.ticket_id == ticket_id, Notification.type == type_)
    if audience_username is not None:
        q = q.filter(Notification.audience_username == audience_username)
    if since:
        q = q.filter(Notification.created_at >= since)
    return db.query(q.exists()).scalar()

def get_notifications(db: Session, role: str, username: str = None, unread_only: bool = False, limit: int = 100):
    q = db.query(Notification)
    if role != "CC_MANAGER":
        # Role-wide broadcasts for this team, OR anything addressed to this
        # person by name (e.g. "you were assigned this", a Team Manager's
        # individual 80%-TAT warning) even if audience_role differs.
        q = q.filter(or_(Notification.audience_role == role, Notification.audience_username == username))
    if unread_only:
        q = q.filter(Notification.read_at.is_(None))
    return q.order_by(Notification.created_at.desc()).limit(limit).all()

def mark_read(db: Session, notification_id: int, role: str, username: str = None):
    n = db.query(Notification).filter(Notification.id == notification_id).first()
    if not n:
        return None
    if role != "CC_MANAGER" and n.audience_role != role and n.audience_username != username:
        return False
    n.read_at = datetime.datetime.now()
    db.commit()
    db.refresh(n)
    return n
