import time
import datetime
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.api.deps import require_admin

router = APIRouter(prefix="/health", tags=["health"])

@router.get("/detailed")
def detailed_health(db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    """Deeper readiness check, separate from the bare /health liveness probe
    nginx/systemd use. CC-Manager-only, same restriction as Daily Monitoring.
    There is no LIS/CDA integration in this codebase to monitor, so that's
    intentionally not reported here rather than faked."""
    db_ok, db_latency_ms, db_error = False, None, None
    try:
        t0 = time.monotonic()
        db.execute(text("SELECT 1"))
        db_latency_ms = round((time.monotonic() - t0) * 1000, 1)
        db_ok = True
    except Exception as e:
        db_error = str(e)

    last_ticket_age_mins = None
    if db_ok:
        row = db.execute(text("SELECT MAX(created_at) m FROM ccc_ticket")).fetchone()
        last_created = row[0] if row else None
        if last_created:
            last_ticket_age_mins = round((datetime.datetime.now() - last_created).total_seconds() / 60.0, 1)

    return {
        "ok": db_ok,
        "database": {"ok": db_ok, "latency_ms": db_latency_ms, "error": db_error},
        "last_ticket_age_mins": last_ticket_age_mins,
        "time": datetime.datetime.now().isoformat(),
    }
