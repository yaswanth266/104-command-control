from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.api.deps import require_admin
from app.schemas.admin import (TeamIn, TeamUpdate, CategoryIn, CategoryUpdate, SlaUpdate, UserIn, UserUpdate,
                                DistrictIn, DistrictUpdate, ZoneIn, ZoneUpdate, MandalIn, MandalUpdate,
                                VehicleIn, VehicleUpdate, ReasonIn, ReasonUpdate, MachineIn, MachineUpdate,
                                DispatchUpdate, WebhookConfigUpdate, TicketTypeIn, TicketTypeUpdate,
                                PriorityIn, PriorityUpdate, PriorityMatrixCellIn,
                                SlaPolicyIn, SlaPolicyUpdate, BusinessCalendarIn, BusinessCalendarUpdate,
                                CalendarHolidayIn, RoutingRuleIn, RoutingRuleUpdate, HierarchyConfigUpdate)
from app.crud import (crud_team, crud_category, crud_settings, crud_user, crud_geo, crud_vehicle, crud_reason,
                      crud_machine, crud_ticket_type, crud_priority, crud_priority_matrix,
                      crud_sla_policy, crud_calendar, crud_routing_rule, crud_assignment_exception)
from app.crud.crud_admin_event import log_admin_event, get_admin_events
from app.services import webhooks as webhook_service
from app.services import hierarchy as hierarchy_service

router = APIRouter(prefix="/admin", tags=["admin"])

def _team_out(t):
    return {"code": t.code, "name": t.name, "is_active": t.is_active}

def _category_out(c):
    return {"code": c.code, "label": c.label, "team_code": c.team_code, "default_owner": c.default_owner,
            "is_active": c.is_active, "route_by_zone": c.route_by_zone, "visible_to_lt": c.visible_to_lt,
            "ticket_type": c.ticket_type}

def _ticket_type_out(t):
    return {"code": t.code, "label": t.label, "requires_approval": t.requires_approval, "is_active": t.is_active}

def _priority_out(p):
    return {"code": p.code, "label": p.label, "description": p.description, "severity": p.severity,
            "display_order": p.display_order, "is_active": p.is_active}

def _matrix_cell_out(m):
    return {"impact_code": m.impact_code, "urgency_code": m.urgency_code, "priority_code": m.priority_code}

def _user_out(u):
    return {"id": u.id, "username": u.username, "name": u.name, "role": u.role, "phone": u.phone, "active": u.active,
            "hr_emp_code": u.hr_emp_code, "reporting_manager_id": u.reporting_manager_id,
            "is_team_manager": u.is_team_manager, "vehicle_id": u.vehicle_id,
            "district_id": u.district_id, "mandal_id": u.mandal_id}

def _reason_out(r):
    return {"code": r.code, "category_code": r.category_code, "label": r.label, "is_active": r.is_active,
            "ticket_type": r.ticket_type}

def _machine_out(m):
    return {"id": m.id, "name": m.name, "is_active": m.is_active}

def _district_out(d):
    return {"id": d.id, "name": d.name, "is_active": d.is_active}

def _zone_out(z):
    return {"id": z.id, "name": z.name, "team_code": z.team_code, "is_active": z.is_active}

def _mandal_out(m):
    return {"id": m.id, "name": m.name, "district_id": m.district_id, "zone_id": m.zone_id, "is_active": m.is_active}

def _vehicle_out(v):
    return {"id": v.id, "registration_no": v.registration_no, "last_mandal_id": v.last_mandal_id, "is_active": v.is_active}

# ---------- teams ----------

