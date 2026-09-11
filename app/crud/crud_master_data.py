"""Read/write access to the Phase 5 stage 2 master-data cache (shadow copies
of the external vehicle/employee/hierarchy rosters - see
app/models/ext_vehicle.py, ext_employee.py, emp_hierarchy.py, sync_run.py).
Write side is used by app/services/master_sync.py's sync jobs; read side
backs app/services/hierarchy.py's cache-first lookup_vehicle()/
search_employees(), app/services/roles.py's resolve_role_holder(), and the
admin Sync Status screen."""
import datetime
from sqlalchemy.orm import Session
from app.models.ext_vehicle import ExtVehicle
from app.models.ext_employee import ExtEmployee
from app.models.emp_hierarchy import EmpHierarchy
from app.models.sync_run import SyncRun

# ---------- reads ----------

def get_ext_vehicle(db: Session, registration_no: str):
    if not registration_no:
        return None
    return db.query(ExtVehicle).filter(ExtVehicle.registration_no == registration_no.strip().upper(),
                                        ExtVehicle.is_active == True).first()

def search_ext_employees(db: Session, q: str, limit: int = 20):
    if not q:
        return []
    from sqlalchemy import or_
    pattern = f"%{q}%"
    return (db.query(ExtEmployee)
              .filter(ExtEmployee.is_active == True,
                      or_(ExtEmployee.name.like(pattern), ExtEmployee.emp_code.like(pattern)))
              .order_by(ExtEmployee.name)
              .limit(min(limit, 50)).all())

def get_emp_hierarchy_holder(db: Session, emp_code: str, role_code: str):
    if not emp_code or not role_code:
        return None
    return db.query(EmpHierarchy).filter(EmpHierarchy.emp_code == emp_code,
                                          EmpHierarchy.role_code == role_code.strip().upper()).first()

def get_last_sync_run(db: Session, job: str):
    return db.query(SyncRun).filter(SyncRun.job == job).order_by(SyncRun.id.desc()).first()

def get_sync_status(db: Session, jobs=("vehicles", "employees", "hierarchy")) -> dict:
    now = datetime.datetime.now()
    status = {}
    for job in jobs:
        run = get_last_sync_run(db, job)
        if not run:
            status[job] = {"job": job, "status": None, "finished_at": None, "rows_upserted": None,
                            "error_message": None, "age_minutes": None}
            continue
        age = (now - run.finished_at).total_seconds() / 60.0 if run.finished_at else None
        status[job] = {"job": job, "status": run.status,
                        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
                        "rows_upserted": run.rows_upserted, "error_message": run.error_message,
                        "age_minutes": round(age) if age is not None else None}
    return status

# ---------- writes (master_sync.py only) ----------

def record_sync_run(db: Session, job: str, started_at, finished_at, status: str,
                     rows_upserted: int = None, error_message: str = None) -> SyncRun:
    row = SyncRun(job=job, started_at=started_at, finished_at=finished_at, status=status,
                   rows_upserted=rows_upserted, error_message=(error_message or "")[:500] or None)
    db.add(row)
    db.commit()
    return row

def upsert_ext_vehicles(db: Session, rows: list, synced_at: datetime.datetime, chunk_size: int = 500) -> int:
    """rows: [{registration_no, segment_number, district_name, mandal_name,
    secretariat, village, district_id, mandal_id}]. Upserts by
    registration_no, marks any existing row not present in `rows`
    is_active=False (never deleted), commits every `chunk_size` rows."""
    seen = set()
    count = 0
    for i, r in enumerate(rows):
        reg = (r.get("registration_no") or "").strip().upper()
        if not reg:
            continue
        seen.add(reg)
        existing = db.query(ExtVehicle).filter(ExtVehicle.registration_no == reg).first()
        if not existing:
            existing = ExtVehicle(registration_no=reg)
            db.add(existing)
        existing.segment_number = r.get("segment_number")
        existing.district_name = r.get("district_name")
        existing.mandal_name = r.get("mandal_name")
        existing.secretariat = r.get("secretariat")
        existing.village = r.get("village")
        existing.district_id = r.get("district_id")
        existing.mandal_id = r.get("mandal_id")
        existing.is_active = True
        existing.synced_at = synced_at
        count += 1
        if (i + 1) % chunk_size == 0:
            db.commit()
    db.commit()
    if seen:
        (db.query(ExtVehicle)
           .filter(ExtVehicle.registration_no.notin_(seen), ExtVehicle.is_active == True)
           .update({"is_active": False}, synchronize_session=False))
        db.commit()
    return count

def upsert_ext_employees(db: Session, rows: list, synced_at: datetime.datetime, chunk_size: int = 500) -> int:
    """rows: [{emp_code, name, designation, role_code, phone}]."""
    seen = set()
    count = 0
    for i, r in enumerate(rows):
        code = (r.get("emp_code") or "").strip()
        if not code:
            continue
        seen.add(code)
        existing = db.query(ExtEmployee).filter(ExtEmployee.emp_code == code).first()
        if not existing:
            existing = ExtEmployee(emp_code=code)
            db.add(existing)
        existing.name = r.get("name")
        existing.designation = r.get("designation")
        existing.role_code = (r.get("role_code") or "").strip().upper() or None
        existing.phone = r.get("phone")
        existing.is_active = True
        existing.synced_at = synced_at
        count += 1
        if (i + 1) % chunk_size == 0:
            db.commit()
    db.commit()
    if seen:
        (db.query(ExtEmployee)
           .filter(ExtEmployee.emp_code.notin_(seen), ExtEmployee.is_active == True)
           .update({"is_active": False}, synchronize_session=False))
        db.commit()
    return count

def upsert_emp_hierarchy(db: Session, rows: list, synced_at: datetime.datetime, chunk_size: int = 500) -> int:
    """rows: [{emp_code, role_code, holder_emp_code, holder_name,
    holder_designation}]. Full replace-by-(emp_code, role_code) since a
    stale "who used to be your OE" row is actively wrong, not just stale -
    unlike vehicles/employees there's no is_active flag here."""
    count = 0
    for i, r in enumerate(rows):
        emp_code = (r.get("emp_code") or "").strip()
        role_code = (r.get("role_code") or "").strip().upper()
        if not emp_code or not role_code:
            continue
        existing = db.query(EmpHierarchy).filter(EmpHierarchy.emp_code == emp_code,
                                                   EmpHierarchy.role_code == role_code).first()
        if not existing:
            existing = EmpHierarchy(emp_code=emp_code, role_code=role_code)
            db.add(existing)
        existing.holder_emp_code = r.get("holder_emp_code")
        existing.holder_name = r.get("holder_name")
        existing.holder_designation = r.get("holder_designation")
        existing.synced_at = synced_at
        count += 1
        if (i + 1) % chunk_size == 0:
            db.commit()
    db.commit()
    return count
