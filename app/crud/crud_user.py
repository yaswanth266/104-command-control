from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.user import User
from app.core.security import hash_pw

FIXED_ROLES = ["CALL_TAKER", "LT"]  # CC_MANAGER is a real (undeactivatable) ccc_team row - see crud_team.py

def get_user_by_username(db: Session, username: str):
    return db.query(User).filter(User.username == username, User.active == True).first()

def get_user(db: Session, user_id: int):
    return db.query(User).filter(User.id == user_id).first()

def get_users(db: Session):
    return db.query(User).order_by(User.role, User.username).all()

def get_active_users_by_role(db: Session, role: str):
    return db.query(User).filter(User.role == role, User.active == True).order_by(User.username).all()

def get_valid_roles(db: Session):
    from app.crud.crud_team import get_teams
    return FIXED_ROLES + [t.code for t in get_teams(db, include_inactive=False)]

def get_team_managers(db: Session, team_code: str):
    return db.query(User).filter(User.role == team_code, User.is_team_manager == True, User.active == True).all()

def get_local_team_lead(db: Session, team_code: str, district_id: int):
    """Same shape as get_team_managers, additionally scoped to one district -
    a Team Executive whose profile has this district set. Dormant unless the
    caller has already checked crud_settings.get_dispatch_config's
    local_team_lead_enabled flag."""
    return db.query(User).filter(User.role == team_code, User.is_team_manager == True,
                                  User.active == True, User.district_id == district_id).all()

def create_user(db: Session, username: str, name: str, role: str, password: str, phone: str = None,
                 hr_emp_code: str = None, reporting_manager_id: int = None, is_team_manager: bool = False,
                 vehicle_id: int = None, district_id: int = None, mandal_id: int = None) -> User:
    username = (username or "").strip().lower()
    if not username or not (name or "").strip():
        raise HTTPException(400, "Username and name are required")
    if role not in get_valid_roles(db):
        raise HTTPException(400, f"'{role}' is not a valid role")
    if len(password or "") < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(409, f"Username '{username}' already exists")
    if reporting_manager_id is not None and not get_user(db, reporting_manager_id):
        raise HTTPException(400, "Reporting manager not found")
    u = User(username=username, name=name.strip(), role=role, phone=phone,
              pw=hash_pw(password), active=True, hr_emp_code=(hr_emp_code or "").strip() or None,
              reporting_manager_id=reporting_manager_id, is_team_manager=bool(is_team_manager),
              vehicle_id=vehicle_id, district_id=district_id, mandal_id=mandal_id)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u

def update_user(db: Session, user_id: int, name: str = None, role: str = None, phone: str = None,
                 active: bool = None, password: str = None, hr_emp_code: str = None,
                 reporting_manager_id=None, is_team_manager: bool = None,
                 vehicle_id=None, district_id=None, mandal_id=None) -> User:
    u = get_user(db, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    if active is False and u.role == "CC_MANAGER" and u.active:
        remaining = db.query(User).filter(User.role == "CC_MANAGER", User.active == True, User.id != user_id).count()
        if remaining == 0:
            raise HTTPException(409, "Cannot deactivate the last active Global Team Executive")
    if name is not None:
        if not name.strip():
            raise HTTPException(400, "Name cannot be blank")
        u.name = name.strip()
    if role is not None:
        if role not in get_valid_roles(db):
            raise HTTPException(400, f"'{role}' is not a valid role")
        u.role = role
    if phone is not None:
        u.phone = phone
    if active is not None:
        u.active = active
    if password is not None:
        if len(password) < 8:
            raise HTTPException(400, "Password must be at least 8 characters")
        u.pw = hash_pw(password)
    if hr_emp_code is not None:
        u.hr_emp_code = hr_emp_code.strip() or None
    if reporting_manager_id is not None:
        rm_id = None if reporting_manager_id == 0 else reporting_manager_id
        if rm_id == user_id:
            raise HTTPException(400, "A user cannot report to themselves")
        if rm_id is not None and not get_user(db, rm_id):
            raise HTTPException(400, "Reporting manager not found")
        u.reporting_manager_id = rm_id
    if is_team_manager is not None:
        u.is_team_manager = is_team_manager
    if vehicle_id is not None:
        u.vehicle_id = None if vehicle_id == 0 else vehicle_id
    if district_id is not None:
        u.district_id = None if district_id == 0 else district_id
    if mandal_id is not None:
        u.mandal_id = None if mandal_id == 0 else mandal_id
    db.commit()
    db.refresh(u)
    return u
