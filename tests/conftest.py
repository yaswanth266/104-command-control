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
from app.models import User, Ticket, Event, Notification, Team, Category  # noqa: E402
from app.core.security import hash_pw, mktoken  # noqa: E402

ROLES = ["CC_MANAGER", "CALL_TAKER", "SERVICE", "APPLICATION", "QUALITY", "TECHNICAL", "NETWORK", "FIELD_OPS", "FLEET"]

# Mirrors alembic/versions/1913fabf3a6b's seed data (the same routing matrix
# that used to be the hardcoded ROUTING/TEAMS dicts) - Base.metadata.create_all
# only builds schema, not seed rows, so tests need their own copy of this.
_SEED_TEAMS = [
    ("SERVICE", "Service Team"), ("QUALITY", "Quality / Application"),
    ("APPLICATION", "Application Team"), ("TECHNICAL", "Technical Team"),
    ("NETWORK", "Network Team"), ("FIELD_OPS", "Field Operations Team"),
    ("FLEET", "Fleet Team"), ("CC_MANAGER", "CC Manager / Technical Team"),
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
    for code, name in _SEED_TEAMS:
        db.add(Team(code=code, name=name, is_active=True))
    for code, label, team_code, owner in _SEED_CATEGORIES:
        db.add(Category(code=code, label=label, team_code=team_code, default_owner=owner, is_active=True))
    db.commit()
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
