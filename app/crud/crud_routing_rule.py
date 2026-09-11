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

def _specificity(r: RoutingRule) -> int:
    """4 for a subcategory match, 2 for a district match, 1 for a zone
    match - so cat+sub+district (7) > cat+sub+zone (5) > cat+sub (4) >
    cat+district (2) > cat+zone (1) > cat-only (0)."""
    score = 0
    if r.subcategory_code:
        score += 4
    if r.district_id:
        score += 2
    if r.zone_id:
        score += 1
    return score

def match_rule(db: Session, category_code: str, zone_id: int = None, district_id: int = None,
                subcategory_code: str = None) -> RoutingRule:
    """Most specific active rule for this category. Every narrowing field a
    rule declares (subcategory_code/district_id/zone_id) must match the
    ticket for that rule to be eligible at all; among eligible rules the one
    declaring the most fields wins (see _specificity), tie-broken by code
    for determinism. None if nothing matches - callers fall back to the
    default L1-L4 ladder (see app/services/hierarchy.py)."""
    rules = db.query(RoutingRule).filter(RoutingRule.category_code == category_code,
                                          RoutingRule.is_active == True).all()
    eligible = [
        r for r in rules
        if (not r.subcategory_code or r.subcategory_code == subcategory_code)
        and (not r.district_id or r.district_id == district_id)
        and (not r.zone_id or r.zone_id == zone_id)
    ]
    if not eligible:
        return None
    best_score = max(_specificity(r) for r in eligible)
    return min((r for r in eligible if _specificity(r) == best_score), key=lambda r: r.code)

def _require_active_category(db: Session, category_code: str) -> str:
    category_code = (category_code or "").strip().upper()
    c = db.query(Category).filter(Category.code == category_code).first()
    if not c:
        raise HTTPException(400, f"'{category_code}' is not a known category")
    return category_code

def _require_subcategory_of(db: Session, subcategory_code, category_code: str):
    if not subcategory_code:
        return None
    from app.crud.crud_reason import get_reason
    reason = get_reason(db, subcategory_code.strip().upper())
    if not reason or reason.category_code != category_code:
        raise HTTPException(400, f"'{subcategory_code}' is not a sub-category of '{category_code}'")
    return reason.code

def _require_active_district(db: Session, district_id):
    if not district_id:
        return None
    from app.crud.crud_geo import get_district
    d = get_district(db, district_id)
    if not d or not d.is_active:
        raise HTTPException(400, f"District {district_id} is not active")
    return district_id

def _require_active_zone(db: Session, zone_id):
    if not zone_id:
        return None
    from app.crud.crud_geo import get_zone
    z = get_zone(db, zone_id)
    if not z or not z.is_active:
        raise HTTPException(400, f"Zone {zone_id} is not active")
    return zone_id

# Every L1-L4 field, for create_rule/update_rule below - keeps those two
# functions from repeating the same 12-field boilerplate three times over.
# Precedence at resolution time (username > role > team_code > default
# ladder) lives in app/services/hierarchy.py's _resolve_level(), not here.
_LEVEL_FIELDS = [f"l{n}_{kind}" for n in ("1", "2", "3", "4") for kind in ("team_code", "username", "role")]

def _normalize_level_kwargs(kwargs: dict) -> dict:
    out = {}
    for field, value in kwargs.items():
        if value is None:
            continue
        out[field] = value.strip().lower() if field.endswith("_username") else (value or "").strip().upper() or None
    return out

def create_rule(db: Session, code: str, category_code: str, subcategory_code: str = None,
                 district_id: int = None, zone_id: int = None, **level_kwargs) -> RoutingRule:
    """level_kwargs: any of _LEVEL_FIELDS (l1_team_code, l1_username,
    l1_role, l2_team_code, ... l4_role)."""
    code = (code or "").strip().upper()
    if not code:
        raise HTTPException(400, "Routing rule code is required")
    unknown = set(level_kwargs) - set(_LEVEL_FIELDS)
    if unknown:
        raise HTTPException(400, f"Unknown routing rule field(s): {sorted(unknown)}")
    category_code = _require_active_category(db, category_code)
    subcategory_code = _require_subcategory_of(db, subcategory_code, category_code)
    district_id = _require_active_district(db, district_id)
    zone_id = _require_active_zone(db, zone_id)
    if db.query(RoutingRule).filter(RoutingRule.code == code).first():
        raise HTTPException(409, f"Routing rule code '{code}' already exists")
    existing = db.query(RoutingRule).filter(
        RoutingRule.category_code == category_code, RoutingRule.subcategory_code == subcategory_code,
        RoutingRule.district_id == district_id, RoutingRule.zone_id == zone_id,
        RoutingRule.is_active == True).first()
    if existing:
        raise HTTPException(409, f"An active rule already covers this category/sub-category/district/zone "
                                  f"combination ('{existing.code}')")
    r = RoutingRule(code=code, category_code=category_code, subcategory_code=subcategory_code,
                     district_id=district_id, zone_id=zone_id, is_active=True,
                     **_normalize_level_kwargs(level_kwargs))
    db.add(r)
    db.commit()
    db.refresh(r)
    return r

def update_rule(db: Session, code: str, is_active: bool = None, **level_kwargs) -> RoutingRule:
    """level_kwargs: any of _LEVEL_FIELDS - identity/scope (category,
    sub-category, district, zone) are immutable after create."""
    r = get_rule(db, code)
    if not r:
        raise HTTPException(404, "Routing rule not found")
    unknown = set(level_kwargs) - set(_LEVEL_FIELDS)
    if unknown:
        raise HTTPException(400, f"Unknown routing rule field(s): {sorted(unknown)}")
    for field, value in _normalize_level_kwargs(level_kwargs).items():
        setattr(r, field, value)
    if is_active is not None:
        r.is_active = is_active
    db.commit()
    db.refresh(r)
    return r
