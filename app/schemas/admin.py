from typing import Optional, Dict
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

class CategoryUpdate(BaseModel):
    label: Optional[str] = None
    team_code: Optional[str] = None
    default_owner: Optional[str] = None
    is_active: Optional[bool] = None

class SlaUpdate(BaseModel):
    sla: Optional[Dict[str, float]] = None
    tat: Optional[Dict[str, int]] = None

class UserIn(BaseModel):
    username: str
    name: str
    role: str
    password: str
    phone: Optional[str] = None

class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    phone: Optional[str] = None
    active: Optional[bool] = None
    password: Optional[str] = None
