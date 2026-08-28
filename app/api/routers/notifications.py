from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.api.deps import get_current_user
from app.crud.crud_notification import get_notifications, mark_read

router = APIRouter(prefix="/notifications", tags=["notifications"])

@router.get("")
def list_notifications(unread_only: bool = False, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    rows = get_notifications(db, current_user["role"], username=current_user["username"], unread_only=unread_only)
    return {"count": len(rows), "rows": [
        {"id": n.id, "ticket_id": n.ticket_id, "type": n.type, "message": n.message,
         "created_at": n.created_at.strftime("%Y-%m-%d %H:%M") if n.created_at else None,
         "read_at": n.read_at.strftime("%Y-%m-%d %H:%M") if n.read_at else None}
        for n in rows
    ]}

@router.post("/{nid}/read")
def read_notification(nid: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    result = mark_read(db, nid, current_user["role"], username=current_user["username"])
    if result is None:
        raise HTTPException(404, "Notification not found")
    if result is False:
        raise HTTPException(403, "This notification is not addressed to your department")
    return {"ok": True}
