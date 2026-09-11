"""Master-data sync (Phase 5 stage 2): polls the external vehicle/employee/
hierarchy rosters every CCC_MASTER_SYNC_SECONDS into the ccc_ext_vehicle/
ccc_ext_employee/ccc_emp_hierarchy cache tables (app/crud/crud_master_data.py)
so Register Call's lookups and Routing Rule role mapping
(app/services/roles.py) don't depend on a live per-request call to the
external API. Mirrors app/services/sla_sweep.py's shape: a synchronous
run_master_sync_once() (tests call it directly) plus an async loop started
from main.py's lifespan.

Off by default (ccc_config's 'hierarchy' key, sync_enabled) - see
app/services/hierarchy.py's get_hierarchy_config()/update_hierarchy_config().
Each of the three jobs is independent: one failing doesn't stop the others,
and none of them can ever corrupt ccc_vehicle/ccc_user - see
app/models/ext_vehicle.py's docstring for why these are separate shadow
tables rather than upserts into the live master data."""
import asyncio
import datetime
import logging

import httpx
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.core.config import CCC_MASTER_SYNC_SECONDS
from app.services.hierarchy import get_hierarchy_config, _lookup_headers
from app.crud import crud_master_data
from app.crud.crud_geo import get_districts, get_mandals

logger = logging.getLogger("ccc.master_sync")

# A truncated/empty API response must never wipe out an otherwise-healthy
# roster - abort the upsert (and record the run as an ERROR) rather than
# mark everything else inactive.
_MIN_ROW_FRACTION = 0.5


def _get(url: str, cfg: dict) -> dict:
    with httpx.Client(timeout=cfg.get("timeout_seconds", 5.0)) as client:
        resp = client.get(url, headers=_lookup_headers(cfg))
    resp.raise_for_status()
    return resp.json()


def _looks_truncated(new_count: int, existing_count: int) -> bool:
    if new_count == 0 and existing_count > 0:
        return True
    return existing_count > 0 and new_count < existing_count * _MIN_ROW_FRACTION


def _normalize_vehicle_roster(raw) -> list:
    """Tolerant of a bare list or {"vehicles": [...]}; same key-spelling
    tolerance as hierarchy.py's single-item _normalize_vehicle_response."""
    items = raw if isinstance(raw, list) else ((raw.get("vehicles") if isinstance(raw, dict) else None) or [])
    results = []
    for e in items:
        if not isinstance(e, dict):
            continue

        def g(*keys):
            for k in keys:
                v = e.get(k)
                if v not in (None, ""):
                    return v
            return None

        reg = g("registration_no", "registrationNo", "vehicle_number", "vehicleNumber")
        if not reg:
            continue
        results.append({
            "registration_no": reg,
            "segment_number": g("segment_number", "segmentNumber", "segment"),
            "district_name": g("district", "district_name", "districtName"),
            "mandal_name": g("mandal", "mandal_name", "mandalName"),
            "secretariat": g("secretariat", "secretariat_name", "secretariatName"),
            "village": g("village", "village_name", "villageName"),
        })
    return results


def _normalize_employee_roster(raw) -> list:
    items = raw if isinstance(raw, list) else ((raw.get("employees") if isinstance(raw, dict) else None) or [])
    results = []
    for e in items:
        if not isinstance(e, dict):
            continue

        def g(*keys):
            for k in keys:
                v = e.get(k)
                if v not in (None, ""):
                    return v
            return None

        emp_code = g("emp_code", "empCode", "emp_id", "employeeId", "employee_id", "id")
        if not emp_code:
            continue
        results.append({
            "emp_code": emp_code,
            "name": g("name", "employeeName", "full_name"),
            "designation": g("designation", "designationName", "designation_name"),
            "role_code": g("role_code", "roleCode", "role"),
            "phone": g("phone", "mobile", "phoneNumber"),
        })
    return results


