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
from app.crud import crud_master_data
from app.services.roles import resolve_role_holder

logger = logging.getLogger("ccc.hierarchy")

_CONFIG_KEY = "hierarchy"
_DEFAULT_CONFIG = {
    "mode": "LOCAL",         # or "EXTERNAL_API"
    "url": None,
    "auth_header": None,     # e.g. "Authorization" - sent with auth_token as its value
    "auth_token": None,
    "timeout_seconds": 5.0,
    # Same external system/auth as the hierarchy API above, two more GET
    # endpoints on it: vehicle geo lookup and employee search. Independent
    # of 'mode' - usable even while hierarchy resolution itself is LOCAL.
    "vehicle_lookup_url": None,
    "employee_lookup_url": None,
    # Phase 5 stage 2: three more GET endpoints, same system/auth, each
    # returning a FULL roster rather than a single-item lookup - polled
    # every CCC_MASTER_SYNC_SECONDS into the ccc_ext_vehicle/ccc_ext_employee/
    # ccc_emp_hierarchy cache tables by app/services/master_sync.py when
    # sync_enabled is on. lookup_vehicle()/search_employees() below check
    # that cache first and only call the single-item URLs above on a miss.
    "vehicle_roster_url": None,
    "employee_roster_url": None,
    "hierarchy_roster_url": None,
    "sync_enabled": False,
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
    if "vehicle_lookup_url" in patch:
        url = (patch["vehicle_lookup_url"] or "").strip() or None
        if url and not (url.startswith("http://") or url.startswith("https://")):
            raise HTTPException(400, "Vehicle lookup URL must start with http:// or https://")
        cfg["vehicle_lookup_url"] = url
    if "employee_lookup_url" in patch:
        url = (patch["employee_lookup_url"] or "").strip() or None
        if url and not (url.startswith("http://") or url.startswith("https://")):
            raise HTTPException(400, "Employee lookup URL must start with http:// or https://")
        cfg["employee_lookup_url"] = url
    for key, label in (("vehicle_roster_url", "Vehicle roster"), ("employee_roster_url", "Employee roster"),
                        ("hierarchy_roster_url", "Hierarchy roster")):
        if key in patch:
            url = (patch[key] or "").strip() or None
            if url and not (url.startswith("http://") or url.startswith("https://")):
                raise HTTPException(400, f"{label} URL must start with http:// or https://")
            cfg[key] = url
    if "sync_enabled" in patch:
        cfg["sync_enabled"] = bool(patch["sync_enabled"])
    if cfg["mode"] == "EXTERNAL_API" and not cfg.get("url"):
        raise HTTPException(400, "Cannot switch to EXTERNAL_API mode without a URL")
    if cfg["sync_enabled"] and not any(cfg.get(k) for k in
                                        ("vehicle_roster_url", "employee_roster_url", "hierarchy_roster_url")):
        raise HTTPException(400, "Cannot enable master-data sync without at least one roster URL configured")

    row = db.query(Config).filter(Config.k == _CONFIG_KEY).first()
    if row:
        row.v = json.dumps(cfg)
    else:
        db.add(Config(k=_CONFIG_KEY, v=json.dumps(cfg)))
    db.commit()
    return cfg


# ---------- LocalMappingProvider ----------

def _level_team(rule, n: str, default_team_code: str, team_map: dict):
    """This level's team_code/team_name: a Routing Rule's lN_team_code
    (Phase 5 stage 2 - e.g. "L3 -> Helpdesk") overrides the default, else
    the default (L1's own routed team for L1-L3, CC_MANAGER for L4)."""
    override = getattr(rule, f"l{n}_team_code", None) if rule else None
    team_code = override or default_team_code
    return team_code, team_map.get(team_code, team_code)


def _level_occupant(db: Session, ticket, rule, n: str):
    """This level's occupant, in precedence order: an explicit local
    username > an external-API organizational role (OE/DM/RM/SPH/...,
    resolved against the ticket's caller via app/services/roles.py) > None,
    meaning "no override - use the level's own default-ladder computation".
    Returns (user, unmapped) - `unmapped` is a
    {"emp_code","name","designation"} dict when a role resolved to a real
    person with no local ccc_user account (Phase 5 stage 2's "unmapped role
    occupant" case), else None."""
    if not rule:
        return None, None
    username = getattr(rule, f"l{n}_username", None)
    if username:
        return get_user_by_username(db, username), None
    role = getattr(rule, f"l{n}_role", None)
    if role:
        holder = resolve_role_holder(db, ticket.caller_emp_id, role)
        if holder:
            return holder.get("user"), (None if holder.get("user") else holder)
    return None, None


def _resolve_local(db: Session, ticket, rule=None) -> list:
    if rule is None:
        rule = match_rule(db, ticket.category, zone_id=ticket.zone_id, district_id=ticket.district_id,
                           subcategory_code=ticket.subcategory_code)
    team_map = get_team_map(db)

    l1_team_code = (rule.l1_team_code if rule and rule.l1_team_code else ticket.team)
    l1_team_name = team_map.get(l1_team_code, l1_team_code)
    l1_user, l1_unmapped = _level_occupant(db, ticket, rule, "1")
    chain = [{"level": "L1", "user": l1_user, "team_code": l1_team_code, "team_name": l1_team_name,
              "unmapped": l1_unmapped}]

    l2_team_code, l2_team_name = _level_team(rule, "2", l1_team_code, team_map)
    l2_user, l2_unmapped = _level_occupant(db, ticket, rule, "2")
    if not l2_user and not l2_unmapped:
        # Same "who gets paged at 80% TAT" pool sla_sweep.py already uses -
        # a Local Team Lead if that (dormant) toggle is on and the ticket has
        # a district, otherwise the team's statewide manager(s).
        managers = []
        if ticket.district_id and get_dispatch_config(db)["local_team_lead_enabled"]:
            managers = get_local_team_lead(db, l1_team_code, ticket.district_id)
        if not managers:
            managers = get_team_managers(db, l1_team_code)
        l2_user = managers[0] if managers else None
    chain.append({"level": "L2", "user": l2_user, "team_code": l2_team_code, "team_name": l2_team_name,
                  "unmapped": l2_unmapped})

    l3_team_code, l3_team_name = _level_team(rule, "3", l1_team_code, team_map)
    l3_user, l3_unmapped = _level_occupant(db, ticket, rule, "3")
    if not l3_user and not l3_unmapped and l2_user and l2_user.reporting_manager_id:
        l3_user = get_user(db, l2_user.reporting_manager_id)
    chain.append({"level": "L3", "user": l3_user, "team_code": l3_team_code, "team_name": l3_team_name,
                  "unmapped": l3_unmapped})

    l4_team_code, l4_team_name = _level_team(rule, "4", "CC_MANAGER", team_map)
    l4_user, l4_unmapped = _level_occupant(db, ticket, rule, "4")
    chain.append({"level": "L4", "user": l4_user, "team_code": l4_team_code, "team_name": l4_team_name,
                  "unmapped": l4_unmapped})

    return chain


# ---------- ExternalApiProvider ----------

def _normalize_external_response(db: Session, data, rule=None) -> list:
    """Tolerant of either shape from the spec's S47 conceptual contract:
    {"hierarchy": [{"level","userId"/"userName","teamId","teamName"}, ...]}
    or, when the external system can only return a flat pool of people with
    no level assigned: {"users": [{"userId"/"userName"}, ...]} - assigned to
    L1..L4 in list order.

    Phase 5 stage 2: an entry's "level" need not already be "L1".."L4" - the
    external hierarchy API may instead return organizational roles
    (OE/DM/RM/SPH/...), which previously made this function silently drop
    the entry. When `rule` maps a role to a level (its lN_role columns -
    see app/models/routing_rule.py), that role's entry is placed at that
    level instead of being discarded; an entry whose role isn't mapped by
    any level, and isn't itself L1-L4, is still dropped."""
    entries = data.get("hierarchy") if isinstance(data, dict) else None
    chain = []
    if entries:
        role_to_level = {}
        if rule:
            for n in ("1", "2", "3", "4"):
                role = getattr(rule, f"l{n}_role", None)
                if role:
                    role_to_level[role.strip().upper()] = f"L{n}"

        for e in entries:
            raw_level = str(e.get("level") or "").strip().upper()
            was_role_mapped = raw_level not in ("L1", "L2", "L3", "L4")
            level = raw_level if not was_role_mapped else role_to_level.get(raw_level)
            if not level:
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
            # Only a role-label entry (not an already-"L1".."L4" one - that
            # path's behavior predates Phase 5 and is intentionally
            # unchanged) that named someone real but unresolvable locally is
            # flagged - same "unmapped role occupant" case as LOCAL mode.
            unmapped = None
            if was_role_mapped and not user and (e.get("name") or uname):
                unmapped = {"emp_code": e.get("empCode") or e.get("emp_code"),
                            "name": e.get("name") or uname, "designation": e.get("designation")}
            chain.append({"level": level, "user": user,
                          "team_code": e.get("teamId") or e.get("team_id"),
                          "team_name": e.get("teamName") or e.get("team_name"),
                          "unmapped": unmapped})
    else:
        users = (data.get("users") if isinstance(data, dict) else None) or []
        for level, e in zip(("L1", "L2", "L3", "L4"), users):
            uname = e.get("username") or e.get("userName")
            user = get_user_by_username(db, uname) if uname else None
            chain.append({"level": level, "user": user, "team_code": None, "team_name": None, "unmapped": None})
    return chain


def _resolve_external_api(db: Session, ticket, cfg: dict, rule=None):
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
    chain = _normalize_external_response(db, data, rule=rule)
    return chain, request_payload, data


# ---------- orchestration ----------

def resolve_hierarchy(db: Session, ticket, rule=None):
    """(chain, mode_used). Never raises - an EXTERNAL_API failure falls back
    to LOCAL so the ticket always gets a usable chain. `rule` lets a caller
    that already matched a Routing Rule (e.g. crud_category.route_ticket, at
    ticket-creation time) hand it in so it's never matched twice."""
    cfg = get_hierarchy_config(db)
    if cfg["mode"] == "EXTERNAL_API" and cfg.get("url"):
        request_payload = None
        try:
            api_rule = rule if rule is not None else match_rule(
                db, ticket.category, zone_id=ticket.zone_id, district_id=ticket.district_id,
                subcategory_code=ticket.subcategory_code)
            chain, request_payload, response_payload = _resolve_external_api(db, ticket, cfg, rule=api_rule)
            if not chain:
                raise ValueError("External hierarchy API returned no recognizable L1-L4 entries")
            log_attempt(db, ticket.id, "EXTERNAL_API", request_payload, response_payload, "SUCCESS")
            return chain, "EXTERNAL_API"
        except Exception as exc:
            log_attempt(db, ticket.id, "EXTERNAL_API", request_payload, None, "ERROR", str(exc))
            create_exception(db, ticket.id, "API_FAILURE", str(exc))
            logger.warning("Hierarchy API failed for ticket %s, falling back to local mapping: %s", ticket.id, exc)

    chain = _resolve_local(db, ticket, rule=rule)
    log_attempt(db, ticket.id, "LOCAL", {"category": ticket.category, "zone_id": ticket.zone_id}, None, "SUCCESS")
    return chain, "LOCAL"


def apply_hierarchy_to_ticket(db: Session, ticket, chain: list, source: str):
    now = datetime.datetime.now()
    for entry in chain:
        unmapped = entry.get("unmapped")
        add_occupant(db, ticket.id, entry["level"], user=entry.get("user"),
                     team_code=entry.get("team_code"), team_name=entry.get("team_name"),
                     source=source, now=now, user_name=(unmapped or {}).get("name"))
        if unmapped:
            # A Routing Rule's lN_role resolved to a real person via the
            # synced hierarchy cache, but they have no ccc_user account -
            # recorded by name only above; flagged here so an admin can
            # create the account or fix the mapping (Phase 5 stage 2).
            create_exception(db, ticket.id, "UNMAPPED_ROLE_OCCUPANT",
                              f"{entry['level']}: {unmapped.get('name')} ({unmapped.get('emp_code')}, "
                              f"{unmapped.get('designation') or 'no designation on file'}) has no CCC user account")
    ticket.current_level = "L1"
    l1 = next((e for e in chain if e["level"] == "L1"), None)
    ticket.current_assignee_username = l1["user"].username if (l1 and l1.get("user")) else None
    db.commit()


def resolve_and_apply(db: Session, ticket, rule=None):
    """Entry point for ticket-creation call sites - swallows everything so a
    hierarchy bug can never fail ticket creation (BR-013; the ticket already
    exists by the time this is called). `rule` - see resolve_hierarchy()."""
    try:
        chain, mode = resolve_hierarchy(db, ticket, rule=rule)
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


def _lookup_headers(cfg: dict) -> dict:
    headers = {}
    if cfg.get("auth_header") and cfg.get("auth_token"):
        headers[cfg["auth_header"]] = cfg["auth_token"]
    return headers


def _normalize_vehicle_response(raw) -> dict:
    """No live upstream system yet - placeholder contract, tolerant of a
    flat object or {"vehicle": {...}} and of snake_case/camelCase keys:
    segment_number, district, mandal, secretariat, village."""
    if not isinstance(raw, dict):
        return None
    obj = raw.get("vehicle") if isinstance(raw.get("vehicle"), dict) else raw

    def g(*keys):
        for k in keys:
            v = obj.get(k)
            if v not in (None, ""):
                return v
        return None

    result = {
        "segment_number": g("segment_number", "segmentNumber", "segment"),
        "district": g("district", "district_name", "districtName"),
        "mandal": g("mandal", "mandal_name", "mandalName"),
        "secretariat": g("secretariat", "secretariat_name", "secretariatName"),
        "village": g("village", "village_name", "villageName"),
    }
    return result if any(result.values()) else None


def lookup_vehicle(db: Session, registration_no: str) -> dict:
    """Cache-first (Phase 5 stage 2): checks the ccc_ext_vehicle roster
    app/services/master_sync.py keeps synced, and only falls through to a
    live GET against cfg['vehicle_lookup_url'] on a cache miss (or when
    nothing has ever been synced). Backs a live form field, not ticket
    creation, so it never raises - an unconfigured or unreachable API just
    means the caller falls back to typing segment/secretariat/village in
    manually. Returns {"configured", "found", "data", "error", "source"}
    where source is "CACHE" or "LIVE"."""
    cached = crud_master_data.get_ext_vehicle(db, registration_no)
    if cached:
        data = {"segment_number": cached.segment_number, "district": cached.district_name,
                "mandal": cached.mandal_name, "secretariat": cached.secretariat, "village": cached.village}
        return {"configured": True, "found": True, "data": data, "error": None, "source": "CACHE",
                "synced_at": cached.synced_at.isoformat() if cached.synced_at else None}

    cfg = get_hierarchy_config(db)
    url = cfg.get("vehicle_lookup_url")
    if not url:
        return {"configured": False, "found": False, "data": None, "error": None, "source": "LIVE"}
    try:
        with httpx.Client(timeout=cfg.get("timeout_seconds", 5.0)) as client:
            resp = client.get(url, params={"registration_no": registration_no}, headers=_lookup_headers(cfg))
        resp.raise_for_status()
        data = _normalize_vehicle_response(resp.json())
    except Exception as exc:
        logger.warning("Vehicle lookup failed for %s: %s", registration_no, exc)
        return {"configured": True, "found": False, "data": None, "error": str(exc), "source": "LIVE"}
    return {"configured": True, "found": data is not None, "data": data, "error": None, "source": "LIVE"}


def _normalize_employee_response(raw) -> list:
    """Placeholder contract - tolerant of a bare list or {"employees": [...]}
    of {emp_id, name, designation} under a few likely key spellings."""
    items = raw if isinstance(raw, list) else ((raw.get("employees") if isinstance(raw, dict) else None) or [])
    results = []
    for e in items:
        if not isinstance(e, dict):
            continue
        emp_id = e.get("emp_id") or e.get("employeeId") or e.get("employee_id") or e.get("id")
        name = e.get("name") or e.get("employeeName") or e.get("full_name")
        designation = e.get("designation") or e.get("designationName") or e.get("designation_name")
        if emp_id or name:
            results.append({"emp_id": emp_id, "name": name, "designation": designation})
    return results


def search_employees(db: Session, query: str) -> dict:
    """Cache-first (Phase 5 stage 2): searches the ccc_ext_employee roster
    app/services/master_sync.py keeps synced, and only falls through to a
    live GET against cfg['employee_lookup_url'] when the cache has nothing
    for this query (including "cache never populated" - so this degrades
    exactly like before on a fresh install with sync never configured).
    Never raises - see lookup_vehicle(). Returns {"configured", "results",
    "error", "source"} where source is "CACHE" or "LIVE"."""
    cached = crud_master_data.search_ext_employees(db, query)
    if cached:
        results = [{"emp_id": e.emp_code, "name": e.name, "designation": e.designation} for e in cached]
        return {"configured": True, "results": results, "error": None, "source": "CACHE"}

    cfg = get_hierarchy_config(db)
    url = cfg.get("employee_lookup_url")
    if not url:
        return {"configured": False, "results": [], "error": None, "source": "LIVE"}
    try:
        with httpx.Client(timeout=cfg.get("timeout_seconds", 5.0)) as client:
            resp = client.get(url, params={"q": query}, headers=_lookup_headers(cfg))
        resp.raise_for_status()
        results = _normalize_employee_response(resp.json())
    except Exception as exc:
        logger.warning("Employee lookup failed for query %r: %s", query, exc)
        return {"configured": True, "results": [], "error": str(exc), "source": "LIVE"}
    return {"configured": True, "results": results, "error": None, "source": "LIVE"}


def send_lookup_test_ping(db: Session, kind: str) -> dict:
    """Connectivity check for the admin 'Test' buttons on the vehicle/employee
    lookup URLs - mirrors send_test_ping() below but GET-based, matching how
    lookup_vehicle()/search_employees() actually call out."""
    cfg = get_hierarchy_config(db)
    url_key = "vehicle_lookup_url" if kind == "vehicle" else "employee_lookup_url"
    url = cfg.get(url_key)
    if not url:
        raise HTTPException(400, f"Configure a {kind} lookup URL first")
    params = {"registration_no": "TEST"} if kind == "vehicle" else {"q": "test"}
    started = time.monotonic()
    try:
        with httpx.Client(timeout=cfg.get("timeout_seconds", 5.0)) as client:
            resp = client.get(url, params=params, headers=_lookup_headers(cfg))
        return {"ok": resp.status_code < 300, "status_code": resp.status_code,
                "elapsed_ms": round((time.monotonic() - started) * 1000)}
    except httpx.HTTPError as exc:
        return {"ok": False, "error": str(exc), "elapsed_ms": round((time.monotonic() - started) * 1000)}


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
