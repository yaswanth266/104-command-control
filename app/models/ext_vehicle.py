from sqlalchemy import Column, Integer, String, Boolean, DateTime, text
from app.db.database import Base

class ExtVehicle(Base):
    """5-minute-synced shadow copy of the external vehicle roster (Phase 5
    stage 2) - a read-only cache that app/services/master_sync.py refreshes.
    Deliberately a SEPARATE table from ccc_vehicle (the local MMU registry
    app/models/vehicle.py, which User.vehicle_id/Ticket.vehicle_id reference)
    so a bad or truncated API response can never corrupt those live
    references; nothing points a foreign key at this table. Backs
    app/services/hierarchy.py's lookup_vehicle() as a cache-first layer in
    front of the existing live per-keystroke lookup."""
    __tablename__ = "ccc_ext_vehicle"

    id = Column(Integer, primary_key=True, autoincrement=True)
    registration_no = Column(String(32), unique=True, nullable=False, index=True)
    segment_number = Column(String(64))
    district_name = Column(String(191))
    mandal_name = Column(String(191))
    secretariat = Column(String(191))
    village = Column(String(191))
    # Best-effort resolution of district_name/mandal_name against ccc_district/
    # ccc_mandal by name - nullable, since the external roster's place names
    # won't always match the locally configured geo master 1:1.
    district_id = Column(Integer, index=True)
    mandal_id = Column(Integer, index=True)
    is_active = Column(Boolean, server_default=text("1"), nullable=False)
    synced_at = Column(DateTime)
