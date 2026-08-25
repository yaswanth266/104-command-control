from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.api.deps import get_current_user
from app.crud.crud_user import get_users

router = APIRouter(prefix="/users", tags=["users"])

@router.get("")
def list_users(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "CC_MANAGER":
        raise HTTPException(403, "CC Manager only")
        
    users = get_users(db)
    return [
        {"id": u.id, "username": u.username, "name": u.name, "role": u.role, "phone": u.phone, "active": u.active} 
        for u in users
    ]
