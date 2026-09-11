from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.priority import Priority

def get_priorities(db: Session, include_inactive: bool = False):
    q = db.query(Priority)
    if not include_inactive:
        q = q.filter(Priority.is_active == True)
    return q.order_by(Priority.display_order, Priority.code).all()

def get_priority(db: Session, code: str):
    return db.query(Priority).filter(Priority.code == code).first()

def get_priority_map(db: Session):
    """{code: description} for active priorities - the /meta 'priority' shape,
    unchanged from the old hardcoded PRIORITY dict."""
    return {p.code: (p.description or p.label) for p in get_priorities(db)}

def get_priority_full_map(db: Session):
    """{code: {label, description, severity, display_order}} for active
    priorities - richer shape for building selects/admin UI."""
    return {p.code: {"label": p.label, "description": p.description,
                      "severity": p.severity, "display_order": p.display_order}
            for p in get_priorities(db)}

def create_priority(db: Session, code: str, label: str, description: str = None,
                     severity: int = None, display_order: int = 0) -> Priority:
    code = (code or "").strip().upper()
    if not code or not (label or "").strip():
        raise HTTPException(400, "Priority code and label are required")
    if db.query(Priority).filter(Priority.code == code).first():
        raise HTTPException(409, f"Priority code '{code}' already exists")
    p = Priority(code=code, label=label.strip(), description=(description or "").strip() or None,
                 severity=severity, display_order=display_order or 0, is_active=True)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p

def update_priority(db: Session, code: str, label: str = None, description: str = None,
                     severity: int = None, display_order: int = None, is_active: bool = None) -> Priority:
    p = get_priority(db, code)
    if not p:
        raise HTTPException(404, "Priority not found")
    if label is not None:
        if not label.strip():
            raise HTTPException(400, "Priority label cannot be blank")
        p.label = label.strip()
    if description is not None:
        p.description = description.strip() or None
    if severity is not None:
        p.severity = severity
    if display_order is not None:
        p.display_order = display_order
    if is_active is not None:
        p.is_active = is_active
    db.commit()
    db.refresh(p)
    return p
