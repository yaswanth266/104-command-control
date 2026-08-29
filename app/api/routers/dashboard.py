from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.api.deps import require_admin
from app.services.reporting import build_report_data

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

@router.get("")
def dashboard(district: str = "", mmu_vehicle: str = "", team: str = "", date_from: str = "", date_to: str = "",
              db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    """SOP section 10 - daily CC Manager monitoring + section 15 KPIs.
    All filter params default to empty, which reproduces exactly what this
    endpoint has always returned (see build_report_data)."""
    return build_report_data(db, district=district, mmu_vehicle=mmu_vehicle, team=team,
                              date_from=date_from, date_to=date_to)
