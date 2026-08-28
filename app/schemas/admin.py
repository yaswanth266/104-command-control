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

class CategoryUpdate(BaseModel):
    label: Optional[str] = None
    team_code: Optional[str] = None
    default_owner: Optional[str] = None
    is_active: Optional[bool] = None
    route_by_zone: Optional[bool] = None

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

class UserIn(BaseModel):
    username: str
    name: str
    role: str
    password: str
    phone: Optional[str] = None
    hr_emp_code: Optional[str] = None
    reporting_manager_id: Optional[int] = None
    is_team_manager: Optional[bool] = False

class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    phone: Optional[str] = None
    active: Optional[bool] = None
    password: Optional[str] = None
    hr_emp_code: Optional[str] = None
    reporting_manager_id: Optional[int] = None  # 0 clears it, matches crud_user.py's sentinel
    is_team_manager: Optional[bool] = None
