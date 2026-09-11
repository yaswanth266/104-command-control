import datetime
from sqlalchemy import text

def get_chronic_breakdowns_map(db):
    """{mmu_vehicle: count} for vehicles with >= 3 breakdowns in the past 30
    days - backs the chronic-equipment watchdog badge on tickets/queue and
    the dashboard's watchdog table (see app/services/reporting.py)."""
    try:
        res = db.execute(text("""
            SELECT mmu_vehicle, COUNT(*) AS c
            FROM ccc_ticket
            WHERE mmu_vehicle IS NOT NULL AND mmu_vehicle <> ''
              AND created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
            GROUP BY mmu_vehicle
            HAVING c >= 3
        """)).fetchall()
        return {str(row[0]): int(row[1]) for row in res}
    except Exception:
        return {}

def sla_tier(mins_left, tat_mins, sla_cfg):
    """Single source of truth for SLA state, shared by the per-ticket pill,
    the queue risk/critical filters and the SLA sweep. BREACHED < CRITICAL <
    AT RISK < ON TRACK, each a widening window around due_at. `sla_cfg` is the
    dict shape from crud_settings.get_sla_config (admin-editable, DB-backed)."""
    tat_mins = tat_mins or 240
    if mins_left < 0:
        return "BREACHED"
    if mins_left <= max(sla_cfg["critical_minutes"], tat_mins * sla_cfg["critical_fraction"]):
        return "CRITICAL"
    if mins_left <= max(sla_cfg["at_risk_minutes"], tat_mins * sla_cfg["at_risk_fraction"]):
        return "AT RISK"
    return "ON TRACK"

def enrich(ticket, category_map, team_map, sla_cfg, chronic_map=None):
    """Attach live TAT state + display labels for serialization.
    category_map: crud_category.get_routing_map(db) shape ({code: {label,team,owner}}).
    team_map: {team_code: team_name}.
    sla_cfg: crud_settings.get_sla_config(db) shape.
    chronic_map: optional get_chronic_breakdowns_map(db) shape - omitted by
    callers that don't need the chronic-fault badge (exports, LT's own list)."""
    if not ticket:
        return ticket

    t = {c.name: getattr(ticket, c.name) for c in ticket.__table__.columns}

    now = datetime.datetime.now()
    for k in ("created_at", "due_at", "assigned_at", "acknowledged_at", "resolved_at", "closed_at",
              "called_at", "confirmed_at", "escalated_at", "first_response_at", "response_due_at"):
        if isinstance(t.get(k), datetime.datetime):
            t[k] = t[k].strftime("%Y-%m-%d %H:%M")

    due = t.get("due_at")
    t["tat_state"] = "-"
    t["mins_left"] = None
    # sla_status (phase 3): the spec's WITHIN/APPROACHING/BREACHED/
    # RESOLVED_WITHIN/RESOLVED_AFTER, derived from the same tat_state this
    # pill has always used - additive, not a replacement for tat_state/
    # sla_tier(), which remain the single source of truth for the pill.
    _SLA_STATUS_MAP = {"BREACHED": "BREACHED", "CRITICAL": "APPROACHING", "AT RISK": "APPROACHING", "ON TRACK": "WITHIN"}
    if due and t.get("status") not in ("CLOSED",):
        try:
            d = datetime.datetime.strptime(due, "%Y-%m-%d %H:%M")
            left = (d - now).total_seconds() / 60.0
            t["mins_left"] = round(left)
            t["tat_state"] = sla_tier(left, t.get("tat_mins"), sla_cfg)
            t["sla_status"] = _SLA_STATUS_MAP.get(t["tat_state"], "WITHIN")
        except Exception:
            t["sla_status"] = None
    elif t.get("status") == "CLOSED":
        t["tat_state"] = "BREACHED" if t.get("breached") else "MET"
        t["sla_status"] = "RESOLVED_AFTER" if t.get("breached") else "RESOLVED_WITHIN"
    else:
        t["sla_status"] = None

    veh = str(t.get("mmu_vehicle") or "")
    t["is_chronic_fault"] = bool(chronic_map and veh and veh in chronic_map)
    t["chronic_breakdown_count"] = chronic_map.get(veh, 0) if (chronic_map and veh) else 0

    t["category_label"] = category_map.get(t.get("category") or "", {}).get("label", t.get("category"))
    t["team_label"] = team_map.get(t.get("team") or "", t.get("team"))
    return t
