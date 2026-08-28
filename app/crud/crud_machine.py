from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.machine import Machine

def search_machines(db: Session, q: str = "", limit: int = 20):
    query = db.query(Machine).filter(Machine.is_active == True)
    if q:
        query = query.filter(Machine.name.like(f"%{q.strip()}%"))
    return query.order_by(Machine.name).limit(min(limit, 50)).all()

def get_machines(db: Session, include_inactive: bool = False):
    q = db.query(Machine)
    if not include_inactive:
        q = q.filter(Machine.is_active == True)
    return q.order_by(Machine.name).all()

def get_machine(db: Session, machine_id: int):
    return db.query(Machine).filter(Machine.id == machine_id).first()

def create_machine(db: Session, name: str) -> Machine:
    name = (name or "").strip()
    if not name:
        raise HTTPException(400, "Machine name is required")
    if db.query(Machine).filter(Machine.name == name).first():
        raise HTTPException(409, f"Machine '{name}' already exists")
    m = Machine(name=name, is_active=True)
    db.add(m)
    db.commit()
    db.refresh(m)
    return m

def update_machine(db: Session, machine_id: int, is_active: bool = None) -> Machine:
    m = get_machine(db, machine_id)
    if not m:
        raise HTTPException(404, "Machine not found")
    if is_active is not None:
        m.is_active = is_active
    db.commit()
    db.refresh(m)
    return m
