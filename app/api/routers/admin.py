from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.api.deps import require_admin
from app.schemas.admin import TeamIn, TeamUpdate, CategoryIn, CategoryUpdate, SlaUpdate, UserIn, UserUpdate
from app.crud import crud_team, crud_category, crud_settings, crud_user
from app.crud.crud_admin_event import log_admin_event, get_admin_events

router = APIRouter(prefix="/admin", tags=["admin"])

def _team_out(t):
    return {"code": t.code, "name": t.name, "is_active": t.is_active}

def _category_out(c):
    return {"code": c.code, "label": c.label, "team_code": c.team_code, "default_owner": c.default_owner, "is_active": c.is_active}

def _user_out(u):
    return {"id": u.id, "username": u.username, "name": u.name, "role": u.role, "phone": u.phone, "active": u.active}

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
    c = crud_category.create_category(db, b.code, b.label, b.team_code, b.default_owner)
    log_admin_event(db, current_user, "CATEGORY_CREATED", "category", c.code, f"label={c.label}, team={c.team_code}")
    return _category_out(c)

@router.put("/categories/{code}")
def update_category(code: str, b: CategoryUpdate, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    c = crud_category.update_category(db, code.upper(), label=b.label, team_code=b.team_code,
                                       default_owner=b.default_owner, is_active=b.is_active)
    log_admin_event(db, current_user, "CATEGORY_UPDATED", "category", c.code,
                     f"label={c.label}, team={c.team_code}, is_active={c.is_active}")
    return _category_out(c)

# ---------- SLA & TAT ----------

@router.get("/sla")
def get_sla(db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    from app.crud.crud_ticket import get_tat_map
    return {"sla": crud_settings.get_sla_config(db), "tat": get_tat_map(db)}

@router.put("/sla")
def update_sla(b: SlaUpdate, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    out = {}
    if b.sla:
        out["sla"] = crud_settings.update_sla_config(db, b.sla)
        log_admin_event(db, current_user, "SLA_SETTINGS_UPDATED", "settings", "sla", str(out["sla"]))
    if b.tat:
        out["tat"] = crud_settings.update_tat_map(db, b.tat)
        log_admin_event(db, current_user, "TAT_UPDATED", "settings", "tat", str(out["tat"]))
    if not out:
        raise HTTPException(400, "Nothing to update - provide 'sla' and/or 'tat'")
    return out

# ---------- users ----------
# (GET /users already exists for the roster listing - these add write access)

@router.post("/users")
def create_user(b: UserIn, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    u = crud_user.create_user(db, b.username, b.name, b.role, b.password, b.phone)
    log_admin_event(db, current_user, "USER_CREATED", "user", u.username, f"role={u.role}")
    return _user_out(u)

@router.put("/users/{user_id}")
def update_user(user_id: int, b: UserUpdate, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    u = crud_user.update_user(db, user_id, name=b.name, role=b.role, phone=b.phone,
                               active=b.active, password=b.password)
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
