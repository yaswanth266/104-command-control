from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.api.deps import require_admin
from app.schemas.admin import (TeamIn, TeamUpdate, CategoryIn, CategoryUpdate, SlaUpdate, UserIn, UserUpdate,
                                DistrictIn, DistrictUpdate, ZoneIn, ZoneUpdate, MandalIn, MandalUpdate,
                                VehicleIn, VehicleUpdate)
from app.crud import crud_team, crud_category, crud_settings, crud_user, crud_geo, crud_vehicle
from app.crud.crud_admin_event import log_admin_event, get_admin_events

router = APIRouter(prefix="/admin", tags=["admin"])

def _team_out(t):
    return {"code": t.code, "name": t.name, "is_active": t.is_active}

def _category_out(c):
    return {"code": c.code, "label": c.label, "team_code": c.team_code, "default_owner": c.default_owner,
            "is_active": c.is_active, "route_by_zone": c.route_by_zone}

def _user_out(u):
    return {"id": u.id, "username": u.username, "name": u.name, "role": u.role, "phone": u.phone, "active": u.active,
            "hr_emp_code": u.hr_emp_code, "reporting_manager_id": u.reporting_manager_id,
            "is_team_manager": u.is_team_manager}

def _district_out(d):
    return {"id": d.id, "name": d.name, "is_active": d.is_active}

def _zone_out(z):
    return {"id": z.id, "name": z.name, "team_code": z.team_code, "is_active": z.is_active}

def _mandal_out(m):
    return {"id": m.id, "name": m.name, "district_id": m.district_id, "zone_id": m.zone_id, "is_active": m.is_active}

def _vehicle_out(v):
    return {"id": v.id, "registration_no": v.registration_no, "last_mandal_id": v.last_mandal_id, "is_active": v.is_active}

# ---------- teams ----------

