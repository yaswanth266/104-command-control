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
    # L1-L4 auto-escalation (phase 5): percent of the ticket's Resolution SLA
    # consumed (business-calendar-correct - see sla_sweep.py's _pct_used())
    # at which each level's occupant is notified and current_level advances,
    # ascending L1->L4; 100% is the fixed BREACHED/CC_MANAGER escalation
    # below and isn't configurable here. Replaces the old two-tier
    # assignee_warn_pct/team_manager_warn_pct scheme (see
    # app/services/sla_sweep.py's _sweep_open_tickets()).
    "escalation_pcts": {"L1": 0.3, "L2": 0.5, "L3": 0.7, "L4": 0.9},
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

_ESCALATION_LEVELS = ("L1", "L2", "L3", "L4")

def _parse_escalation_pcts(pcts) -> dict:
    if not isinstance(pcts, dict) or set(pcts) != set(_ESCALATION_LEVELS):
        raise HTTPException(400, f"'escalation_pcts' must have exactly {list(_ESCALATION_LEVELS)}")
    try:
        parsed = {k: float(pcts[k]) for k in _ESCALATION_LEVELS}
    except (TypeError, ValueError):
        raise HTTPException(400, "'escalation_pcts' values must be numbers")
    if not all(0 < parsed[k] < 1 for k in _ESCALATION_LEVELS):
        raise HTTPException(400, "'escalation_pcts' values must be between 0 and 1")
    if not (parsed["L1"] < parsed["L2"] < parsed["L3"] < parsed["L4"]):
        raise HTTPException(400, "'escalation_pcts' must be strictly ascending L1 < L2 < L3 < L4")
    return parsed

def update_sla_config(db: Session, patch: dict) -> dict:
    cfg = get_sla_config(db)
    minute_fields = ("at_risk_minutes", "critical_minutes", "resolved_followup_hours", "reopen_window_hours",
                     "lt_cda_escalation_minutes", "pending_escalation_hours")
    fraction_fields = ("at_risk_fraction", "critical_fraction")
    if "escalation_pcts" in patch:
        cfg["escalation_pcts"] = _parse_escalation_pcts(patch["escalation_pcts"])
    for k, v in patch.items():
        if k == "escalation_pcts" or k not in cfg:
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
    """Writes the baseline ccc_sla_policy rows (see app/crud/crud_sla_policy.py)
    - the old ccc_config['tat'] JSON key this used to write is retired as of
    phase 3, kept only as inert leftover data on any deployment that had it."""
    from app.crud.crud_priority import get_priorities
    from app.crud.crud_sla_policy import upsert_baseline_resolution_mins, get_baseline_tat_map
    valid_codes = {p.code for p in get_priorities(db, include_inactive=True)}
    for k, v in patch.items():
        if k not in valid_codes:
            raise HTTPException(400, f"Unknown priority '{k}' (must be one of {sorted(valid_codes)})")
        try:
            v = int(v)
        except (TypeError, ValueError):
            raise HTTPException(400, f"TAT for '{k}' must be a whole number of minutes")
        if v <= 0:
            raise HTTPException(400, f"TAT for '{k}' must be a positive number of minutes")
        upsert_baseline_resolution_mins(db, k, v)
    return get_baseline_tat_map(db)
