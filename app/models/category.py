from sqlalchemy import Column, String, Boolean, DateTime, text
from sqlalchemy.sql import func
from app.db.database import Base

class Category(Base):
    __tablename__ = "ccc_category"

    code = Column(String(24), primary_key=True)
    label = Column(String(191), nullable=False)
    team_code = Column(String(24), index=True, nullable=False)
    default_owner = Column(String(128))
    # If true, routing for this category prefers the ticket's Zone (derived
    # from its Mandal) over this category's own team_code, when a Zone is
    # configured - for issues needing physical/geographic dispatch. Central
    # categories (software, network, ...) leave this false.
    route_by_zone = Column(Boolean, server_default=text("0"), nullable=False)
    # Whether this category is offered on the LT self-service portal. Kept
    # false by default so existing internal-only categories (Application,
    # Network, ...) don't suddenly appear there.
    visible_to_lt = Column(Boolean, server_default=text("0"), nullable=False)
    is_active = Column(Boolean, server_default=text("1"), nullable=False)
    created_at = Column(DateTime, default=func.now())
