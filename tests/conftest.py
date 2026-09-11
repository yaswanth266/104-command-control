"""Test fixtures. Runs against a dedicated `ccc_test` MySQL schema on the same
server as local dev - never the `ccc` database itself. Env vars must be set
before any `app.*` module is imported, since app.core.config builds the DB URL
at import time."""
import os
import pymysql
import pytest

os.environ.setdefault("CCC_SECRET", "test-secret-for-pytest-only-do-not-use-elsewhere")
os.environ.setdefault("CCC_INTAKE_KEY", "test-intake-key-for-pytest-only")
os.environ["CCC_DB_NAME"] = "ccc_test"

INTAKE_KEY = os.environ["CCC_INTAKE_KEY"]

_DB_HOST = os.environ.get("CCC_DB_HOST", "127.0.0.1")
_DB_USER = os.environ.get("CCC_DB_USER", "root")
_DB_PW = os.environ.get("CCC_DB_PW", "root")


def _ensure_test_db():
    conn = pymysql.connect(host=_DB_HOST, user=_DB_USER, password=_DB_PW)
    try:
        with conn.cursor() as cur:
            cur.execute("CREATE DATABASE IF NOT EXISTS ccc_test CHARACTER SET utf8mb4")
        conn.commit()
    finally:
        conn.close()


_ensure_test_db()

from app.db.database import Base, engine, SessionLocal  # noqa: E402
from app.models import (User, Ticket, Event, Notification, Team, Category,  # noqa: E402
                         District, Mandal, Zone, Vehicle, Reason, Machine, TicketType, Priority, PriorityMatrix)
from app.core.security import hash_pw, mktoken  # noqa: E402

ROLES = ["CC_MANAGER", "CALL_TAKER", "SERVICE", "APPLICATION", "QUALITY", "TECHNICAL", "NETWORK", "FIELD_OPS", "FLEET"]

# LT self-service test fixtures: one district/mandal routed (via Zone) to a
# dedicated CDA team, so resolve_team's zone-routing path is exercised
# end-to-end exactly like a real LT-raised ticket would be. IDs are assigned
# by the DB at seed time (see _schema below) and stashed here for tests to
# import, rather than hardcoded, since these are autoincrement PKs.
LT_CDA_TEAM = "CDA_TEST"
LT_CATEGORY = "LT_ISSUE"
LT_REASON_CODES = ["NO_POWER", "CALIBRATION"]
LT_USERNAME = "lt1"
lt_ids = {}  # populated by _schema: district_id, mandal_id, zone_id, vehicle_id, machine_id

