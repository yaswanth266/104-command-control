"""Routing engine / L1-L4 hierarchy resolution (spec S15-S21).

Two providers, both normalizing to the same shape - a list of
{level, user, team_code, team_name} entries for L1..L4:

- LocalMappingProvider (default, mode='LOCAL'): app/crud/crud_routing_rule.py
  for an explicit category(+zone) override, falling back to today's
  resolve_team() for L1's team, that team's manager for L2, L2's
  reporting_manager_id for L3, and CC_MANAGER as the terminal L4.
- ExternalApiProvider (mode='EXTERNAL_API'): POSTs the ticket's
  classification to a configured URL and normalizes whatever comes back -
  tolerant of either a full per-level mapping or a flat list of users.

BR-013: the ticket is always persisted (via the existing team-routing insert)
BEFORE this runs - resolve_and_apply() is called as a second, independent
step and never allowed to raise, so a hierarchy problem can never fail ticket
creation. EXTERNAL_API failures fall back to LOCAL rather than leaving the
ticket with no chain at all, and are both logged (ccc_api_assignment_log) and
queued for review (ccc_assignment_exception).
"""
import datetime
import json
import logging
import time

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.config import Config
from app.crud.crud_routing_rule import match_rule
from app.crud.crud_team import get_team_map
from app.crud.crud_user import get_user_by_username, get_user, get_team_managers, get_local_team_lead
from app.crud.crud_settings import get_dispatch_config
from app.crud.crud_assignment import add_occupant, release_level
from app.crud.crud_assignment_log import log_attempt
from app.crud.crud_assignment_exception import create_exception

logger = logging.getLogger("ccc.hierarchy")

_CONFIG_KEY = "hierarchy"
_DEFAULT_CONFIG = {
    "mode": "LOCAL",         # or "EXTERNAL_API"
    "url": None,
    "auth_header": None,     # e.g. "Authorization" - sent with auth_token as its value
    "auth_token": None,
    "timeout_seconds": 5.0,
}
_VALID_MODES = ("LOCAL", "EXTERNAL_API")


# ---------- configuration (DB-backed, ccc_config key 'hierarchy') ----------

def get_hierarchy_config(db: Session) -> dict:
    cfg = dict(_DEFAULT_CONFIG)
    row = db.query(Config).filter(Config.k == _CONFIG_KEY).first()
    if row:
        try:
            cfg.update(json.loads(row.v))
        except Exception:
            logger.exception("Corrupt hierarchy config in ccc_config - falling back to defaults")
    return cfg


def update_hierarchy_config(db: Session, patch: dict) -> dict:
    cfg = get_hierarchy_config(db)
    if "mode" in patch:
        mode = (patch["mode"] or "").strip().upper()
        if mode not in _VALID_MODES:
            raise HTTPException(400, f"'mode' must be one of {list(_VALID_MODES)}")
        cfg["mode"] = mode
    if "url" in patch:
        url = (patch["url"] or "").strip() or None
        if url and not (url.startswith("http://") or url.startswith("https://")):
            raise HTTPException(400, "Hierarchy API URL must start with http:// or https://")
        cfg["url"] = url
    if "auth_header" in patch:
        cfg["auth_header"] = (patch["auth_header"] or "").strip() or None
    if "auth_token" in patch:
        cfg["auth_token"] = (patch["auth_token"] or "").strip() or None
    if "timeout_seconds" in patch:
        try:
            t = float(patch["timeout_seconds"])
        except (TypeError, ValueError):
            raise HTTPException(400, "'timeout_seconds' must be a number")
        if not (0 < t <= 30):
            raise HTTPException(400, "'timeout_seconds' must be between 0 and 30")
        cfg["timeout_seconds"] = t
    if cfg["mode"] == "EXTERNAL_API" and not cfg.get("url"):
        raise HTTPException(400, "Cannot switch to EXTERNAL_API mode without a URL")

    row = db.query(Config).filter(Config.k == _CONFIG_KEY).first()
    if row:
        row.v = json.dumps(cfg)
    else:
        db.add(Config(k=_CONFIG_KEY, v=json.dumps(cfg)))
    db.commit()
    return cfg


# ---------- LocalMappingProvider ----------

