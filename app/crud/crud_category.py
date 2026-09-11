from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.category import Category
from app.models.team import Team
from app.models.mandal import Mandal
from app.models.zone import Zone
from app.models.ticket_type import TicketType

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

def route_ticket(db: Session, category_code: str, subcategory_code: str = None,
                  district_id: int = None, mandal_id: int = None):
    """Routing decision for a NEW ticket: {"team", "owner", "zone_id", "rule"}
    or None if the category is unknown/inactive. Precedence:
    1. A matching Routing Rule's l1_team_code (see crud_routing_rule.match_rule
       - category+sub-category+district/zone specificity), so the team a
       ticket is filed against and its L1 occupant can never disagree.
    2. If the category is flagged route_by_zone and the ticket's Mandal
       resolves to an active Zone, that Zone's team.
    3. The category's own default team - identical to pre-Phase-5 behavior.
    This fallback chain is what keeps routing working correctly before/while
    the geo hierarchy and routing rules are populated. The matched `rule` is
    returned so callers (ticket creation, hierarchy.resolve_hierarchy) reuse
    it instead of matching a second time."""
    c = get_category(db, category_code)
    if not c or not c.is_active:
        return None

    zone_id = None
    if c.route_by_zone and mandal_id:
        row = (db.query(Mandal, Zone)
                 .join(Zone, Mandal.zone_id == Zone.id)
                 .filter(Mandal.id == mandal_id, Mandal.is_active == True, Zone.is_active == True)
                 .first())
        if row:
            zone_id = row[1].id

    from app.crud.crud_routing_rule import match_rule
    rule = match_rule(db, category_code, zone_id=zone_id, district_id=district_id,
                       subcategory_code=subcategory_code)

    if rule and rule.l1_team_code:
        return {"team": rule.l1_team_code, "owner": c.default_owner, "zone_id": zone_id, "rule": rule}
    if zone_id:
        zone = db.query(Zone).filter(Zone.id == zone_id).first()
        return {"team": zone.team_code, "owner": c.default_owner, "zone_id": zone_id, "rule": rule}
    return {"team": c.team_code, "owner": c.default_owner, "zone_id": zone_id, "rule": rule}

def resolve_team(db: Session, category_code: str, mandal_id: int = None):
    """Back-compat wrapper over route_ticket() for callers that don't yet
    pass sub-category/district (e.g. the routing preview on Register Call
    before the form is fully filled in). Drops the "rule" key."""
    result = route_ticket(db, category_code, mandal_id=mandal_id)
    if result is None:
        return None
    return {"team": result["team"], "owner": result["owner"], "zone_id": result["zone_id"]}

def _require_active_team(db: Session, team_code: str) -> str:
    team_code = (team_code or "").strip().upper()
    t = db.query(Team).filter(Team.code == team_code).first()
    if not t or not t.is_active:
        raise HTTPException(400, f"'{team_code}' is not an active team")
    return team_code

def _require_active_ticket_type(db: Session, ticket_type: str) -> str:
    ticket_type = (ticket_type or "").strip().upper()
    tt = db.query(TicketType).filter(TicketType.code == ticket_type).first()
    if not tt or not tt.is_active:
        raise HTTPException(400, f"'{ticket_type}' is not an active ticket type")
    return ticket_type

def create_category(db: Session, code: str, label: str, team_code: str, default_owner: str = None,
                     route_by_zone: bool = False, visible_to_lt: bool = False, ticket_type: str = None) -> Category:
    code = (code or "").strip().upper()
    if not code or not (label or "").strip():
        raise HTTPException(400, "Category code and label are required")
    if db.query(Category).filter(Category.code == code).first():
        raise HTTPException(409, f"Category code '{code}' already exists")
    team_code = _require_active_team(db, team_code)
    ticket_type = _require_active_ticket_type(db, ticket_type or "INCIDENT")
    c = Category(code=code, label=label.strip(), team_code=team_code,
                 default_owner=(default_owner or "").strip() or None, is_active=True,
                 route_by_zone=bool(route_by_zone), visible_to_lt=bool(visible_to_lt), ticket_type=ticket_type)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c

def update_category(db: Session, code: str, label: str = None, team_code: str = None,
                     default_owner: str = None, is_active: bool = None, route_by_zone: bool = None,
                     visible_to_lt: bool = None, ticket_type: str = None) -> Category:
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
    if ticket_type is not None:
        c.ticket_type = _require_active_ticket_type(db, ticket_type)
    if default_owner is not None:
        c.default_owner = default_owner.strip() or None
    if is_active is not None:
        c.is_active = is_active
    db.commit()
    db.refresh(c)
    return c
