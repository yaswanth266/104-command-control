import time
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.schemas.auth import LoginIn, ForgotPasswordIn
from app.crud.crud_user import get_user_by_username
from app.core.security import verify_pw, mktoken, hash_pw

router = APIRouter(prefix="/auth", tags=["auth"])

MAX_ATTEMPTS = 5
LOCKOUT_WINDOW_SECONDS = 15 * 60
_failed_attempts: dict[str, list[float]] = {}
_failed_reset_attempts: dict[str, list[float]] = {}

def _register_failure(key: str, store: dict = None):
    store = _failed_attempts if store is None else store
    now = time.time()
    hits = [t for t in store.get(key, []) if now - t < LOCKOUT_WINDOW_SECONDS]
    hits.append(now)
    store[key] = hits

def _is_locked_out(key: str, store: dict = None) -> bool:
    store = _failed_attempts if store is None else store
    now = time.time()
    hits = [t for t in store.get(key, []) if now - t < LOCKOUT_WINDOW_SECONDS]
    store[key] = hits
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
                 "is_team_manager": u.is_team_manager, "district_id": u.district_id}
    tok = mktoken(user_dict)

    return {"token": tok, "user": {"username": u.username, "name": u.name, "role": u.role,
                                    "is_team_manager": u.is_team_manager, "district_id": u.district_id}}

@router.post("/forgot-password")
def forgot_password(b: ForgotPasswordIn, db: Session = Depends(get_db)):
    """Unauthenticated self-service reset - the phone number on file is the
    only proof of identity, so it must always be checked. A user with no
    phone on file has nothing to verify against and is deliberately refused
    here rather than let through, and a wrong username gets the exact same
    error as a wrong phone so this can't be used to enumerate usernames."""
    key = b.username.strip().lower()
    if _is_locked_out(key, _failed_reset_attempts):
        raise HTTPException(status_code=429, detail="Too many attempts. Try again later.")

    u = get_user_by_username(db, key)
    input_digits = "".join(filter(str.isdigit, b.phone or ""))
    user_digits = "".join(filter(str.isdigit, u.phone or "")) if u else ""

    if not u or not user_digits or len(input_digits) < 10 or user_digits[-10:] != input_digits[-10:]:
        _register_failure(key, _failed_reset_attempts)
        raise HTTPException(status_code=400, detail="Username and registered mobile number do not match our records")

    if len((b.new_password or "").strip()) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters")

    _failed_reset_attempts.pop(key, None)
    u.pw = hash_pw(b.new_password.strip())
    db.commit()
    return {"ok": True, "message": "Password reset successfully. You may now sign in."}
