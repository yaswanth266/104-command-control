from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.team import Team
from app.models.category import Category

def get_teams(db: Session, include_inactive: bool = False):
    q = db.query(Team)
    if not include_inactive:
        q = q.filter(Team.is_active == True)
    return q.order_by(Team.code).all()

def get_team(db: Session, code: str):
    return db.query(Team).filter(Team.code == code).first()

def get_team_map(db: Session):
    """{code: name} for ALL teams (active + inactive) - for label lookups on
    tickets that may reference a since-deactivated team. Use
    get_active_team_map() for "what can a ticket route/reassign to" instead."""
    return {t.code: t.name for t in db.query(Team).all()}

def get_active_team_map(db: Session):
    return {t.code: t.name for t in get_teams(db, include_inactive=False)}

def create_team(db: Session, code: str, name: str) -> Team:
    code = (code or "").strip().upper()
    if not code or not name.strip():
        raise HTTPException(400, "Team code and name are required")
    if db.query(Team).filter(Team.code == code).first():
        raise HTTPException(409, f"Team code '{code}' already exists")
    t = Team(code=code, name=name.strip(), is_active=True)
    db.add(t)
    db.commit()
    db.refresh(t)
    return t

def update_team(db: Session, code: str, name: str = None, is_active: bool = None) -> Team:
    t = get_team(db, code)
    if not t:
        raise HTTPException(404, "Team not found")
    if is_active is False and code == "CC_MANAGER":
        raise HTTPException(409, "CC_MANAGER can't be deactivated - it's the fallback route for "
                                  "unclassified issues (the OTHER category) and the admin role")
    if is_active is False and t.is_active:
        # Deactivating only stops NEW routing to this team; existing users/tickets
        # for it are untouched and department staff can keep working them. Only
        # block when an active category would be left pointing at a dead team.
        active_categories = db.query(Category).filter(Category.team_code == code, Category.is_active == True).count()
        if active_categories:
            raise HTTPException(409, f"{active_categories} active categor{'y' if active_categories==1 else 'ies'} still "
                                      f"route to '{code}' - reassign or deactivate them first")
    if name is not None:
        if not name.strip():
            raise HTTPException(400, "Team name cannot be blank")
        t.name = name.strip()
    if is_active is not None:
        t.is_active = is_active
    db.commit()
    db.refresh(t)
    return t
