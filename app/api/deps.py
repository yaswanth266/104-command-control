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
