import datetime
from app.core.config import ROUTING, TEAMS

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
            t["tat_state"] = "BREACHED" if left < 0 else ("AT RISK" if left <= max(30, (t.get("tat_mins") or 240) * 0.2) else "ON TRACK")
        except Exception:
            pass
    elif t.get("status") == "CLOSED":
        t["tat_state"] = "BREACHED" if t.get("breached") else "MET"
        
    t["category_label"] = ROUTING.get(t.get("category") or "", {}).get("label", t.get("category"))
    t["team_label"] = TEAMS.get(t.get("team") or "", t.get("team"))
    return t
