from typing import Optional, Dict, List
from pydantic import BaseModel

class TeamIn(BaseModel):
    code: str
    name: str

class TeamUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None

class CategoryIn(BaseModel):
    code: str
    label: str
    team_code: str
    default_owner: Optional[str] = None
    route_by_zone: Optional[bool] = False
    visible_to_lt: Optional[bool] = False
    ticket_type: Optional[str] = None

class CategoryUpdate(BaseModel):
    label: Optional[str] = None
    team_code: Optional[str] = None
    default_owner: Optional[str] = None
    is_active: Optional[bool] = None
    route_by_zone: Optional[bool] = None
    visible_to_lt: Optional[bool] = None
    ticket_type: Optional[str] = None

class ReasonIn(BaseModel):
    code: str
    category_code: str
    label: str
    ticket_type: Optional[str] = None

class ReasonUpdate(BaseModel):
    label: Optional[str] = None
    is_active: Optional[bool] = None
    ticket_type: Optional[str] = None

class TicketTypeIn(BaseModel):
    code: str
    label: str
    requires_approval: Optional[bool] = False

class TicketTypeUpdate(BaseModel):
    label: Optional[str] = None
    requires_approval: Optional[bool] = None
    is_active: Optional[bool] = None

class PriorityIn(BaseModel):
    code: str
    label: str
    description: Optional[str] = None
    severity: Optional[int] = None
    display_order: Optional[int] = 0

class PriorityUpdate(BaseModel):
    label: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[int] = None
    display_order: Optional[int] = None
    is_active: Optional[bool] = None

class PriorityMatrixCellIn(BaseModel):
    impact_code: str
    urgency_code: str
    priority_code: str

class SlaPolicyIn(BaseModel):
    code: str
    priority_code: str
    resolution_mins: int
    calendar_code: Optional[str] = "DEFAULT-24X7"
    response_mins: Optional[int] = None
    subcategory_code: Optional[str] = None
    category_code: Optional[str] = None
    ticket_type: Optional[str] = None

class SlaPolicyUpdate(BaseModel):
    resolution_mins: Optional[int] = None
    response_mins: Optional[int] = None
    calendar_code: Optional[str] = None
    is_active: Optional[bool] = None

class BusinessCalendarIn(BaseModel):
    code: str
    name: str
    is_24x7: Optional[bool] = True
    timezone: Optional[str] = "Asia/Kolkata"
    working_hours: Optional[Dict[str, Optional[List[str]]]] = None

class BusinessCalendarUpdate(BaseModel):
    name: Optional[str] = None
    is_24x7: Optional[bool] = None
    timezone: Optional[str] = None
    working_hours: Optional[Dict[str, Optional[List[str]]]] = None
    is_active: Optional[bool] = None

class CalendarHolidayIn(BaseModel):
    holiday_date: str
    label: Optional[str] = None

class MachineIn(BaseModel):
    name: str

class MachineUpdate(BaseModel):
    is_active: Optional[bool] = None

class DistrictIn(BaseModel):
    name: str

class DistrictUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None

class ZoneIn(BaseModel):
    name: str
    team_code: str

class ZoneUpdate(BaseModel):
    name: Optional[str] = None
    team_code: Optional[str] = None
    is_active: Optional[bool] = None

class MandalIn(BaseModel):
    name: str
    district_id: int
    zone_id: Optional[int] = None

class MandalUpdate(BaseModel):
    name: Optional[str] = None
    district_id: Optional[int] = None
    zone_id: Optional[int] = None
    is_active: Optional[bool] = None

class VehicleIn(BaseModel):
    registration_no: str
    last_mandal_id: Optional[int] = None

class VehicleUpdate(BaseModel):
    last_mandal_id: Optional[int] = None
    is_active: Optional[bool] = None

class SlaUpdate(BaseModel):
    sla: Optional[Dict[str, float]] = None
    tat: Optional[Dict[str, int]] = None
    vip_keywords: Optional[List[str]] = None

class DispatchUpdate(BaseModel):
    local_team_lead_enabled: Optional[bool] = None

class WebhookConfigUpdate(BaseModel):
    url: Optional[str] = None
    secret: Optional[str] = None
    enabled: Optional[bool] = None
    events: Optional[List[str]] = None
    timeout_seconds: Optional[float] = None

class UserIn(BaseModel):
    username: str
    name: str
    role: str
    password: str
    phone: Optional[str] = None
    hr_emp_code: Optional[str] = None
    reporting_manager_id: Optional[int] = None
    is_team_manager: Optional[bool] = False
    vehicle_id: Optional[int] = None
    district_id: Optional[int] = None
    mandal_id: Optional[int] = None

class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    phone: Optional[str] = None
    active: Optional[bool] = None
    password: Optional[str] = None
    hr_emp_code: Optional[str] = None
    reporting_manager_id: Optional[int] = None  # 0 clears it, matches crud_user.py's sentinel
    is_team_manager: Optional[bool] = None
    vehicle_id: Optional[int] = None    # 0 clears it, matches crud_user.py's sentinel
    district_id: Optional[int] = None   # 0 clears it, matches crud_user.py's sentinel
    mandal_id: Optional[int] = None     # 0 clears it, matches crud_user.py's sentinel

class RoutingRuleIn(BaseModel):
    code: str
    category_code: str
    subcategory_code: Optional[str] = None
    district_id: Optional[int] = None
    zone_id: Optional[int] = None
    l1_team_code: Optional[str] = None
    l1_username: Optional[str] = None
    l1_role: Optional[str] = None
    l2_team_code: Optional[str] = None
    l2_username: Optional[str] = None
    l2_role: Optional[str] = None
    l3_team_code: Optional[str] = None
    l3_username: Optional[str] = None
    l3_role: Optional[str] = None
    l4_team_code: Optional[str] = None
    l4_username: Optional[str] = None
    l4_role: Optional[str] = None

class RoutingRuleUpdate(BaseModel):
    l1_team_code: Optional[str] = None
    l1_username: Optional[str] = None
    l1_role: Optional[str] = None
    l2_team_code: Optional[str] = None
    l2_username: Optional[str] = None
    l2_role: Optional[str] = None
    l3_team_code: Optional[str] = None
    l3_username: Optional[str] = None
    l3_role: Optional[str] = None
    l4_team_code: Optional[str] = None
    l4_username: Optional[str] = None
    l4_role: Optional[str] = None
    is_active: Optional[bool] = None

class HierarchyConfigUpdate(BaseModel):
    mode: Optional[str] = None
    url: Optional[str] = None
    auth_header: Optional[str] = None
    auth_token: Optional[str] = None
    timeout_seconds: Optional[float] = None
    vehicle_lookup_url: Optional[str] = None
    employee_lookup_url: Optional[str] = None
    vehicle_roster_url: Optional[str] = None
    employee_roster_url: Optional[str] = None
    hierarchy_roster_url: Optional[str] = None
    sync_enabled: Optional[bool] = None
