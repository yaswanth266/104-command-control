from typing import Optional
from fastapi import Header, HTTPException, Depends
from sqlalchemy.orm import Session
from app.core.security import parse_token
from app.db.database import get_db

def get_current_user(authorization: Optional[str] = Header(None)):
    t = (authorization or "")
    t = t[7:] if t.startswith("Bearer ") else t
    u = parse_token(t)
    if not u:
        raise HTTPException(status_code=401, detail="Login required")
    return u

def is_admin(user: dict) -> bool:
    """Single source of truth for 'has full CC Manager / admin access'. Used by
    every CC-Manager-only endpoint so a future extra admin tier can't drift
    out of sync across call sites."""
    return user.get("role") == "CC_MANAGER"

def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if not is_admin(current_user):
        raise HTTPException(status_code=403, detail="This action is restricted to the Global Team Executive")
    return current_user
