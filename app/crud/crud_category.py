from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.category import Category
from app.models.team import Team
from app.models.mandal import Mandal
from app.models.zone import Zone

def get_categories(db: Session, include_inactive: bool = False):
    q = db.query(Category)
    if not include_inactive:
        q = q.filter(Category.is_active == True)
    return q.order_by(Category.code).all()

def get_category(db: Session, code: str):
    return db.query(Category).filter(Category.code == code).first()

def get_routing_map(db: Session):
    """Active categories joined to their team's display name. Replaces the
    old hardcoded ROUTING dict: {code: {"label":..., "team":..., "owner":...}}.
    Use this for "what can a NEW ticket route to" - not for label lookups on
    existing tickets, which may reference a since-deactivated category."""
    rows = (db.query(Category, Team)
              .join(Team, Category.team_code == Team.code)
              .filter(Category.is_active == True)
              .all())
    return {c.code: {"label": c.label, "team": c.team_code, "owner": c.default_owner} for c, t in rows}

def get_category_map(db: Session):
    """{code: {label, team}} for ALL categories (active + inactive) - for
    label lookups on tickets that may reference a since-deactivated category."""
    return {c.code: {"label": c.label, "team": c.team_code} for c in db.query(Category).all()}

def get_lt_visible_categories(db: Session):
    """Active categories flagged visible_to_lt - the LT self-service portal's
    category dropdown. Everything internal-only (Application, Network, ...)
    stays hidden by default."""
    return db.query(Category).filter(Category.is_active == True, Category.visible_to_lt == True).order_by(Category.label).all()

def resolve_team(db: Session, category_code: str, mandal_id: int = None):
    """Routing decision for a NEW ticket: {"team":..., "owner":..., "zone_id":...}
    or None if the category is unknown/inactive. If the category is flagged
    route_by_zone and the ticket's Mandal resolves to an active Zone, that
    Zone's team wins; otherwise (most categories, or no Mandal given, or the
    Mandal has no Zone configured yet) falls back to the category's own
    default team - identical to today's behavior. This fallback is what keeps
    routing working correctly before/while the geo hierarchy is populated."""
    c = get_category(db, category_code)
    if not c or not c.is_active:
        return None
    result = {"team": c.team_code, "owner": c.default_owner, "zone_id": None}
    if c.route_by_zone and mandal_id:
        row = (db.query(Mandal, Zone)
                 .join(Zone, Mandal.zone_id == Zone.id)
                 .filter(Mandal.id == mandal_id, Mandal.is_active == True, Zone.is_active == True)
                 .first())
        if row:
            mandal, zone = row
            result = {"team": zone.team_code, "owner": c.default_owner, "zone_id": zone.id}
    return result

def _require_active_team(db: Session, team_code: str) -> str:
    team_code = (team_code or "").strip().upper()
    t = db.query(Team).filter(Team.code == team_code).first()
    if not t or not t.is_active:
        raise HTTPException(400, f"'{team_code}' is not an active team")
    return team_code

def create_category(db: Session, code: str, label: str, team_code: str, default_owner: str = None,
                     route_by_zone: bool = False, visible_to_lt: bool = False) -> Category:
    code = (code or "").strip().upper()
    if not code or not (label or "").strip():
        raise HTTPException(400, "Category code and label are required")
    if db.query(Category).filter(Category.code == code).first():
        raise HTTPException(409, f"Category code '{code}' already exists")
    team_code = _require_active_team(db, team_code)
    c = Category(code=code, label=label.strip(), team_code=team_code,
                 default_owner=(default_owner or "").strip() or None, is_active=True,
                 route_by_zone=bool(route_by_zone), visible_to_lt=bool(visible_to_lt))
    db.add(c)
    db.commit()
    db.refresh(c)
    return c

def update_category(db: Session, code: str, label: str = None, team_code: str = None,
                     default_owner: str = None, is_active: bool = None, route_by_zone: bool = None,
                     visible_to_lt: bool = None) -> Category:
    c = get_category(db, code)
    if not c:
        raise HTTPException(404, "Category not found")
    if label is not None:
        if not label.strip():
            raise HTTPException(400, "Category label cannot be blank")
        c.label = label.strip()
    if team_code is not None:
        c.team_code = _require_active_team(db, team_code)
    if route_by_zone is not None:
        c.route_by_zone = route_by_zone
    if visible_to_lt is not None:
        c.visible_to_lt = visible_to_lt
    if default_owner is not None:
        c.default_owner = default_owner.strip() or None
    if is_active is not None:
        c.is_active = is_active
    db.commit()
    db.refresh(c)
    return c
