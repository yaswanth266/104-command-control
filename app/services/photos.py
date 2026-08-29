import os
import uuid
from fastapi import HTTPException, UploadFile
from app.core.config import UPLOAD_DIR

_ALLOWED_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
_MAX_BYTES = 5 * 1024 * 1024  # 5 MB

def save_ticket_photo(upload: UploadFile) -> str:
    """Validates and saves an LT-uploaded ticket photo. Returns the relative
    path to store on the ticket (served back via the /uploads static mount).
    Never trusts the client's filename - writes under a fresh UUID name to
    avoid path traversal / overwrite collisions."""
    ext = _ALLOWED_TYPES.get((upload.content_type or "").lower())
    if not ext:
        raise HTTPException(400, "Photo must be JPEG, PNG, or WEBP")

    data = upload.file.read()
    if len(data) > _MAX_BYTES:
        raise HTTPException(400, "Photo must be 5MB or smaller")
    if not data:
        raise HTTPException(400, "Photo file is empty")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{ext}"
    with open(os.path.join(UPLOAD_DIR, filename), "wb") as f:
        f.write(data)
    return filename

# Ticket attachments (evidence/reports at any stage) are a broader, separate
# allowance from LT portal photos above - images + PDFs + short docs, larger
# cap - but never video, to keep disk usage predictable on a modest VM.
_ATTACHMENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}
_ATTACHMENT_MAX_BYTES = 20 * 1024 * 1024  # 20 MB

def save_ticket_attachment(upload: UploadFile) -> dict:
    """Validates and saves a general ticket attachment/evidence file. Returns
    {"filename": <stored uuid name>, "size_bytes": ...} - same never-trust-the-
    client's-filename / UUID-on-disk approach as save_ticket_photo."""
    ext = _ATTACHMENT_TYPES.get((upload.content_type or "").lower())
    if not ext:
        raise HTTPException(400, "Attachment must be a JPEG/PNG/WEBP image, a PDF, or a Word document")

    data = upload.file.read()
    if len(data) > _ATTACHMENT_MAX_BYTES:
        raise HTTPException(400, "Attachment must be 20MB or smaller")
    if not data:
        raise HTTPException(400, "Attachment file is empty")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{ext}"
    with open(os.path.join(UPLOAD_DIR, filename), "wb") as f:
        f.write(data)
    return {"filename": filename, "size_bytes": len(data)}
