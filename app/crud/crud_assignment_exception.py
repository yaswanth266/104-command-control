import datetime
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.assignment_exception import AssignmentException

def create_exception(db: Session, ticket_id: int, reason: str, detail: str = None) -> AssignmentException:
    e = AssignmentException(ticket_id=ticket_id, reason=reason, detail=detail, status="OPEN")
    db.add(e)
    db.commit()
    db.refresh(e)
    return e

def get_exceptions(db: Session, status: str = None):
    q = db.query(AssignmentException)
    if status:
        q = q.filter(AssignmentException.status == status.upper())
    return q.order_by(AssignmentException.created_at.desc()).all()

def resolve_exception(db: Session, exception_id: int, resolved_by: str) -> AssignmentException:
    e = db.query(AssignmentException).filter(AssignmentException.id == exception_id).first()
    if not e:
        raise HTTPException(404, "Assignment exception not found")
    if e.status == "OPEN":
        e.status = "RESOLVED"
        e.resolved_at = datetime.datetime.now()
        e.resolved_by = resolved_by
        db.commit()
        db.refresh(e)
    return e