# Mirrors alembic/versions/1913fabf3a6b's seed data (the same routing matrix
# that used to be the hardcoded ROUTING/TEAMS dicts) - Base.metadata.create_all
# only builds schema, not seed rows, so tests need their own copy of this.
_SEED_TEAMS = [
    ("SERVICE", "Service Team"), ("QUALITY", "Quality / Application"),
    ("APPLICATION", "Application Team"), ("TECHNICAL", "Technical Team"),
    ("NETWORK", "Network Team"), ("FIELD_OPS", "Field Operations Team"),
    ("FLEET", "Fleet Team"), ("CC_MANAGER", "CC Manager / Technical Team"),
]
_SEED_TICKET_TYPES = [
    ("INCIDENT", "Incident", False),
    ("SERVICE_REQUEST", "Service Request", False),
    ("CHANGE_REQUEST", "Change Request", True),
]
# Mirrors alembic/versions/c7e9a1b3d5f7's seed data.
_SEED_PRIORITIES = [
    ("P1", "Critical", "Critical - MMU unable to operate / major service interruption", 1, 1),
    ("P2", "High", "High - major equipment/application/network issue affecting operations", 2, 2),
    ("P3", "Medium", "Medium - issue with workaround available", 3, 3),
    ("P4", "Low", "Low - non-critical request / information issue", 4, 4),
]
_SEED_PRIORITY_MATRIX = [
    ("HIGH", "HIGH", "P1"), ("HIGH", "MEDIUM", "P2"), ("HIGH", "LOW", "P2"),
    ("MEDIUM", "HIGH", "P2"), ("MEDIUM", "MEDIUM", "P3"), ("MEDIUM", "LOW", "P3"),
    ("LOW", "HIGH", "P3"), ("LOW", "MEDIUM", "P4"), ("LOW", "LOW", "P4"),
]
_SEED_CATEGORIES = [
    ("MACHINE", "Machine / Instrument Breakdown", "SERVICE", "Service Engineer"),
    ("QC", "QC Failure / Quality Issue", "QUALITY", "Quality Person / Application Person"),
    ("APPLICATION", "Application / Software Issue", "APPLICATION", "Application Person"),
    ("TECHNICAL", "General Technical Issue", "TECHNICAL", "Technical Team (5 members)"),
    ("LIS", "LIS Connection / Data Transfer", "NETWORK", "Network Team (4 members)"),
    ("NETWORK", "Network / Connectivity Issue", "NETWORK", "Network Team (4 members)"),
    ("FIELD", "Field Operational Issue", "FIELD_OPS", "Field Operations Team"),
    ("FLEET", "Fleet / Vehicle Issue", "FLEET", "Fleet Team"),
    ("OTHER", "Other / Unclear Issue", "CC_MANAGER", "CC Manager / Technical Team"),
]


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    db = SessionLocal()
    for role in ROLES:
        db.add(User(username=role.lower(), name=role.title().replace("_", " "), role=role,
                     pw=hash_pw("testpass123"), active=True))
    for code, label, requires_approval in _SEED_TICKET_TYPES:
        db.add(TicketType(code=code, label=label, requires_approval=requires_approval, is_active=True))
    for code, label, description, severity, display_order in _SEED_PRIORITIES:
        db.add(Priority(code=code, label=label, description=description, severity=severity,
                         display_order=display_order, is_active=True))
    for impact_code, urgency_code, priority_code in _SEED_PRIORITY_MATRIX:
        db.add(PriorityMatrix(impact_code=impact_code, urgency_code=urgency_code, priority_code=priority_code))
    for code, name in _SEED_TEAMS:
        db.add(Team(code=code, name=name, is_active=True))
    for code, label, team_code, owner in _SEED_CATEGORIES:
        db.add(Category(code=code, label=label, team_code=team_code, default_owner=owner, is_active=True))

    # LT self-service: dedicated CDA team + district/mandal/zone routed to it,
    # a category flagged visible_to_lt + route_by_zone, its reasons, a
    # machine, a vehicle, and the LT user whose profile auto-fills all of it.
    db.add(Team(code=LT_CDA_TEAM, name="CDA Test Team", is_active=True))
    db.add(Category(code=LT_CATEGORY, label="Field Machine Issue", team_code="SERVICE",
                     default_owner="Service Engineer", is_active=True, route_by_zone=True, visible_to_lt=True))
    # A second LT-visible category with no reasons of its own, purely so tests
    # can confirm a reason tagged to LT_CATEGORY is rejected here.
    db.add(Category(code="LT_OTHER", label="Other Field Issue", team_code="SERVICE",
                     default_owner="Service Engineer", is_active=True, visible_to_lt=True))
    db.commit()

    district = District(name="LT Test District", is_active=True)
    db.add(district)
    db.commit()
    db.refresh(district)

    zone = Zone(name="LT Test Zone", team_code=LT_CDA_TEAM, is_active=True)
    db.add(zone)
    db.commit()
    db.refresh(zone)

    mandal = Mandal(name="LT Test Mandal", district_id=district.id, zone_id=zone.id, is_active=True)
    db.add(mandal)
    db.commit()
    db.refresh(mandal)

    vehicle = Vehicle(registration_no="LT-TEST-01", last_mandal_id=mandal.id, is_active=True)
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)

    machine = Machine(name="Analyzer Test-100", is_active=True)
    db.add(machine)
    db.commit()
    db.refresh(machine)

    for code, label in [("NO_POWER", "No power / won't switch on"), ("CALIBRATION", "Calibration failure")]:
        db.add(Reason(code=code, category_code=LT_CATEGORY, label=label, is_active=True))
    db.add(User(username=LT_USERNAME, name="Lab Technician One", role="LT",
                pw=hash_pw("testpass123"), active=True,
                vehicle_id=vehicle.id, district_id=district.id, mandal_id=mandal.id))
    db.add(User(username=LT_CDA_TEAM.lower(), name="CDA Test Staff", role=LT_CDA_TEAM,
                pw=hash_pw("testpass123"), active=True))
    db.commit()

    lt_ids.update(district_id=district.id, mandal_id=mandal.id, zone_id=zone.id,
                   vehicle_id=vehicle.id, machine_id=machine.id)
    db.close()
    yield


@pytest.fixture(autouse=True)
def _clean_tickets():
    """Every test starts with an empty ticket/event/notification set; seeded users persist."""
    db = SessionLocal()
    db.query(Notification).delete()
    db.query(Event).delete()
    db.query(Ticket).delete()
    db.commit()
    db.close()
    yield


@pytest.fixture(scope="session")
def client():
    from starlette.testclient import TestClient
    import main
    with TestClient(main.app) as c:
        yield c


def auth_headers(role, username=None):
    tok = mktoken({"uid": 1, "username": username or role.lower(), "name": role.title(), "role": role})
    return {"Authorization": "Bearer " + tok}
