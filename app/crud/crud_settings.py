import json
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.config import Config
from app.core.config import TAT_DEFAULT, PRIORITY

SLA_DEFAULT = {
    "at_risk_minutes": 60, "at_risk_fraction": 0.2,
    "critical_minutes": 15, "critical_fraction": 0.05,
    "resolved_followup_hours": 4,
}

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
    minute_fields = ("at_risk_minutes", "critical_minutes", "resolved_followup_hours")
    fraction_fields = ("at_risk_fraction", "critical_fraction")
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
    _set_config_row(db, "sla", cfg)
    return cfg

def update_tat_map(db: Session, patch: dict) -> dict:
    """Was previously read-only (get_tat_map in crud_ticket.py) with no way to
    write it from anywhere - this closes that gap."""
    from app.crud.crud_ticket import get_tat_map
    tat = get_tat_map(db)
    for k, v in patch.items():
        if k not in PRIORITY:
            raise HTTPException(400, f"Unknown priority '{k}' (must be one of {list(PRIORITY)})")
        try:
            v = int(v)
        except (TypeError, ValueError):
            raise HTTPException(400, f"TAT for '{k}' must be a whole number of minutes")
        if v <= 0:
            raise HTTPException(400, f"TAT for '{k}' must be a positive number of minutes")
        tat[k] = v
    _set_config_row(db, "tat", tat)
    return tat
