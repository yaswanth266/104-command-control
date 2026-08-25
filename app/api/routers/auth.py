from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.schemas.auth import LoginIn
from app.crud.crud_user import get_user_by_username
from app.core.security import verify_pw, mktoken

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("")
def auth(b: LoginIn, db: Session = Depends(get_db)):
    u = get_user_by_username(db, b.username.strip().lower())
    if not u or not verify_pw(b.password, u.pw):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    user_dict = {"uid": u.id, "username": u.username, "name": u.name, "role": u.role}
    tok = mktoken(user_dict)
    
    return {"token": tok, "user": {"username": u.username, "name": u.name, "role": u.role}}
