from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.reason import Reason
from app.models.category import Category

def get_reasons(db: Session, category_code: str = None, include_inactive: bool = False):
    q = db.query(Reason)
    if category_code:
        q = q.filter(Reason.category_code == category_code.upper())
    if not include_inactive:
        q = q.filter(Reason.is_active == True)
    return q.order_by(Reason.label).all()

def get_reason(db: Session, code: str):
    return db.query(Reason).filter(Reason.code == code).first()

def create_reason(db: Session, code: str, category_code: str, label: str) -> Reason:
    code = (code or "").strip().upper()
    category_code = (category_code or "").strip().upper()
    if not code or not (label or "").strip():
        raise HTTPException(400, "Reason code and label are required")
    if not db.query(Category).filter(Category.code == category_code).first():
        raise HTTPException(400, f"'{category_code}' is not a known category")
    if db.query(Reason).filter(Reason.code == code).first():
        raise HTTPException(409, f"Reason code '{code}' already exists")
    r = Reason(code=code, category_code=category_code, label=label.strip(), is_active=True)
    db.add(r)
    db.commit()
    db.refresh(r)
    return r

def update_reason(db: Session, code: str, label: str = None, is_active: bool = None) -> Reason:
    r = get_reason(db, code)
    if not r:
        raise HTTPException(404, "Reason not found")
    if label is not None:
        if not label.strip():
            raise HTTPException(400, "Reason label cannot be blank")
        r.label = label.strip()
    if is_active is not None:
        r.is_active = is_active
    db.commit()
    db.refresh(r)
    return r
