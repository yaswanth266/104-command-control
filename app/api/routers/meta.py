from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.core.config import FLOW, IMPACT_LEVELS, URGENCY_LEVELS
from app.crud.crud_ticket import get_tat_map
from app.crud.crud_category import get_routing_map
from app.crud.crud_team import get_team_map
from app.crud.crud_settings import get_sla_config
from app.crud.crud_user import get_valid_roles
from app.crud.crud_ticket_type import get_ticket_type_map
from app.crud.crud_reason import get_reasons
from app.crud.crud_priority import get_priority_map, get_priority_full_map
from app.crud.crud_priority_matrix import get_matrix_map

router = APIRouter(prefix="/meta", tags=["meta"])

def _subcategory_map(db: Session):
    """{code: {label, category_code, ticket_type}} for active Sub-Categories
    (ccc_reason) - not restricted to visible_to_lt, since Register Call and
    /intake can select a Sub-Category too, not just the LT portal."""
    return {r.code: {"label": r.label, "category_code": r.category_code, "ticket_type": r.ticket_type}
            for r in get_reasons(db)}

@router.get("")
def meta(db: Session = Depends(get_db)):
    return {
        "routing": get_routing_map(db),
        "teams": get_team_map(db),
        "flow": FLOW,
        "priority": get_priority_map(db),
        "priorities": get_priority_full_map(db),
        "impact_levels": IMPACT_LEVELS,
        "urgency_levels": URGENCY_LEVELS,
        "priority_matrix": get_matrix_map(db),
        "tat": get_tat_map(db),
        "roles": get_valid_roles(db),
        "sla": get_sla_config(db),
        "ticket_types": get_ticket_type_map(db),
        "subcategories": _subcategory_map(db),
    }