@router.get("/teams")
def list_teams(db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    return [_team_out(t) for t in crud_team.get_teams(db, include_inactive=True)]

@router.post("/teams")
def create_team(b: TeamIn, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    t = crud_team.create_team(db, b.code, b.name)
    log_admin_event(db, current_user, "TEAM_CREATED", "team", t.code, f"name={t.name}")
    return _team_out(t)

@router.put("/teams/{code}")
def update_team(code: str, b: TeamUpdate, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    t = crud_team.update_team(db, code.upper(), name=b.name, is_active=b.is_active)
    log_admin_event(db, current_user, "TEAM_UPDATED", "team", t.code, f"name={t.name}, is_active={t.is_active}")
    return _team_out(t)

# ---------- categories ----------

@router.get("/categories")
def list_categories(db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    return [_category_out(c) for c in crud_category.get_categories(db, include_inactive=True)]

@router.post("/categories")
def create_category(b: CategoryIn, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    c = crud_category.create_category(db, b.code, b.label, b.team_code, b.default_owner, b.route_by_zone,
                                       b.visible_to_lt, b.ticket_type)
    log_admin_event(db, current_user, "CATEGORY_CREATED", "category", c.code, f"label={c.label}, team={c.team_code}")
    webhook_service.dispatch_category_event(db, "category.created", c, current_user["username"])
    return _category_out(c)

@router.put("/categories/{code}")
def update_category(code: str, b: CategoryUpdate, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    c = crud_category.update_category(db, code.upper(), label=b.label, team_code=b.team_code,
                                       default_owner=b.default_owner, is_active=b.is_active, route_by_zone=b.route_by_zone,
                                       visible_to_lt=b.visible_to_lt, ticket_type=b.ticket_type)
    log_admin_event(db, current_user, "CATEGORY_UPDATED", "category", c.code,
                     f"label={c.label}, team={c.team_code}, is_active={c.is_active}, "
                     f"route_by_zone={c.route_by_zone}, visible_to_lt={c.visible_to_lt}, ticket_type={c.ticket_type}")
    webhook_service.dispatch_category_event(db, "category.updated", c, current_user["username"])
    return _category_out(c)

# ---------- reasons (Sub-Category master) ----------

@router.get("/reasons")
def list_reasons(category: str = None, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    return [_reason_out(r) for r in crud_reason.get_reasons(db, category_code=category, include_inactive=True)]

@router.post("/reasons")
def create_reason(b: ReasonIn, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    r = crud_reason.create_reason(db, b.code, b.category_code, b.label, b.ticket_type)
    log_admin_event(db, current_user, "REASON_CREATED", "reason", r.code, f"label={r.label}, category={r.category_code}")
    return _reason_out(r)

@router.put("/reasons/{code}")
def update_reason(code: str, b: ReasonUpdate, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    r = crud_reason.update_reason(db, code.upper(), label=b.label, is_active=b.is_active, ticket_type=b.ticket_type)
    log_admin_event(db, current_user, "REASON_UPDATED", "reason", r.code, f"label={r.label}, is_active={r.is_active}")
    return _reason_out(r)

# ---------- ticket types ----------

@router.get("/ticket-types")
def list_ticket_types(db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    return [_ticket_type_out(t) for t in crud_ticket_type.get_ticket_types(db, include_inactive=True)]

@router.post("/ticket-types")
def create_ticket_type(b: TicketTypeIn, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    t = crud_ticket_type.create_ticket_type(db, b.code, b.label, b.requires_approval)
    log_admin_event(db, current_user, "TICKET_TYPE_CREATED", "ticket_type", t.code, f"label={t.label}")
    return _ticket_type_out(t)

@router.put("/ticket-types/{code}")
def update_ticket_type(code: str, b: TicketTypeUpdate, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    t = crud_ticket_type.update_ticket_type(db, code.upper(), label=b.label, requires_approval=b.requires_approval,
                                             is_active=b.is_active)
    log_admin_event(db, current_user, "TICKET_TYPE_UPDATED", "ticket_type", t.code, f"label={t.label}, is_active={t.is_active}")
    return _ticket_type_out(t)

# ---------- priorities + impact/urgency matrix ----------

@router.get("/priorities")
def list_priorities(db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    return [_priority_out(p) for p in crud_priority.get_priorities(db, include_inactive=True)]

@router.post("/priorities")
def create_priority(b: PriorityIn, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    p = crud_priority.create_priority(db, b.code, b.label, b.description, b.severity, b.display_order)
    log_admin_event(db, current_user, "PRIORITY_CREATED", "priority", p.code, f"label={p.label}")
    return _priority_out(p)

@router.put("/priorities/{code}")
def update_priority(code: str, b: PriorityUpdate, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    p = crud_priority.update_priority(db, code.upper(), label=b.label, description=b.description,
                                       severity=b.severity, display_order=b.display_order, is_active=b.is_active)
    log_admin_event(db, current_user, "PRIORITY_UPDATED", "priority", p.code, f"label={p.label}, is_active={p.is_active}")
    return _priority_out(p)

@router.get("/priority-matrix")
def list_priority_matrix(db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    return [_matrix_cell_out(m) for m in crud_priority_matrix.get_matrix(db)]

@router.put("/priority-matrix")
def update_priority_matrix_cell(b: PriorityMatrixCellIn, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    m = crud_priority_matrix.set_cell(db, b.impact_code, b.urgency_code, b.priority_code)
    log_admin_event(db, current_user, "PRIORITY_MATRIX_UPDATED", "priority_matrix",
                     f"{m.impact_code}/{m.urgency_code}", f"priority_code={m.priority_code}")
    return _matrix_cell_out(m)

# ---------- machines ----------

@router.get("/machines")
def list_machines(db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    return [_machine_out(m) for m in crud_machine.get_machines(db, include_inactive=True)]

@router.post("/machines")
def create_machine(b: MachineIn, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    m = crud_machine.create_machine(db, b.name)
    log_admin_event(db, current_user, "MACHINE_CREATED", "machine", str(m.id), f"name={m.name}")
    return _machine_out(m)

@router.put("/machines/{machine_id}")
def update_machine(machine_id: int, b: MachineUpdate, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    m = crud_machine.update_machine(db, machine_id, is_active=b.is_active)
    log_admin_event(db, current_user, "MACHINE_UPDATED", "machine", str(m.id), f"is_active={m.is_active}")
    return _machine_out(m)

# ---------- geography ----------

@router.get("/districts")
def list_districts(db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    return [_district_out(d) for d in crud_geo.get_districts(db, include_inactive=True)]

@router.post("/districts")
def create_district(b: DistrictIn, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    d = crud_geo.create_district(db, b.name)
    log_admin_event(db, current_user, "DISTRICT_CREATED", "district", str(d.id), f"name={d.name}")
    return _district_out(d)

@router.put("/districts/{district_id}")
def update_district(district_id: int, b: DistrictUpdate, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    d = crud_geo.update_district(db, district_id, name=b.name, is_active=b.is_active)
    log_admin_event(db, current_user, "DISTRICT_UPDATED", "district", str(d.id), f"name={d.name}, is_active={d.is_active}")
    return _district_out(d)

@router.get("/zones")
def list_zones(db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    return [_zone_out(z) for z in crud_geo.get_zones(db, include_inactive=True)]

@router.post("/zones")
def create_zone(b: ZoneIn, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    z = crud_geo.create_zone(db, b.name, b.team_code)
    log_admin_event(db, current_user, "ZONE_CREATED", "zone", str(z.id), f"name={z.name}, team={z.team_code}")
    return _zone_out(z)

@router.put("/zones/{zone_id}")
def update_zone(zone_id: int, b: ZoneUpdate, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    z = crud_geo.update_zone(db, zone_id, name=b.name, team_code=b.team_code, is_active=b.is_active)
    log_admin_event(db, current_user, "ZONE_UPDATED", "zone", str(z.id), f"name={z.name}, team={z.team_code}, is_active={z.is_active}")
    return _zone_out(z)

@router.get("/mandals")
def list_mandals(district_id: int = None, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    return [_mandal_out(m) for m in crud_geo.get_mandals(db, district_id=district_id, include_inactive=True)]

@router.post("/mandals")
def create_mandal(b: MandalIn, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    m = crud_geo.create_mandal(db, b.name, b.district_id, b.zone_id)
    log_admin_event(db, current_user, "MANDAL_CREATED", "mandal", str(m.id), f"name={m.name}, district_id={m.district_id}")
    return _mandal_out(m)

@router.put("/mandals/{mandal_id}")
def update_mandal(mandal_id: int, b: MandalUpdate, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    m = crud_geo.update_mandal(db, mandal_id, name=b.name, district_id=b.district_id, zone_id=b.zone_id, is_active=b.is_active)
    log_admin_event(db, current_user, "MANDAL_UPDATED", "mandal", str(m.id),
                     f"name={m.name}, district_id={m.district_id}, zone_id={m.zone_id}, is_active={m.is_active}")
    return _mandal_out(m)

# ---------- vehicles ----------

@router.get("/vehicles")
def list_vehicles(db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    return [_vehicle_out(v) for v in crud_vehicle.get_vehicles(db, include_inactive=True)]

@router.post("/vehicles")
def create_vehicle(b: VehicleIn, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    v = crud_vehicle.create_vehicle(db, b.registration_no, b.last_mandal_id)
    log_admin_event(db, current_user, "VEHICLE_CREATED", "vehicle", str(v.id), f"registration_no={v.registration_no}")
    return _vehicle_out(v)

@router.put("/vehicles/{vehicle_id}")
def update_vehicle(vehicle_id: int, b: VehicleUpdate, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    v = crud_vehicle.update_vehicle(db, vehicle_id, last_mandal_id=b.last_mandal_id, is_active=b.is_active)
    log_admin_event(db, current_user, "VEHICLE_UPDATED", "vehicle", str(v.id), f"is_active={v.is_active}")
    return _vehicle_out(v)

# ---------- SLA & TAT ----------

@router.get("/sla")
def get_sla(db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    from app.crud.crud_ticket import get_tat_map
    return {"sla": crud_settings.get_sla_config(db), "tat": get_tat_map(db), "vip_keywords": crud_settings.get_vip_keywords(db)}

@router.put("/sla")
def update_sla(b: SlaUpdate, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    out = {}
    if b.sla:
        out["sla"] = crud_settings.update_sla_config(db, b.sla)
        log_admin_event(db, current_user, "SLA_SETTINGS_UPDATED", "settings", "sla", str(out["sla"]))
    if b.tat:
        out["tat"] = crud_settings.update_tat_map(db, b.tat)
        log_admin_event(db, current_user, "TAT_UPDATED", "settings", "tat", str(out["tat"]))
        for priority_code in b.tat:
            if priority_code in out["tat"]:
                webhook_service.dispatch_priority_event(db, priority_code, out["tat"][priority_code], current_user["username"])
    if b.vip_keywords is not None:
        out["vip_keywords"] = crud_settings.update_vip_keywords(db, b.vip_keywords)
        log_admin_event(db, current_user, "VIP_KEYWORDS_UPDATED", "settings", "vip_keywords", str(out["vip_keywords"]))
    if not out:
        raise HTTPException(400, "Nothing to update - provide 'sla', 'tat' and/or 'vip_keywords'")
    return out

# ---------- dispatch (Local Team Lead routing - future, dormant by default) ----------

@router.get("/dispatch")
def get_dispatch(db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    return crud_settings.get_dispatch_config(db)

@router.put("/dispatch")
def update_dispatch(b: DispatchUpdate, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    if b.local_team_lead_enabled is None:
        raise HTTPException(400, "Nothing to update - provide 'local_team_lead_enabled'")
    out = crud_settings.update_dispatch_config(db, {"local_team_lead_enabled": b.local_team_lead_enabled})
    log_admin_event(db, current_user, "DISPATCH_SETTINGS_UPDATED", "settings", "dispatch", str(out))
    return out

# ---------- SLA policies ----------

def _sla_policy_out(p):
    return {"code": p.code, "priority_code": p.priority_code, "subcategory_code": p.subcategory_code,
            "category_code": p.category_code, "ticket_type": p.ticket_type,
            "response_mins": p.response_mins, "resolution_mins": p.resolution_mins,
            "calendar_code": p.calendar_code, "is_active": p.is_active}

@router.get("/sla-policies")
def list_sla_policies(db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    return [_sla_policy_out(p) for p in crud_sla_policy.get_policies(db, include_inactive=True)]

@router.post("/sla-policies")
def create_sla_policy(b: SlaPolicyIn, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    p = crud_sla_policy.create_policy(db, b.code, b.priority_code, b.resolution_mins, b.calendar_code,
                                       b.subcategory_code, b.category_code, b.ticket_type, b.response_mins)
    log_admin_event(db, current_user, "SLA_POLICY_CREATED", "sla_policy", p.code,
                     f"priority={p.priority_code}, resolution_mins={p.resolution_mins}")
    return _sla_policy_out(p)

@router.put("/sla-policies/{code}")
def update_sla_policy(code: str, b: SlaPolicyUpdate, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    p = crud_sla_policy.update_policy(db, code.upper(), resolution_mins=b.resolution_mins,
                                       response_mins=b.response_mins, calendar_code=b.calendar_code,
                                       is_active=b.is_active)
    log_admin_event(db, current_user, "SLA_POLICY_UPDATED", "sla_policy", p.code,
                     f"resolution_mins={p.resolution_mins}, is_active={p.is_active}")
    return _sla_policy_out(p)

# ---------- business calendars ----------

def _calendar_out(c):
    return {"code": c.code, "name": c.name, "is_24x7": c.is_24x7, "timezone": c.timezone,
            "working_hours": c.working_hours, "is_active": c.is_active}

def _holiday_out(h):
    return {"id": h.id, "calendar_code": h.calendar_code, "holiday_date": h.holiday_date.strftime("%Y-%m-%d"),
            "label": h.label}

@router.get("/calendars")
def list_calendars(db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    return [_calendar_out(c) for c in crud_calendar.get_calendars(db, include_inactive=True)]

@router.post("/calendars")
def create_calendar(b: BusinessCalendarIn, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    c = crud_calendar.create_calendar(db, b.code, b.name, b.is_24x7, b.timezone, b.working_hours)
    log_admin_event(db, current_user, "CALENDAR_CREATED", "calendar", c.code, f"name={c.name}, is_24x7={c.is_24x7}")
    return _calendar_out(c)

@router.put("/calendars/{code}")
def update_calendar(code: str, b: BusinessCalendarUpdate, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    c = crud_calendar.update_calendar(db, code.upper(), name=b.name, is_24x7=b.is_24x7, timezone=b.timezone,
                                       working_hours=b.working_hours, is_active=b.is_active)
    log_admin_event(db, current_user, "CALENDAR_UPDATED", "calendar", c.code, f"is_24x7={c.is_24x7}, is_active={c.is_active}")
    return _calendar_out(c)

@router.get("/calendars/{code}/holidays")
def list_calendar_holidays(code: str, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    return [_holiday_out(h) for h in crud_calendar.get_holidays(db, code)]

@router.post("/calendars/{code}/holidays")
def add_calendar_holiday(code: str, b: CalendarHolidayIn, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    h = crud_calendar.add_holiday(db, code, b.holiday_date, b.label)
    log_admin_event(db, current_user, "CALENDAR_HOLIDAY_ADDED", "calendar", code, f"date={h.holiday_date}, label={h.label}")
    return _holiday_out(h)

@router.delete("/calendars/holidays/{holiday_id}")
def remove_calendar_holiday(holiday_id: int, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    # Unlike other master data (soft-toggle only), holidays are pure schedule
    # metadata with no ticket-snapshot dependency, so a hard delete here is
    # safe - it doesn't touch anything append-only.
    crud_calendar.delete_holiday(db, holiday_id)
    log_admin_event(db, current_user, "CALENDAR_HOLIDAY_REMOVED", "calendar", str(holiday_id), "")
    return {"ok": True}

# ---------- users ----------
# (GET /users already exists for the roster listing - these add write access)

@router.post("/users")
def create_user(b: UserIn, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    u = crud_user.create_user(db, b.username, b.name, b.role, b.password, b.phone,
                               b.hr_emp_code, b.reporting_manager_id, b.is_team_manager,
                               b.vehicle_id, b.district_id, b.mandal_id)
    log_admin_event(db, current_user, "USER_CREATED", "user", u.username, f"role={u.role}")
    return _user_out(u)

@router.put("/users/{user_id}")
def update_user(user_id: int, b: UserUpdate, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    u = crud_user.update_user(db, user_id, name=b.name, role=b.role, phone=b.phone,
                               active=b.active, password=b.password, hr_emp_code=b.hr_emp_code,
                               reporting_manager_id=b.reporting_manager_id, is_team_manager=b.is_team_manager,
                               vehicle_id=b.vehicle_id, district_id=b.district_id, mandal_id=b.mandal_id)
    detail = f"role={u.role}, active={u.active}" + (", password reset" if b.password else "")
    log_admin_event(db, current_user, "USER_UPDATED", "user", u.username, detail)
    return _user_out(u)

@router.get("/roles")
def list_valid_roles(db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    return crud_user.get_valid_roles(db)

# ---------- outbound webhooks ----------

def _webhook_config_out(cfg: dict) -> dict:
    # secret is never echoed back out - only whether one is set.
    return {"url": cfg.get("url"), "enabled": cfg.get("enabled"), "events": cfg.get("events"),
            "timeout_seconds": cfg.get("timeout_seconds"), "secret_set": bool(cfg.get("secret")),
            "available_events": webhook_service.WEBHOOK_EVENTS}

@router.get("/webhooks/config")
def get_webhook_config(db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    return _webhook_config_out(webhook_service.get_webhook_config(db))

@router.post("/webhooks/config")
def update_webhook_config(b: WebhookConfigUpdate, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    patch = b.model_dump(exclude_unset=True)
    if not patch:
        raise HTTPException(400, "Nothing to update - provide url, secret, enabled, events and/or timeout_seconds")
    cfg = webhook_service.update_webhook_config(db, patch)
    log_admin_event(db, current_user, "WEBHOOK_CONFIG_UPDATED", "settings", "webhook",
                     f"url={cfg.get('url')}, enabled={cfg.get('enabled')}, events={cfg.get('events')}, "
                     f"secret_set={bool(cfg.get('secret'))}")
    return _webhook_config_out(cfg)

@router.post("/webhooks/test")
def test_webhook(db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    result = webhook_service.send_test_ping(db)
    log_admin_event(db, current_user, "WEBHOOK_TEST_PING", "settings", "webhook",
                     f"ok={result.get('ok')}, status_code={result.get('status_code')}, elapsed_ms={result.get('elapsed_ms')}")
    return result

# ---------- routing rules (L1-L4 hierarchy, local mapping) ----------

def _routing_rule_out(r):
    return {"code": r.code, "category_code": r.category_code, "zone_id": r.zone_id,
            "l1_team_code": r.l1_team_code, "l1_username": r.l1_username, "l2_username": r.l2_username,
            "l3_username": r.l3_username, "l4_username": r.l4_username, "is_active": r.is_active}

@router.get("/routing-rules")
def list_routing_rules(db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    return [_routing_rule_out(r) for r in crud_routing_rule.get_rules(db, include_inactive=True)]

@router.post("/routing-rules")
def create_routing_rule(b: RoutingRuleIn, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    r = crud_routing_rule.create_rule(db, b.code, b.category_code, b.zone_id, b.l1_team_code,
                                       b.l1_username, b.l2_username, b.l3_username, b.l4_username)
    log_admin_event(db, current_user, "ROUTING_RULE_CREATED", "routing_rule", r.code,
                     f"category={r.category_code}, zone_id={r.zone_id}")
    return _routing_rule_out(r)

@router.put("/routing-rules/{code}")
def update_routing_rule(code: str, b: RoutingRuleUpdate, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    r = crud_routing_rule.update_rule(db, code.upper(), l1_team_code=b.l1_team_code, l1_username=b.l1_username,
                                       l2_username=b.l2_username, l3_username=b.l3_username,
                                       l4_username=b.l4_username, is_active=b.is_active)
    log_admin_event(db, current_user, "ROUTING_RULE_UPDATED", "routing_rule", r.code, f"is_active={r.is_active}")
    return _routing_rule_out(r)

# ---------- hierarchy source (L1-L4 - local mapping vs external API) ----------

@router.get("/hierarchy/config")
def get_hierarchy_config(db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    cfg = hierarchy_service.get_hierarchy_config(db)
    return {**cfg, "auth_token_set": bool(cfg.get("auth_token")), "auth_token": None}

@router.put("/hierarchy/config")
def update_hierarchy_config(b: HierarchyConfigUpdate, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    patch = b.model_dump(exclude_unset=True)
    if not patch:
        raise HTTPException(400, "Nothing to update - provide mode, url, auth_header, auth_token, timeout_seconds, "
                                  "vehicle_lookup_url and/or employee_lookup_url")
    cfg = hierarchy_service.update_hierarchy_config(db, patch)
    log_admin_event(db, current_user, "HIERARCHY_CONFIG_UPDATED", "settings", "hierarchy",
                     f"mode={cfg.get('mode')}, url={cfg.get('url')}")
    return {**cfg, "auth_token_set": bool(cfg.get("auth_token")), "auth_token": None}

@router.post("/hierarchy/test")
def test_hierarchy_api(db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    result = hierarchy_service.send_test_ping(db)
    log_admin_event(db, current_user, "HIERARCHY_TEST_PING", "settings", "hierarchy",
                     f"ok={result.get('ok')}, status_code={result.get('status_code')}, elapsed_ms={result.get('elapsed_ms')}")
    return result

@router.post("/hierarchy/test-vehicle-lookup")
def test_vehicle_lookup_api(db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    result = hierarchy_service.send_lookup_test_ping(db, "vehicle")
    log_admin_event(db, current_user, "VEHICLE_LOOKUP_TEST_PING", "settings", "hierarchy",
                     f"ok={result.get('ok')}, status_code={result.get('status_code')}")
    return result

@router.post("/hierarchy/test-employee-lookup")
def test_employee_lookup_api(db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    result = hierarchy_service.send_lookup_test_ping(db, "employee")
    log_admin_event(db, current_user, "EMPLOYEE_LOOKUP_TEST_PING", "settings", "hierarchy",
                     f"ok={result.get('ok')}, status_code={result.get('status_code')}")
    return result

# ---------- assignment exceptions (hierarchy resolution recovery queue) ----------

def _assignment_exception_out(e):
    return {"id": e.id, "ticket_id": e.ticket_id, "reason": e.reason, "detail": e.detail, "status": e.status,
            "created_at": e.created_at.strftime("%Y-%m-%d %H:%M") if e.created_at else None,
            "resolved_at": e.resolved_at.strftime("%Y-%m-%d %H:%M") if e.resolved_at else None,
            "resolved_by": e.resolved_by}

@router.get("/assignment-exceptions")
def list_assignment_exceptions(status: str = None, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    return [_assignment_exception_out(e) for e in crud_assignment_exception.get_exceptions(db, status)]

@router.post("/assignment-exceptions/{exception_id}/resolve")
def resolve_assignment_exception(exception_id: int, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    e = crud_assignment_exception.resolve_exception(db, exception_id, current_user["username"])
    log_admin_event(db, current_user, "ASSIGNMENT_EXCEPTION_RESOLVED", "assignment_exception", str(e.id), f"ticket_id={e.ticket_id}")
    return _assignment_exception_out(e)

# ---------- audit ----------

@router.get("/audit")
def list_admin_events(limit: int = 100, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    rows = get_admin_events(db, limit=min(limit, 500))
    return [{"id": e.id, "at": e.at.strftime("%Y-%m-%d %H:%M") if e.at else None, "actor": e.actor,
             "actor_role": e.actor_role, "action": e.action, "entity_type": e.entity_type,
             "entity_id": e.entity_id, "detail": e.detail} for e in rows]