def _normalize_hierarchy_roster(raw) -> list:
    """Tolerant of a flat list of {emp_code, role_code, holder_...} rows, or
    a per-employee nested shape: {"emp_code": "E1", "roles": {"OE": {
    "emp_code"/"name"/"designation"}, "DM": {...}}} - either directly, or
    wrapped in {"employees": [...]}."""
    items = raw if isinstance(raw, list) else ((raw.get("employees") if isinstance(raw, dict) else None) or
                                                (raw.get("hierarchy") if isinstance(raw, dict) else None) or [])
    results = []
    for e in items:
        if not isinstance(e, dict):
            continue
        emp_code = e.get("emp_code") or e.get("empCode")
        if not emp_code:
            continue
        roles = e.get("roles")
        if isinstance(roles, dict):
            for role_code, holder in roles.items():
                if not isinstance(holder, dict):
                    continue
                results.append({
                    "emp_code": emp_code, "role_code": role_code,
                    "holder_emp_code": holder.get("emp_code") or holder.get("empCode"),
                    "holder_name": holder.get("name"), "holder_designation": holder.get("designation"),
                })
        elif e.get("role_code") or e.get("roleCode"):
            results.append({
                "emp_code": emp_code, "role_code": e.get("role_code") or e.get("roleCode"),
                "holder_emp_code": e.get("holder_emp_code") or e.get("holderEmpCode"),
                "holder_name": e.get("holder_name") or e.get("holderName"),
                "holder_designation": e.get("holder_designation") or e.get("holderDesignation"),
            })
    return results


def _resolve_geo_ids(db: Session, rows: list) -> None:
    """Best-effort: fills district_id/mandal_id on vehicle roster rows by
    matching district_name/mandal_name against the locally configured geo
    master, case-insensitively. Leaves them None on no match - a vehicle
    roster row with no local geo match is still cached and still useful for
    its segment/secretariat/village text fields."""
    districts = {d.name.strip().lower(): d.id for d in get_districts(db)}
    mandals = {m.name.strip().lower(): m.id for m in get_mandals(db)}
    for r in rows:
        if r.get("district_name"):
            r["district_id"] = districts.get(r["district_name"].strip().lower())
        if r.get("mandal_name"):
            r["mandal_id"] = mandals.get(r["mandal_name"].strip().lower())


def _run_job(db: Session, job: str, url: str, cfg: dict, normalize, existing_count_fn, upsert_fn) -> int:
    started = datetime.datetime.now()
    try:
        raw = _get(url, cfg)
        rows = normalize(raw)
        existing_count = existing_count_fn(db)
        if _looks_truncated(len(rows), existing_count):
            raise ValueError(f"Roster response looks truncated: {len(rows)} rows vs {existing_count} currently "
                              f"cached - aborting to avoid wiping good data")
        count = upsert_fn(db, rows, started)
        crud_master_data.record_sync_run(db, job, started, datetime.datetime.now(), "SUCCESS", rows_upserted=count)
        return count
    except Exception as exc:
        logger.warning("Master sync job %r failed: %s", job, exc)
        crud_master_data.record_sync_run(db, job, started, datetime.datetime.now(), "ERROR", error_message=str(exc))
        return 0


def sync_vehicles(db: Session, cfg: dict) -> int:
    url = cfg.get("vehicle_roster_url")
    if not url:
        return 0

    def upsert(db, rows, started):
        _resolve_geo_ids(db, rows)
        return crud_master_data.upsert_ext_vehicles(db, rows, started)

    from app.models.ext_vehicle import ExtVehicle
    return _run_job(db, "vehicles", url, cfg, _normalize_vehicle_roster,
                     lambda db: db.query(ExtVehicle).filter(ExtVehicle.is_active == True).count(), upsert)


def sync_employees(db: Session, cfg: dict) -> int:
    url = cfg.get("employee_roster_url")
    if not url:
        return 0
    from app.models.ext_employee import ExtEmployee
    return _run_job(db, "employees", url, cfg, _normalize_employee_roster,
                     lambda db: db.query(ExtEmployee).filter(ExtEmployee.is_active == True).count(),
                     crud_master_data.upsert_ext_employees)


def sync_hierarchy(db: Session, cfg: dict) -> int:
    url = cfg.get("hierarchy_roster_url")
    if not url:
        return 0
    from app.models.emp_hierarchy import EmpHierarchy
    return _run_job(db, "hierarchy", url, cfg, _normalize_hierarchy_roster,
                     lambda db: db.query(EmpHierarchy).count(), crud_master_data.upsert_emp_hierarchy)


def run_master_sync_once():
    """One pass over all three jobs. Safe to call repeatedly - each job is
    a full upsert-by-natural-key, not an incremental delta."""
    db = SessionLocal()
    try:
        cfg = get_hierarchy_config(db)
        if not cfg.get("sync_enabled"):
            return
        sync_vehicles(db, cfg)
        sync_employees(db, cfg)
        sync_hierarchy(db, cfg)
    except Exception:
        logger.exception("Master sync pass failed")
        db.rollback()
    finally:
        db.close()


async def master_sync_loop():
    while True:
        await asyncio.to_thread(run_master_sync_once)
        await asyncio.sleep(CCC_MASTER_SYNC_SECONDS)
