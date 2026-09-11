from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.routing_rule import RoutingRule
from app.models.category import Category

def get_rules(db: Session, include_inactive: bool = False):
    q = db.query(RoutingRule)
    if not include_inactive:
        q = q.filter(RoutingRule.is_active == True)
    return q.order_by(RoutingRule.category_code, RoutingRule.code).all()

def get_rule(db: Session, code: str):
    return db.query(RoutingRule).filter(RoutingRule.code == code).first()

def match_rule(db: Session, category_code: str, zone_id: int = None):
    """Most specific active rule for this category: category+zone beats
    category-only. None if nothing matches - callers fall back to the
    default L1-L4 ladder (see app/services/hierarchy.py)."""
    q = db.query(RoutingRule).filter(RoutingRule.category_code == category_code, RoutingRule.is_active == True)
    if zone_id:
        row = q.filter(RoutingRule.zone_id == zone_id).first()
        if row:
            return row
    return q.filter(RoutingRule.zone_id.is_(None)).first()

def create_rule(db: Session, code: str, category_code: str, zone_id: int = None,
                 l1_team_code: str = None, l1_username: str = None, l2_username: str = None,
                 l3_username: str = None, l4_username: str = None) -> RoutingRule:
    code = (code or "").strip().upper()
    category_code = (category_code or "").strip().upper()
    if not code or not category_code:
        raise HTTPException(400, "Routing rule code and category are required")
    if not db.query(Category).filter(Category.code == category_code).first():
        raise HTTPException(400, f"'{category_code}' is not a known category")
    if db.query(RoutingRule).filter(RoutingRule.code == code).first():
        raise HTTPException(409, f"Routing rule code '{code}' already exists")
    existing = db.query(RoutingRule).filter(RoutingRule.category_code == category_code,
                                             RoutingRule.zone_id == zone_id, RoutingRule.is_active == True).first()
    if existing:
        raise HTTPException(409, f"An active rule already covers this category/zone combination ('{existing.code}')")
    r = RoutingRule(code=code, category_code=category_code, zone_id=zone_id,
                     l1_team_code=(l1_team_code or "").strip().upper() or None,
                     l1_username=(l1_username or "").strip().lower() or None,
                     l2_username=(l2_username or "").strip().lower() or None,
                     l3_username=(l3_username or "").strip().lower() or None,
                     l4_username=(l4_username or "").strip().lower() or None,
                     is_active=True)
    db.add(r)
    db.commit()
    db.refresh(r)
    return r

def update_rule(db: Session, code: str, l1_team_code: str = None, l1_username: str = None,
                 l2_username: str = None, l3_username: str = None, l4_username: str = None,
                 is_active: bool = None) -> RoutingRule:
    r = get_rule(db, code)
    if not r:
        raise HTTPException(404, "Routing rule not found")
    if l1_team_code is not None:
        r.l1_team_code = l1_team_code.strip().upper() or None
    if l1_username is not None:
        r.l1_username = l1_username.strip().lower() or None
    if l2_username is not None:
        r.l2_username = l2_username.strip().lower() or None
    if l3_username is not None:
        r.l3_username = l3_username.strip().lower() or None
    if l4_username is not None:
        r.l4_username = l4_username.strip().lower() or None
    if is_active is not None:
        r.is_active = is_active
    db.commit()
    db.refresh(r)
    return r
