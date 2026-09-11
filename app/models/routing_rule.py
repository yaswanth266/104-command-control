from sqlalchemy import Column, Integer, String, Boolean, DateTime, text
from sqlalchemy.sql import func
from app.db.database import Base

class RoutingRule(Base):
    """Explicit local L1-L4 mapping for when there's no external hierarchy
    API, or the API doesn't provide the mapping itself (see
    app/services/hierarchy.py's LocalMappingProvider). Matching is by
    category_code (required) optionally narrowed by zone_id - the most
    specific active match (category+zone over category-only) wins. Any
    L-level left blank falls back to the default ladder: L1 = the ticket's
    routed team (unchanged from today's resolve_team), L2 = that team's
    manager, L3 = L2's reporting_manager_id, L4 = CC_MANAGER.
    ticket_type/subcategory_code are reserved for a future, more specific
    precedence tier - not read by the matcher yet."""
    __tablename__ = "ccc_routing_rule"

    code = Column(String(48), primary_key=True)
    category_code = Column(String(24), index=True, nullable=False)
    zone_id = Column(Integer, index=True)
    ticket_type = Column(String(24))
    subcategory_code = Column(String(32))

    l1_team_code = Column(String(24))
    l1_username = Column(String(64))
    l2_username = Column(String(64))
    l3_username = Column(String(64))
    l4_username = Column(String(64))

    is_active = Column(Boolean, server_default=text("1"), nullable=False)
    created_at = Column(DateTime, default=func.now())
