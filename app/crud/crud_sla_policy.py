from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.sla_policy import SlaPolicy
from app.core.config import TAT_DEFAULT

def get_policies(db: Session, include_inactive: bool = False):
    q = db.query(SlaPolicy)
    if not include_inactive:
        q = q.filter(SlaPolicy.is_active == True)
    return q.order_by(SlaPolicy.priority_code, SlaPolicy.code).all()

def get_policy(db: Session, code: str):
    return db.query(SlaPolicy).filter(SlaPolicy.code == code).first()

def get_baseline_policy(db: Session, priority_code: str):
    """The scope-less row for this priority (subcategory/category/ticket_type
    all NULL) - what get_tat_map()/PUT /admin/sla's `tat` patch read and write."""
    return (db.query(SlaPolicy)
              .filter(SlaPolicy.priority_code == priority_code,
                      SlaPolicy.subcategory_code.is_(None),
                      SlaPolicy.category_code.is_(None),
                      SlaPolicy.ticket_type.is_(None))
              .first())

def get_baseline_tat_map(db: Session) -> dict:
    """{priority_code: resolution_mins} for every baseline policy row -
    replaces the old ccc_config['tat'] JSON blob. Falls back to TAT_DEFAULT
    for any priority with no baseline row yet (should not happen post-
    migration, but keeps this safe if a priority is added without one)."""
    rows = (db.query(SlaPolicy)
              .filter(SlaPolicy.subcategory_code.is_(None),
                      SlaPolicy.category_code.is_(None),
                      SlaPolicy.ticket_type.is_(None),
                      SlaPolicy.is_active == True)
              .all())
    out = dict(TAT_DEFAULT)
    out.update({r.priority_code: r.resolution_mins for r in rows})
    return out

def upsert_baseline_resolution_mins(db: Session, priority_code: str, resolution_mins: int) -> SlaPolicy:
    row = get_baseline_policy(db, priority_code)
    if row:
        row.resolution_mins = resolution_mins
    else:
        row = SlaPolicy(code=f"BASELINE-{priority_code}", priority_code=priority_code,
                         resolution_mins=resolution_mins, calendar_code="DEFAULT-24X7",
                         pause_statuses=["PENDING"], is_active=True)
        db.add(row)
    db.commit()
    db.refresh(row)
    return row

def create_policy(db: Session, code: str, priority_code: str, resolution_mins: int, calendar_code: str,
                   subcategory_code: str = None, category_code: str = None, ticket_type: str = None,
                   response_mins: int = None) -> SlaPolicy:
    code = (code or "").strip().upper()
    priority_code = (priority_code or "").strip().upper()
    if not code:
        raise HTTPException(400, "Policy code is required")
    if db.query(SlaPolicy).filter(SlaPolicy.code == code).first():
        raise HTTPException(409, f"SLA Policy code '{code}' already exists")
    if not resolution_mins or resolution_mins <= 0:
        raise HTTPException(400, "resolution_mins must be a positive number of minutes")
    if response_mins is not None and response_mins <= 0:
        raise HTTPException(400, "response_mins must be a positive number of minutes")
    subcategory_code = (subcategory_code or "").strip().upper() or None
    category_code = (category_code or "").strip().upper() or None
    ticket_type = (ticket_type or "").strip().upper() or None
    p = SlaPolicy(code=code, priority_code=priority_code, resolution_mins=resolution_mins,
                  response_mins=response_mins, calendar_code=(calendar_code or "DEFAULT-24X7").strip().upper(),
                  subcategory_code=subcategory_code, category_code=category_code, ticket_type=ticket_type,
                  pause_statuses=["PENDING"], is_active=True)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p

def update_policy(db: Session, code: str, resolution_mins: int = None, response_mins: int = None,
                   calendar_code: str = None, is_active: bool = None) -> SlaPolicy:
    p = get_policy(db, code)
    if not p:
        raise HTTPException(404, "SLA Policy not found")
    if resolution_mins is not None:
        if resolution_mins <= 0:
            raise HTTPException(400, "resolution_mins must be a positive number of minutes")
        p.resolution_mins = resolution_mins
    if response_mins is not None:
        if response_mins <= 0:
            raise HTTPException(400, "response_mins must be a positive number of minutes")
        p.response_mins = response_mins
    if calendar_code is not None:
        p.calendar_code = calendar_code.strip().upper()
    if is_active is not None:
        p.is_active = is_active
    db.commit()
    db.refresh(p)
    return p
