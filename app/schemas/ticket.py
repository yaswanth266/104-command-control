from typing import Optional, List, Any
from pydantic import BaseModel

class TicketIn(BaseModel):
    mmu_vehicle: Optional[str] = None
    district: Optional[str] = None
    location: Optional[str] = None
    caller_name: Optional[str] = None
    caller_phone: Optional[str] = None
    equipment: Optional[str] = None
    problem: str
    error_code: Optional[str] = None
    impact: Optional[str] = None
    category: str
    priority: str
    subject: Optional[str] = None
    vip: Optional[bool] = False
    district_id: Optional[int] = None
    mandal_id: Optional[int] = None
    vehicle_id: Optional[int] = None
    machine_id: Optional[int] = None
    ticket_type: Optional[str] = None
    subcategory_code: Optional[str] = None

class LogCallIn(BaseModel):
    caller_name: Optional[str] = None
    caller_phone: Optional[str] = None
    note: Optional[str] = None

class ActionIn(BaseModel):
    id: int
    action: str
    diagnosis: Optional[str] = None
    action_taken: Optional[str] = None
    root_cause: Optional[str] = None
    parts: Optional[str] = None
    resolution: Optional[str] = None
    pending_reason: Optional[str] = None
    confirmed_by: Optional[str] = None
    note: Optional[str] = None
    assignee: Optional[str] = None
    team: Optional[str] = None
    priority: Optional[str] = None
