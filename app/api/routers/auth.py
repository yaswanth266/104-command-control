import time
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.schemas.auth import LoginIn
from app.crud.crud_user import get_user_by_username
from app.core.security import verify_pw, mktoken

router = APIRouter(prefix="/auth", tags=["auth"])

MAX_ATTEMPTS = 5
LOCKOUT_WINDOW_SECONDS = 15 * 60
_failed_attempts: dict[str, list[float]] = {}

def _register_failure(key: str):
    now = time.time()
    hits = [t for t in _failed_attempts.get(key, []) if now - t < LOCKOUT_WINDOW_SECONDS]
    hits.append(now)
    _failed_attempts[key] = hits

def _is_locked_out(key: str) -> bool:
    now = time.time()
    hits = [t for t in _failed_attempts.get(key, []) if now - t < LOCKOUT_WINDOW_SECONDS]
    _failed_attempts[key] = hits
    return len(hits) >= MAX_ATTEMPTS

@router.post("")
def auth(b: LoginIn, db: Session = Depends(get_db)):
    key = b.username.strip().lower()
    if _is_locked_out(key):
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again later.")

    u = get_user_by_username(db, key)
    if not u or not verify_pw(b.password, u.pw):
        _register_failure(key)
        raise HTTPException(status_code=401, detail="Invalid username or password")

    _failed_attempts.pop(key, None)
    user_dict = {"uid": u.id, "username": u.username, "name": u.name, "role": u.role,
                 "is_team_manager": u.is_team_manager}
    tok = mktoken(user_dict)

    return {"token": tok, "user": {"username": u.username, "name": u.name, "role": u.role,
                                    "is_team_manager": u.is_team_manager}}
