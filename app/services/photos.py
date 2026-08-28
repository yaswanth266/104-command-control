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
