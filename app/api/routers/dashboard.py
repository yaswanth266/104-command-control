from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db.database import get_db
from app.api.deps import get_current_user
from app.core.config import AT_RISK_MINUTES, AT_RISK_FRACTION, CRITICAL_MINUTES, CRITICAL_FRACTION

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# Same GREATEST(floor, tat_mins*fraction) window as formatting.sla_tier() / crud_ticket's
# queue filters, so every screen agrees on what "at risk" and "critical" mean.
_AT_RISK_WINDOW_SQL = f"due_at<=DATE_ADD(NOW(),INTERVAL GREATEST({AT_RISK_MINUTES}, tat_mins*{AT_RISK_FRACTION}) MINUTE)"
_CRITICAL_WINDOW_SQL = f"due_at<=DATE_ADD(NOW(),INTERVAL GREATEST({CRITICAL_MINUTES}, tat_mins*{CRITICAL_FRACTION}) MINUTE)"

@router.get("")
def dashboard(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """SOP section 10 - daily CC Manager monitoring + section 15 KPIs."""
    if current_user["role"] != "CC_MANAGER":
        raise HTTPException(403, "Daily Monitoring is restricted to the CC Manager")

    def q(sql, one=False):
        result = db.execute(text(sql))
        if one:
            row = result.fetchone()
            return dict(row._mapping) if row else None
        return [dict(r._mapping) for r in result.fetchall()]
        
    def o(sql):
        res = q(sql, one=True)
        return res.get("n", 0) if res else 0

    today = "DATE(created_at)=CURDATE()"
    d = {
        "today": {
            "tickets": o("SELECT COUNT(*) n FROM ccc_ticket WHERE " + today),
            "closed": o("SELECT COUNT(*) n FROM ccc_ticket WHERE DATE(closed_at)=CURDATE()"),
            "open": o("SELECT COUNT(*) n FROM ccc_ticket WHERE status<>'CLOSED'"),
            "escalated": o("SELECT COUNT(*) n FROM ccc_ticket WHERE escalated=1 AND status<>'CLOSED'"),
            "breached": o("SELECT COUNT(*) n FROM ccc_ticket WHERE status<>'CLOSED' AND due_at<NOW()"),
            "critical": o(f"SELECT COUNT(*) n FROM ccc_ticket WHERE status<>'CLOSED' AND due_at>=NOW() AND {_CRITICAL_WINDOW_SQL}"),
            "at_risk": o(f"SELECT COUNT(*) n FROM ccc_ticket WHERE status<>'CLOSED' AND due_at>=NOW() AND {_AT_RISK_WINDOW_SQL} AND NOT ({_CRITICAL_WINDOW_SQL})"),
            "pending": o("SELECT COUNT(*) n FROM ccc_ticket WHERE status='PENDING'"),
            "awaiting_confirmation": o("SELECT COUNT(*) n FROM ccc_ticket WHERE status='RESOLVED'"),
            "p1_open": o("SELECT COUNT(*) n FROM ccc_ticket WHERE status<>'CLOSED' AND priority='P1'"),
        },
        "by_category": q("SELECT category, COUNT(*) n, SUM(status<>'CLOSED') open_n FROM ccc_ticket GROUP BY category ORDER BY n DESC"),
        "by_team": q("SELECT team, COUNT(*) n, SUM(status<>'CLOSED') open_n, SUM(breached) breach_n FROM ccc_ticket GROUP BY team ORDER BY n DESC"),
        "by_priority": q("SELECT priority, COUNT(*) n, SUM(status<>'CLOSED') open_n FROM ccc_ticket GROUP BY priority ORDER BY priority"),
        "by_status": q("SELECT status, COUNT(*) n FROM ccc_ticket GROUP BY status"),
        "repeat_vehicles": q("SELECT mmu_vehicle, COUNT(*) n FROM ccc_ticket WHERE mmu_vehicle IS NOT NULL AND mmu_vehicle<>'' GROUP BY mmu_vehicle HAVING n>1 ORDER BY n DESC LIMIT 10"),
        "daily": q("SELECT DATE(created_at) d, COUNT(*) n, SUM(status='CLOSED') closed_n FROM ccc_ticket GROUP BY d ORDER BY d DESC LIMIT 14"),
    }
    
    tot = o("SELECT COUNT(*) n FROM ccc_ticket WHERE status='CLOSED'")
    met = o("SELECT COUNT(*) n FROM ccc_ticket WHERE status='CLOSED' AND breached=0")
    ack = q("SELECT AVG(TIMESTAMPDIFF(MINUTE,created_at,acknowledged_at)) a FROM ccc_ticket WHERE acknowledged_at IS NOT NULL", one=True)
    res = q("SELECT AVG(TIMESTAMPDIFF(MINUTE,created_at,resolved_at)) a FROM ccc_ticket WHERE resolved_at IS NOT NULL", one=True)
    
    total_tickets = max(1, o("SELECT COUNT(*) n FROM ccc_ticket"))
    
    d["kpi"] = {
        "closed_total": tot,
        "tat_compliance_pct": round(100.0 * met / tot, 1) if tot else None,
        "tat_breach_pct": round(100.0 * (tot - met) / tot, 1) if tot else None,
        "avg_ack_mins": round(float(ack["a"]), 1) if ack and ack.get("a") is not None else None,
        "avg_resolution_mins": round(float(res["a"]), 1) if res and res.get("a") is not None else None,
        "escalation_pct": round(100.0 * o("SELECT COUNT(*) n FROM ccc_ticket WHERE escalated=1") / total_tickets, 1),
    }
    
    for r in d["daily"]:
        if r.get("d"):
            r["d"] = str(r["d"])
            
    # Cast decimals to int/float for JSON serialization
    for k in ("by_category", "by_team", "by_priority", "daily"):
        for r in d[k]:
            for key, val in r.items():
                if hasattr(val, 'quantize'): # Decimal
                    r[key] = int(val) if val % 1 == 0 else float(val)
                    
    return d
