from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.vehicle import Vehicle

def search_vehicles(db: Session, q: str = "", limit: int = 20):
    """Backs the async type-ahead - deliberately capped and match-limited so
    a fleet of thousands never gets dumped to the client at once."""
    query = db.query(Vehicle).filter(Vehicle.is_active == True)
    if q:
        query = query.filter(Vehicle.registration_no.like(f"%{q.strip().upper()}%"))
    return query.order_by(Vehicle.registration_no).limit(min(limit, 50)).all()

def get_vehicles(db: Session, include_inactive: bool = False):
    q = db.query(Vehicle)
    if not include_inactive:
        q = q.filter(Vehicle.is_active == True)
    return q.order_by(Vehicle.registration_no).all()

def get_vehicle(db: Session, vehicle_id: int):
    return db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()

def create_vehicle(db: Session, registration_no: str, last_mandal_id: int = None) -> Vehicle:
    registration_no = (registration_no or "").strip().upper()
    if not registration_no:
        raise HTTPException(400, "Registration number is required")
    if db.query(Vehicle).filter(Vehicle.registration_no == registration_no).first():
        raise HTTPException(409, f"Vehicle '{registration_no}' already exists")
    v = Vehicle(registration_no=registration_no, last_mandal_id=last_mandal_id, is_active=True)
    db.add(v)
    db.commit()
    db.refresh(v)
    return v

def update_vehicle(db: Session, vehicle_id: int, last_mandal_id=None, is_active: bool = None) -> Vehicle:
    v = get_vehicle(db, vehicle_id)
    if not v:
        raise HTTPException(404, "Vehicle not found")
    if last_mandal_id is not None:
        v.last_mandal_id = None if last_mandal_id == 0 else last_mandal_id
    if is_active is not None:
        v.is_active = is_active
    db.commit()
    db.refresh(v)
    return v
