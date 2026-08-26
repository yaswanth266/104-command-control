from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.api.deps import require_admin
from app.crud.crud_user import get_users

router = APIRouter(prefix="/users", tags=["users"])

@router.get("")
def list_users(db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    users = get_users(db)
    return [
        {"id": u.id, "username": u.username, "name": u.name, "role": u.role, "phone": u.phone, "active": u.active}
        for u in users
    ]
