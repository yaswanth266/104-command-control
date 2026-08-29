from sqlalchemy.orm import Session
from app.models.attachment import Attachment

def create_attachment(db: Session, ticket_id: int, filename: str, original_name: str, content_type: str,
                       size_bytes: int, uploaded_by: str, uploaded_by_role: str, note: str = None) -> Attachment:
    a = Attachment(ticket_id=ticket_id, filename=filename, original_name=original_name, content_type=content_type,
                    size_bytes=size_bytes, uploaded_by=uploaded_by, uploaded_by_role=uploaded_by_role, note=note)
    db.add(a)
    db.commit()
    db.refresh(a)
    return a

def get_attachments_by_ticket(db: Session, ticket_id: int):
    return db.query(Attachment).filter(Attachment.ticket_id == ticket_id).order_by(Attachment.id).all()
