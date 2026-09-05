from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.api.deps import require_admin, get_current_user
from app.crud.crud_user import get_users, get_active_users_by_role, get_user, get_user_by_username, change_own_password
from app.crud.crud_geo import get_district, get_mandal
from app.crud.crud_vehicle import get_vehicle
from app.crud.crud_team import get_team
from app.schemas.auth import ChangePasswordIn

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

@router.get("/me")
def get_my_profile(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """Everything a logged-in user needs to see about their own account: which
    District/Mandal/Vehicle their profile is pinned to (this is what an LT's
    field tickets are auto-tagged with, and what routes them - see
    app/api/routers/lt.py), their team, and who they report to."""
    u = get_user_by_username(db, current_user["username"])
    if not u:
        raise HTTPException(404, "User profile not found")

    district = get_district(db, u.district_id) if u.district_id else None
    mandal = get_mandal(db, u.mandal_id) if u.mandal_id else None
    vehicle = get_vehicle(db, u.vehicle_id) if u.vehicle_id else None
    manager = get_user(db, u.reporting_manager_id) if u.reporting_manager_id else None
    team = get_team(db, u.role)

    return {
        "username": u.username,
        "name": u.name,
        "role": u.role,
        "phone": u.phone,
        "hr_emp_code": u.hr_emp_code,
        "is_team_manager": u.is_team_manager,
        "team": {"code": team.code, "name": team.name} if team else None,
        "district": {"id": district.id, "name": district.name} if district else None,
        "mandal": {"id": mandal.id, "name": mandal.name} if mandal else None,
        "vehicle": {"id": vehicle.id, "registration_no": vehicle.registration_no} if vehicle else None,
        "reporting_manager": {"id": manager.id, "name": manager.name, "username": manager.username} if manager else None,
    }

@router.post("/me/password")
def change_my_password(b: ChangePasswordIn, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    u = get_user_by_username(db, current_user["username"])
    if not u:
        raise HTTPException(404, "User profile not found")
    change_own_password(db, u.id, b.current_password, b.new_password)
    return {"ok": True, "message": "Password updated successfully"}

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
