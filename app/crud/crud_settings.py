import json
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.config import Config
from app.core.config import TAT_DEFAULT

SLA_DEFAULT = {
    "at_risk_minutes": 60, "at_risk_fraction": 0.2,
    "critical_minutes": 15, "critical_fraction": 0.05,
    "resolved_followup_hours": 4,
    "reopen_window_hours": 24,
    # Tiered notification AUDIENCE (separate from the at_risk/critical pair
    # above, which still drive the visual ON TRACK/AT RISK/CRITICAL/BREACHED
    # pill unchanged). Percent of TAT consumed at which each tier notifies -
    # the assignee individually first, then that team's Team Manager(s),
    # before BREACHED (100%) reaches CC_MANAGER - so the CC Manager isn't
    # copied on every single warning across every district (alarm fatigue).
    "assignee_warn_pct": 0.5,
    "team_manager_warn_pct": 0.8,
    # LT self-service: if an LT-raised ticket sits with its CDA team without
    # being resolved this long, auto-escalate to CC_MANAGER (see
    # app/services/sla_sweep.py's _sweep_lt_cda_timeouts).
    "lt_cda_escalation_minutes": 60,
    # If a ticket sits in PENDING this long (continuously, since it was last
    # marked pending), auto-escalate to CC_MANAGER so a stalled wait-on-someone-
    # else doesn't go unnoticed just because the TAT clock itself is paused
    # for that stretch (see app/services/sla_sweep.py's _sweep_stuck_pending).
    "pending_escalation_hours": 24,
}

VIP_KEYWORDS_DEFAULT = ["ceo", "collector", "director", "minister", "total shutdown"]

# Local Team Lead routing (see app/crud/crud_user.py's get_local_team_lead) -
# dormant until the Global Team Executive turns it on: a Team Executive
# (is_team_manager=True) with a district_id set becomes that district's Local
# Team Lead once this is enabled. Off by default so nothing changes until
# explicitly switched on.
DISPATCH_DEFAULT = {"local_team_lead_enabled": False}

def _get_config_row(db: Session, key: str):
    return db.query(Config).filter(Config.k == key).first()

def _set_config_row(db: Session, key: str, value: dict):
    row = _get_config_row(db, key)
    if row:
        row.v = json.dumps(value)
    else:
        db.add(Config(k=key, v=json.dumps(value)))
    db.commit()

def get_sla_config(db: Session) -> dict:
    row = _get_config_row(db, "sla")
    if row:
        try:
            cfg = dict(SLA_DEFAULT)
            cfg.update(json.loads(row.v))
            return cfg
        except Exception:
            return dict(SLA_DEFAULT)
    return dict(SLA_DEFAULT)

def update_sla_config(db: Session, patch: dict) -> dict:
    cfg = get_sla_config(db)
    minute_fields = ("at_risk_minutes", "critical_minutes", "resolved_followup_hours", "reopen_window_hours",
                     "lt_cda_escalation_minutes", "pending_escalation_hours")
    fraction_fields = ("at_risk_fraction", "critical_fraction", "assignee_warn_pct", "team_manager_warn_pct")
    for k, v in patch.items():
        if k not in cfg:
            continue
        try:
            v = float(v)
        except (TypeError, ValueError):
            raise HTTPException(400, f"'{k}' must be a number")
        if k in minute_fields and v <= 0:
            raise HTTPException(400, f"'{k}' must be a positive number of minutes/hours")
        if k in fraction_fields and not (0 <= v <= 1):
            raise HTTPException(400, f"'{k}' must be between 0 and 1")
        cfg[k] = v
    if cfg["assignee_warn_pct"] >= cfg["team_manager_warn_pct"]:
        raise HTTPException(400, "'assignee_warn_pct' must be less than 'team_manager_warn_pct'")
    _set_config_row(db, "sla", cfg)
    return cfg

def get_vip_keywords(db: Session):
    row = _get_config_row(db, "vip_keywords")
    if row:
        try:
            return json.loads(row.v)
        except Exception:
            return list(VIP_KEYWORDS_DEFAULT)
    return list(VIP_KEYWORDS_DEFAULT)

def update_vip_keywords(db: Session, keywords: list) -> list:
    cleaned = [str(k).strip().lower() for k in keywords if str(k).strip()]
    row = _get_config_row(db, "vip_keywords")
    if row:
        row.v = json.dumps(cleaned)
    else:
        db.add(Config(k="vip_keywords", v=json.dumps(cleaned)))
    db.commit()
    return cleaned

def detect_vip(db: Session, vip_flag: bool, *text_fields) -> tuple:
    """Returns (is_vip, reason). VIP if the caller flagged it, or if any
    configured keyword appears in the given text fields (problem/impact)."""
    if vip_flag:
        return True, "flagged by call taker"
    haystack = " ".join(f for f in text_fields if f).lower()
    for kw in get_vip_keywords(db):
        if kw and kw in haystack:
            return True, f"matched keyword '{kw}'"
    return False, None

def get_dispatch_config(db: Session) -> dict:
    row = _get_config_row(db, "dispatch")
    if row:
        try:
            cfg = dict(DISPATCH_DEFAULT)
            cfg.update(json.loads(row.v))
            return cfg
        except Exception:
            return dict(DISPATCH_DEFAULT)
    return dict(DISPATCH_DEFAULT)

def update_dispatch_config(db: Session, patch: dict) -> dict:
    cfg = get_dispatch_config(db)
    for k, v in patch.items():
        if k not in cfg:
            continue
        cfg[k] = bool(v)
    _set_config_row(db, "dispatch", cfg)
    return cfg

def update_tat_map(db: Session, patch: dict) -> dict:
    """Was previously read-only (get_tat_map in crud_ticket.py) with no way to
    write it from anywhere - this closes that gap."""
    from app.crud.crud_ticket import get_tat_map
    from app.crud.crud_priority import get_priorities
    valid_codes = {p.code for p in get_priorities(db, include_inactive=True)}
    tat = get_tat_map(db)
    for k, v in patch.items():
        if k not in valid_codes:
            raise HTTPException(400, f"Unknown priority '{k}' (must be one of {sorted(valid_codes)})")
        try:
            v = int(v)
        except (TypeError, ValueError):
            raise HTTPException(400, f"TAT for '{k}' must be a whole number of minutes")
        if v <= 0:
            raise HTTPException(400, f"TAT for '{k}' must be a positive number of minutes")
        tat[k] = v
    _set_config_row(db, "tat", tat)
    return tat
