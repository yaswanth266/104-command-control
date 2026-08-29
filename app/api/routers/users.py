from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.api.deps import require_admin, get_current_user
from app.crud.crud_user import get_users, get_active_users_by_role

router = APIRouter(prefix="/users", tags=["users"])

@router.get("")
def list_users(q: str = "", db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    users = get_users(db, q)
    return [
        {"id": u.id, "username": u.username, "name": u.name, "role": u.role, "phone": u.phone, "active": u.active,
         "hr_emp_code": u.hr_emp_code, "reporting_manager_id": u.reporting_manager_id,
         "is_team_manager": u.is_team_manager, "vehicle_id": u.vehicle_id,
         "district_id": u.district_id, "mandal_id": u.mandal_id}
        for u in users
    ]

@router.get("/team-roster")
def team_roster(team: Optional[str] = None, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """Backs the Team Manager 'Assign to' picker - deliberately lighter than
    GET /users (which is CC-Manager-only and returns everyone): a Team
    Manager may only ever see their own team's roster, not the whole org."""
    if current_user["role"] == "CC_MANAGER":
        target_team = (team or "").strip().upper()
        if not target_team:
            raise HTTPException(400, "Provide ?team=CODE")
    elif current_user.get("is_team_manager"):
        target_team = current_user["role"]
    else:
        raise HTTPException(403, "Only a Team Executive or the Global Team Executive may view a team roster")
    return [{"username": u.username, "name": u.name} for u in get_active_users_by_role(db, target_team)]
