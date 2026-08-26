from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.core.config import FLOW, PRIORITY
from app.crud.crud_ticket import get_tat_map
from app.crud.crud_category import get_routing_map
from app.crud.crud_team import get_team_map
from app.crud.crud_settings import get_sla_config
from app.crud.crud_user import get_valid_roles

router = APIRouter(prefix="/meta", tags=["meta"])

@router.get("")
def meta(db: Session = Depends(get_db)):
    return {
        "routing": get_routing_map(db),
        "teams": get_team_map(db),
        "flow": FLOW,
        "priority": PRIORITY,
        "tat": get_tat_map(db),
        "roles": get_valid_roles(db),
        "sla": get_sla_config(db),
    }