@router.get("/teams")
def list_teams(db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    return [_team_out(t) for t in crud_team.get_teams(db, include_inactive=True)]

@router.post("/teams")
def create_team(b: TeamIn, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    t = crud_team.create_team(db, b.code, b.name)
    log_admin_event(db, current_user, "TEAM_CREATED", "team", t.code, f"name={t.name}")
    return _team_out(t)

@router.put("/teams/{code}")
def update_team(code: str, b: TeamUpdate, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    t = crud_team.update_team(db, code.upper(), name=b.name, is_active=b.is_active)
    log_admin_event(db, current_user, "TEAM_UPDATED", "team", t.code, f"name={t.name}, is_active={t.is_active}")
    return _team_out(t)

# ---------- categories ----------

@router.get("/categories")
def list_categories(db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    return [_category_out(c) for c in crud_category.get_categories(db, include_inactive=True)]

@router.post("/categories")
def create_category(b: CategoryIn, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    c = crud_category.create_category(db, b.code, b.label, b.team_code, b.default_owner, b.route_by_zone)
    log_admin_event(db, current_user, "CATEGORY_CREATED", "category", c.code, f"label={c.label}, team={c.team_code}")
    return _category_out(c)

@router.put("/categories/{code}")
def update_category(code: str, b: CategoryUpdate, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    c = crud_category.update_category(db, code.upper(), label=b.label, team_code=b.team_code,
                                       default_owner=b.default_owner, is_active=b.is_active, route_by_zone=b.route_by_zone)
    log_admin_event(db, current_user, "CATEGORY_UPDATED", "category", c.code,
                     f"label={c.label}, team={c.team_code}, is_active={c.is_active}, route_by_zone={c.route_by_zone}")
    return _category_out(c)

# ---------- geography ----------

@router.get("/districts")
def list_districts(db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    return [_district_out(d) for d in crud_geo.get_districts(db, include_inactive=True)]

@router.post("/districts")
def create_district(b: DistrictIn, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    d = crud_geo.create_district(db, b.name)
    log_admin_event(db, current_user, "DISTRICT_CREATED", "district", str(d.id), f"name={d.name}")
    return _district_out(d)

@router.put("/districts/{district_id}")
def update_district(district_id: int, b: DistrictUpdate, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    d = crud_geo.update_district(db, district_id, name=b.name, is_active=b.is_active)
    log_admin_event(db, current_user, "DISTRICT_UPDATED", "district", str(d.id), f"name={d.name}, is_active={d.is_active}")
    return _district_out(d)

@router.get("/zones")
def list_zones(db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    return [_zone_out(z) for z in crud_geo.get_zones(db, include_inactive=True)]

@router.post("/zones")
def create_zone(b: ZoneIn, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    z = crud_geo.create_zone(db, b.name, b.team_code)
    log_admin_event(db, current_user, "ZONE_CREATED", "zone", str(z.id), f"name={z.name}, team={z.team_code}")
    return _zone_out(z)

@router.put("/zones/{zone_id}")
def update_zone(zone_id: int, b: ZoneUpdate, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    z = crud_geo.update_zone(db, zone_id, name=b.name, team_code=b.team_code, is_active=b.is_active)
    log_admin_event(db, current_user, "ZONE_UPDATED", "zone", str(z.id), f"name={z.name}, team={z.team_code}, is_active={z.is_active}")
    return _zone_out(z)

@router.get("/mandals")
def list_mandals(district_id: int = None, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    return [_mandal_out(m) for m in crud_geo.get_mandals(db, district_id=district_id, include_inactive=True)]

@router.post("/mandals")
def create_mandal(b: MandalIn, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    m = crud_geo.create_mandal(db, b.name, b.district_id, b.zone_id)
    log_admin_event(db, current_user, "MANDAL_CREATED", "mandal", str(m.id), f"name={m.name}, district_id={m.district_id}")
    return _mandal_out(m)

@router.put("/mandals/{mandal_id}")
def update_mandal(mandal_id: int, b: MandalUpdate, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    m = crud_geo.update_mandal(db, mandal_id, name=b.name, district_id=b.district_id, zone_id=b.zone_id, is_active=b.is_active)
    log_admin_event(db, current_user, "MANDAL_UPDATED", "mandal", str(m.id),
                     f"name={m.name}, district_id={m.district_id}, zone_id={m.zone_id}, is_active={m.is_active}")
    return _mandal_out(m)

# ---------- vehicles ----------

@router.get("/vehicles")
def list_vehicles(db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    return [_vehicle_out(v) for v in crud_vehicle.get_vehicles(db, include_inactive=True)]

@router.post("/vehicles")
def create_vehicle(b: VehicleIn, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    v = crud_vehicle.create_vehicle(db, b.registration_no, b.last_mandal_id)
    log_admin_event(db, current_user, "VEHICLE_CREATED", "vehicle", str(v.id), f"registration_no={v.registration_no}")
    return _vehicle_out(v)

@router.put("/vehicles/{vehicle_id}")
def update_vehicle(vehicle_id: int, b: VehicleUpdate, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    v = crud_vehicle.update_vehicle(db, vehicle_id, last_mandal_id=b.last_mandal_id, is_active=b.is_active)
    log_admin_event(db, current_user, "VEHICLE_UPDATED", "vehicle", str(v.id), f"is_active={v.is_active}")
    return _vehicle_out(v)

# ---------- SLA & TAT ----------

@router.get("/sla")
def get_sla(db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    from app.crud.crud_ticket import get_tat_map
    return {"sla": crud_settings.get_sla_config(db), "tat": get_tat_map(db), "vip_keywords": crud_settings.get_vip_keywords(db)}

@router.put("/sla")
def update_sla(b: SlaUpdate, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    out = {}
    if b.sla:
        out["sla"] = crud_settings.update_sla_config(db, b.sla)
        log_admin_event(db, current_user, "SLA_SETTINGS_UPDATED", "settings", "sla", str(out["sla"]))
    if b.tat:
        out["tat"] = crud_settings.update_tat_map(db, b.tat)
        log_admin_event(db, current_user, "TAT_UPDATED", "settings", "tat", str(out["tat"]))
    if b.vip_keywords is not None:
        out["vip_keywords"] = crud_settings.update_vip_keywords(db, b.vip_keywords)
        log_admin_event(db, current_user, "VIP_KEYWORDS_UPDATED", "settings", "vip_keywords", str(out["vip_keywords"]))
    if not out:
        raise HTTPException(400, "Nothing to update - provide 'sla', 'tat' and/or 'vip_keywords'")
    return out

# ---------- users ----------
# (GET /users already exists for the roster listing - these add write access)

@router.post("/users")
def create_user(b: UserIn, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    u = crud_user.create_user(db, b.username, b.name, b.role, b.password, b.phone,
                               b.hr_emp_code, b.reporting_manager_id, b.is_team_manager)
    log_admin_event(db, current_user, "USER_CREATED", "user", u.username, f"role={u.role}")
    return _user_out(u)

@router.put("/users/{user_id}")
def update_user(user_id: int, b: UserUpdate, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    u = crud_user.update_user(db, user_id, name=b.name, role=b.role, phone=b.phone,
                               active=b.active, password=b.password, hr_emp_code=b.hr_emp_code,
                               reporting_manager_id=b.reporting_manager_id, is_team_manager=b.is_team_manager)
    detail = f"role={u.role}, active={u.active}" + (", password reset" if b.password else "")
    log_admin_event(db, current_user, "USER_UPDATED", "user", u.username, detail)
    return _user_out(u)

@router.get("/roles")
def list_valid_roles(db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    return crud_user.get_valid_roles(db)

# ---------- audit ----------

@router.get("/audit")
def list_admin_events(limit: int = 100, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    rows = get_admin_events(db, limit=min(limit, 500))
    return [{"id": e.id, "at": e.at.strftime("%Y-%m-%d %H:%M") if e.at else None, "actor": e.actor,
             "actor_role": e.actor_role, "action": e.action, "entity_type": e.entity_type,
             "entity_id": e.entity_id, "detail": e.detail} for e in rows]