def _resolve_local(db: Session, ticket) -> list:
    rule = match_rule(db, ticket.category, ticket.zone_id)
    team_map = get_team_map(db)

    l1_team_code = (rule.l1_team_code if rule and rule.l1_team_code else ticket.team)
    l1_team_name = team_map.get(l1_team_code, l1_team_code)
    l1_user = get_user_by_username(db, rule.l1_username) if rule and rule.l1_username else None
    chain = [{"level": "L1", "user": l1_user, "team_code": l1_team_code, "team_name": l1_team_name}]

    l2_user = get_user_by_username(db, rule.l2_username) if rule and rule.l2_username else None
    if not l2_user:
        # Same "who gets paged at 80% TAT" pool sla_sweep.py already uses -
        # a Local Team Lead if that (dormant) toggle is on and the ticket has
        # a district, otherwise the team's statewide manager(s).
        managers = []
        if ticket.district_id and get_dispatch_config(db)["local_team_lead_enabled"]:
            managers = get_local_team_lead(db, l1_team_code, ticket.district_id)
        if not managers:
            managers = get_team_managers(db, l1_team_code)
        l2_user = managers[0] if managers else None
    chain.append({"level": "L2", "user": l2_user, "team_code": l1_team_code, "team_name": l1_team_name})

    l3_user = get_user_by_username(db, rule.l3_username) if rule and rule.l3_username else None
    if not l3_user and l2_user and l2_user.reporting_manager_id:
        l3_user = get_user(db, l2_user.reporting_manager_id)
    chain.append({"level": "L3", "user": l3_user, "team_code": l1_team_code, "team_name": l1_team_name})

    l4_user = get_user_by_username(db, rule.l4_username) if rule and rule.l4_username else None
    chain.append({"level": "L4", "user": l4_user, "team_code": "CC_MANAGER", "team_name": team_map.get("CC_MANAGER", "CC_MANAGER")})

    return chain


# ---------- ExternalApiProvider ----------

def _normalize_external_response(db: Session, data) -> list:
    """Tolerant of either shape from the spec's S47 conceptual contract:
    {"hierarchy": [{"level","userId"/"userName","teamId","teamName"}, ...]}
    or, when the external system can only return a flat pool of people with
    no level assigned: {"users": [{"userId"/"userName"}, ...]} - assigned to
    L1..L4 in list order."""
    entries = data.get("hierarchy") if isinstance(data, dict) else None
    chain = []
    if entries:
        for e in entries:
            level = str(e.get("level") or "").strip().upper()
            if level not in ("L1", "L2", "L3", "L4"):
                continue
            user = None
            uid = e.get("userId") or e.get("user_id")
            uname = e.get("username") or e.get("userName")
            if uid is not None:
                try:
                    user = get_user(db, int(uid))
                except (TypeError, ValueError):
                    user = None
            if not user and uname:
                user = get_user_by_username(db, uname)
            chain.append({"level": level, "user": user,
                          "team_code": e.get("teamId") or e.get("team_id"),
                          "team_name": e.get("teamName") or e.get("team_name")})
    else:
        users = (data.get("users") if isinstance(data, dict) else None) or []
        for level, e in zip(("L1", "L2", "L3", "L4"), users):
            uname = e.get("username") or e.get("userName")
            user = get_user_by_username(db, uname) if uname else None
            chain.append({"level": level, "user": user, "team_code": None, "team_name": None})
    return chain


