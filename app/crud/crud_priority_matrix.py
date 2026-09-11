from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.priority_matrix import PriorityMatrix
from app.models.priority import Priority
from app.core.config import IMPACT_LEVELS, URGENCY_LEVELS

def get_matrix(db: Session):
    return db.query(PriorityMatrix).all()

def get_matrix_map(db: Session):
    """{impact_code: {urgency_code: priority_code}} - every (impact, urgency)
    pair the matrix currently has a rule for."""
    out = {}
    for row in get_matrix(db):
        out.setdefault(row.impact_code, {})[row.urgency_code] = row.priority_code
    return out

def resolve_priority(db: Session, impact_code: str, urgency_code: str):
    row = (db.query(PriorityMatrix)
             .filter(PriorityMatrix.impact_code == (impact_code or "").strip().upper(),
                      PriorityMatrix.urgency_code == (urgency_code or "").strip().upper())
             .first())
    return row.priority_code if row else None

def set_cell(db: Session, impact_code: str, urgency_code: str, priority_code: str) -> PriorityMatrix:
    impact_code = (impact_code or "").strip().upper()
    urgency_code = (urgency_code or "").strip().upper()
    priority_code = (priority_code or "").strip().upper()
    if impact_code not in IMPACT_LEVELS:
        raise HTTPException(400, f"Impact must be one of {IMPACT_LEVELS}")
    if urgency_code not in URGENCY_LEVELS:
        raise HTTPException(400, f"Urgency must be one of {URGENCY_LEVELS}")
    if not db.query(Priority).filter(Priority.code == priority_code, Priority.is_active == True).first():
        raise HTTPException(400, f"'{priority_code}' is not an active priority")
    row = (db.query(PriorityMatrix)
             .filter(PriorityMatrix.impact_code == impact_code, PriorityMatrix.urgency_code == urgency_code)
             .first())
    if row:
        row.priority_code = priority_code
    else:
        row = PriorityMatrix(impact_code=impact_code, urgency_code=urgency_code, priority_code=priority_code)
        db.add(row)
    db.commit()
    db.refresh(row)
    return row
