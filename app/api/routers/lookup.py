from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.api.deps import get_current_user
from app.crud import crud_geo, crud_vehicle, crud_reason, crud_machine, crud_category

router = APIRouter(tags=["lookup"])

# Any authenticated user can read these - they're just the searchable-dropdown
# data sources for Register Call, kept separate from the admin CRUD endpoints
# (which manage the master data) and out of /meta (which is small, fully
# cached reference data - Districts/Mandals/Vehicles can be large lists).

@router.get("/districts")
def list_districts(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    return [{"id": d.id, "name": d.name} for d in crud_geo.get_districts(db)]

@router.get("/mandals")
def list_mandals(district_id: Optional[int] = None, db: Session = Depends(get_db),
                  current_user: dict = Depends(get_current_user)):
    return [{"id": m.id, "name": m.name, "district_id": m.district_id, "zone_id": m.zone_id}
            for m in crud_geo.get_mandals(db, district_id=district_id)]

@router.get("/vehicles/search")
def search_vehicles(q: str = "", db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    return [{"id": v.id, "registration_no": v.registration_no, "last_mandal_id": v.last_mandal_id}
            for v in crud_vehicle.search_vehicles(db, q)]

@router.get("/reasons")
def list_reasons(category: str = "", db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    return [{"code": r.code, "category_code": r.category_code, "label": r.label}
            for r in crud_reason.get_reasons(db, category_code=category or None)]

@router.get("/machines/search")
def search_machines(q: str = "", db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    return [{"id": m.id, "name": m.name} for m in crud_machine.search_machines(db, q)]

@router.get("/lt-categories")
def list_lt_categories(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """LT self-service portal's category dropdown - only categories flagged
    visible_to_lt, unlike /meta's full routing map (which is department-facing)."""
    return [{"code": c.code, "label": c.label} for c in crud_category.get_lt_visible_categories(db)]