def _resolve_external_api(db: Session, ticket, cfg: dict):
    request_payload = {
        "ticket_id": ticket.id, "ticket_no": ticket.ticket_no,
        "ticket_type": ticket.ticket_type, "category": ticket.category, "subcategory": ticket.subcategory_code,
        "location": {"district_id": ticket.district_id, "mandal_id": ticket.mandal_id, "zone_id": ticket.zone_id},
    }
    headers = {"Content-Type": "application/json"}
    if cfg.get("auth_header") and cfg.get("auth_token"):
        headers[cfg["auth_header"]] = cfg["auth_token"]
    with httpx.Client(timeout=cfg.get("timeout_seconds", 5.0)) as client:
        resp = client.post(cfg["url"], json=request_payload, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    chain = _normalize_external_response(db, data)
    return chain, request_payload, data


# ---------- orchestration ----------

def resolve_hierarchy(db: Session, ticket):
    """(chain, mode_used). Never raises - an EXTERNAL_API failure falls back
    to LOCAL so the ticket always gets a usable chain."""
    cfg = get_hierarchy_config(db)
    if cfg["mode"] == "EXTERNAL_API" and cfg.get("url"):
        request_payload = None
        try:
            chain, request_payload, response_payload = _resolve_external_api(db, ticket, cfg)
            if not chain:
                raise ValueError("External hierarchy API returned no recognizable L1-L4 entries")
            log_attempt(db, ticket.id, "EXTERNAL_API", request_payload, response_payload, "SUCCESS")
            return chain, "EXTERNAL_API"
        except Exception as exc:
            log_attempt(db, ticket.id, "EXTERNAL_API", request_payload, None, "ERROR", str(exc))
            create_exception(db, ticket.id, "API_FAILURE", str(exc))
            logger.warning("Hierarchy API failed for ticket %s, falling back to local mapping: %s", ticket.id, exc)

    chain = _resolve_local(db, ticket)
    log_attempt(db, ticket.id, "LOCAL", {"category": ticket.category, "zone_id": ticket.zone_id}, None, "SUCCESS")
    return chain, "LOCAL"


def apply_hierarchy_to_ticket(db: Session, ticket, chain: list, source: str):
    now = datetime.datetime.now()
    for entry in chain:
        add_occupant(db, ticket.id, entry["level"], user=entry.get("user"),
                     team_code=entry.get("team_code"), team_name=entry.get("team_name"),
                     source=source, now=now)
    ticket.current_level = "L1"
    l1 = next((e for e in chain if e["level"] == "L1"), None)
    ticket.current_assignee_username = l1["user"].username if (l1 and l1.get("user")) else None
    db.commit()


def resolve_and_apply(db: Session, ticket):
    """Entry point for ticket-creation call sites - swallows everything so a
    hierarchy bug can never fail ticket creation (BR-013; the ticket already
    exists by the time this is called)."""
    try:
        chain, mode = resolve_hierarchy(db, ticket)
        apply_hierarchy_to_ticket(db, ticket, chain, mode)
    except Exception:
        logger.exception("Hierarchy resolution failed outright for ticket %s", ticket.id)
        try:
            create_exception(db, ticket.id, "RESOLUTION_FAILURE", "Unhandled error resolving the L1-L4 hierarchy")
        except Exception:
            logger.exception("Failed to even record the assignment exception for ticket %s", ticket.id)


def record_manual_assignment(db: Session, ticket, level: str, user):
    """Called from ticket_service.py's existing 'assign' action - records the
    named engineer a Team Executive pointed the ticket at as that level's new
    occupant, releasing whoever (if anyone) held it before."""
    now = datetime.datetime.now()
    release_level(db, ticket.id, level, now)
    add_occupant(db, ticket.id, level, user=user, team_code=ticket.team,
                 team_name=get_team_map(db).get(ticket.team, ticket.team), source="MANUAL", now=now)
    if level == (ticket.current_level or "L1"):
        ticket.current_assignee_username = user.username
    db.commit()


def send_test_ping(db: Session) -> dict:
    """Synchronous connectivity check for the admin 'Test' button - mirrors
    app/services/webhooks.py's send_test_ping."""
    cfg = get_hierarchy_config(db)
    if cfg["mode"] != "EXTERNAL_API" or not cfg.get("url"):
        raise HTTPException(400, "Set mode to EXTERNAL_API and configure a URL first")
    headers = {"Content-Type": "application/json"}
    if cfg.get("auth_header") and cfg.get("auth_token"):
        headers[cfg["auth_header"]] = cfg["auth_token"]
    started = time.monotonic()
    try:
        with httpx.Client(timeout=cfg.get("timeout_seconds", 5.0)) as client:
            resp = client.post(cfg["url"], json={"ping": True}, headers=headers)
        return {"ok": resp.status_code < 300, "status_code": resp.status_code,
                "elapsed_ms": round((time.monotonic() - started) * 1000)}
    except httpx.HTTPError as exc:
        return {"ok": False, "error": str(exc), "elapsed_ms": round((time.monotonic() - started) * 1000)}
