from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.district import District
from app.models.mandal import Mandal
from app.models.zone import Zone
from app.models.team import Team

# ---------- districts ----------

def get_districts(db: Session, include_inactive: bool = False):
    q = db.query(District)
    if not include_inactive:
        q = q.filter(District.is_active == True)
    return q.order_by(District.name).all()

def get_district(db: Session, district_id: int):
    return db.query(District).filter(District.id == district_id).first()

def create_district(db: Session, name: str) -> District:
    name = (name or "").strip()
    if not name:
        raise HTTPException(400, "District name is required")
    if db.query(District).filter(District.name == name).first():
        raise HTTPException(409, f"District '{name}' already exists")
    d = District(name=name, is_active=True)
    db.add(d)
    db.commit()
    db.refresh(d)
    return d

def update_district(db: Session, district_id: int, name: str = None, is_active: bool = None) -> District:
    d = get_district(db, district_id)
    if not d:
        raise HTTPException(404, "District not found")
    if is_active is False and d.is_active:
        active_mandals = db.query(Mandal).filter(Mandal.district_id == district_id, Mandal.is_active == True).count()
        if active_mandals:
            raise HTTPException(409, f"{active_mandals} active Mandal(s) still belong to this District - "
                                      "reassign or deactivate them first")
    if name is not None:
        if not name.strip():
            raise HTTPException(400, "District name cannot be blank")
        d.name = name.strip()
    if is_active is not None:
        d.is_active = is_active
    db.commit()
    db.refresh(d)
    return d

# ---------- zones ----------

def get_zones(db: Session, include_inactive: bool = False):
    q = db.query(Zone)
    if not include_inactive:
        q = q.filter(Zone.is_active == True)
    return q.order_by(Zone.name).all()

def get_zone(db: Session, zone_id: int):
    return db.query(Zone).filter(Zone.id == zone_id).first()

def _require_active_team(db: Session, team_code: str) -> str:
    team_code = (team_code or "").strip().upper()
    t = db.query(Team).filter(Team.code == team_code).first()
    if not t or not t.is_active:
        raise HTTPException(400, f"'{team_code}' is not an active team")
    return team_code

def create_zone(db: Session, name: str, team_code: str) -> Zone:
    name = (name or "").strip()
    if not name:
        raise HTTPException(400, "Zone name is required")
    if db.query(Zone).filter(Zone.name == name).first():
        raise HTTPException(409, f"Zone '{name}' already exists")
    team_code = _require_active_team(db, team_code)
    z = Zone(name=name, team_code=team_code, is_active=True)
    db.add(z)
    db.commit()
    db.refresh(z)
    return z

def update_zone(db: Session, zone_id: int, name: str = None, team_code: str = None, is_active: bool = None) -> Zone:
    z = get_zone(db, zone_id)
    if not z:
        raise HTTPException(404, "Zone not found")
    if is_active is False and z.is_active:
        active_mandals = db.query(Mandal).filter(Mandal.zone_id == zone_id, Mandal.is_active == True).count()
        if active_mandals:
            raise HTTPException(409, f"{active_mandals} active Mandal(s) still route through this Zone - "
                                      "reassign or deactivate them first")
    if name is not None:
        if not name.strip():
            raise HTTPException(400, "Zone name cannot be blank")
        z.name = name.strip()
    if team_code is not None:
        z.team_code = _require_active_team(db, team_code)
    if is_active is not None:
        z.is_active = is_active
    db.commit()
    db.refresh(z)
    return z

# ---------- mandals ----------

def get_mandals(db: Session, district_id: int = None, include_inactive: bool = False):
    q = db.query(Mandal)
    if district_id is not None:
        q = q.filter(Mandal.district_id == district_id)
    if not include_inactive:
        q = q.filter(Mandal.is_active == True)
    return q.order_by(Mandal.name).all()

def get_mandal(db: Session, mandal_id: int):
    return db.query(Mandal).filter(Mandal.id == mandal_id).first()

def _require_active_district(db: Session, district_id: int) -> int:
    d = get_district(db, district_id)
    if not d or not d.is_active:
        raise HTTPException(400, f"District {district_id} is not active")
    return district_id

def _optional_active_zone(db: Session, zone_id):
    if zone_id is None:
        return None
    z = get_zone(db, zone_id)
    if not z or not z.is_active:
        raise HTTPException(400, f"Zone {zone_id} is not active")
    return zone_id

def create_mandal(db: Session, name: str, district_id: int, zone_id: int = None) -> Mandal:
    name = (name or "").strip()
    if not name:
        raise HTTPException(400, "Mandal name is required")
    district_id = _require_active_district(db, district_id)
    if db.query(Mandal).filter(Mandal.district_id == district_id, Mandal.name == name).first():
        raise HTTPException(409, f"Mandal '{name}' already exists in this District")
    zone_id = _optional_active_zone(db, zone_id)
    m = Mandal(name=name, district_id=district_id, zone_id=zone_id, is_active=True)
    db.add(m)
    db.commit()
    db.refresh(m)
    return m

def update_mandal(db: Session, mandal_id: int, name: str = None, district_id: int = None,
                   zone_id=None, is_active: bool = None) -> Mandal:
    m = get_mandal(db, mandal_id)
    if not m:
        raise HTTPException(404, "Mandal not found")
    if name is not None:
        if not name.strip():
            raise HTTPException(400, "Mandal name cannot be blank")
        m.name = name.strip()
    if district_id is not None:
        m.district_id = _require_active_district(db, district_id)
    if zone_id is not None:
        m.zone_id = _optional_active_zone(db, None if zone_id == 0 else zone_id)
    if is_active is not None:
        m.is_active = is_active
    db.commit()
    db.refresh(m)
    return m
