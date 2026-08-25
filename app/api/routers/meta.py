from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.core.config import ROUTING, TEAMS, FLOW, PRIORITY, ROLES
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
        "roles": ROLES
    }
