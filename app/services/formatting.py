import datetime
from app.core.config import ROUTING, TEAMS, AT_RISK_MINUTES, AT_RISK_FRACTION, CRITICAL_MINUTES, CRITICAL_FRACTION

def sla_tier(mins_left, tat_mins):
    """Single source of truth for SLA state, shared by the per-ticket pill,
    the queue risk/critical filters and the SLA sweep. BREACHED < CRITICAL <
    AT RISK < ON TRACK, each a widening window around due_at."""
    tat_mins = tat_mins or 240
    if mins_left < 0:
        return "BREACHED"
    if mins_left <= max(CRITICAL_MINUTES, tat_mins * CRITICAL_FRACTION):
        return "CRITICAL"
    if mins_left <= max(AT_RISK_MINUTES, tat_mins * AT_RISK_FRACTION):
        return "AT RISK"
    return "ON TRACK"

def enrich(ticket):
    """Attach live TAT state for serialization"""
    if not ticket:
        return ticket
    
    t = {c.name: getattr(ticket, c.name) for c in ticket.__table__.columns}
    
    now = datetime.datetime.now()
    for k in ("created_at", "due_at", "assigned_at", "acknowledged_at", "resolved_at", "closed_at",
              "called_at", "confirmed_at", "escalated_at", "first_response_at"):
        if isinstance(t.get(k), datetime.datetime):
            t[k] = t[k].strftime("%Y-%m-%d %H:%M")
            
    due = t.get("due_at")
    t["tat_state"] = "-"
    t["mins_left"] = None
    if due and t.get("status") not in ("CLOSED",):
        try:
            d = datetime.datetime.strptime(due, "%Y-%m-%d %H:%M")
            left = (d - now).total_seconds() / 60.0
            t["mins_left"] = round(left)
            t["tat_state"] = sla_tier(left, t.get("tat_mins"))
        except Exception:
            pass
    elif t.get("status") == "CLOSED":
        t["tat_state"] = "BREACHED" if t.get("breached") else "MET"
        
    t["category_label"] = ROUTING.get(t.get("category") or "", {}).get("label", t.get("category"))
    t["team_label"] = TEAMS.get(t.get("team") or "", t.get("team"))
    return t
