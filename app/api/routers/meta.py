from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.core.config import ROUTING, TEAMS, FLOW, PRIORITY, ROLES, AT_RISK_MINUTES, AT_RISK_FRACTION, CRITICAL_MINUTES, CRITICAL_FRACTION
from app.crud.crud_ticket import get_tat_map

router = APIRouter(prefix="/meta", tags=["meta"])

@router.get("")
def meta(db: Session = Depends(get_db)):
    return {
        "routing": ROUTING,
        "teams": TEAMS,
        "flow": FLOW,
        "priority": PRIORITY,
        "tat": get_tat_map(db),
        "roles": ROLES,
        "sla": {"at_risk_minutes": AT_RISK_MINUTES, "at_risk_fraction": AT_RISK_FRACTION,
                "critical_minutes": CRITICAL_MINUTES, "critical_fraction": CRITICAL_FRACTION},
    }
