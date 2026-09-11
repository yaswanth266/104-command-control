"""Resolves a Routing Rule's lN_role (an external-API organizational role
such as OE/DM/RM/SPH) to the person who actually holds that role above a
given ticket's caller, using the ccc_emp_hierarchy cache
app/services/master_sync.py refreshes every CCC_MASTER_SYNC_SECONDS
(Phase 5 stage 2). Consumed by app/services/hierarchy.py's _resolve_local()."""
from sqlalchemy.orm import Session
from app.crud.crud_master_data import get_emp_hierarchy_holder
from app.models.user import User


def resolve_role_holder(db: Session, emp_code: str, role_code: str) -> dict:
    """{"emp_code", "name", "designation", "user"} for the person holding
    role_code (OE/DM/RM/SPH/...) above the employee identified by emp_code,
    or None if emp_code is blank or nothing has been synced for them yet.
    `user` is the local ccc_user account joined on User.hr_emp_code, or None
    when that person has no CCC account - hierarchy._resolve_local() treats
    that as an unmapped-role-occupant case (recorded by name only, with an
    Assignment Exception raised for review)."""
    if not emp_code or not role_code:
        return None
    holder = get_emp_hierarchy_holder(db, emp_code, role_code)
    if not holder or not holder.holder_emp_code:
        return None
    user = db.query(User).filter(User.hr_emp_code == holder.holder_emp_code, User.active == True).first()
    return {"emp_code": holder.holder_emp_code, "name": holder.holder_name,
            "designation": holder.holder_designation, "user": user}
