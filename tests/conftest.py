"""Test fixtures. Runs against a dedicated `ccc_test` MySQL schema on the same
server as local dev - never the `ccc` database itself. Env vars must be set
before any `app.*` module is imported, since app.core.config builds the DB URL
at import time."""
import os
import pymysql
import pytest

os.environ.setdefault("CCC_SECRET", "test-secret-for-pytest-only-do-not-use-elsewhere")
os.environ["CCC_DB_NAME"] = "ccc_test"

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
from app.models import User, Ticket, Event, Notification  # noqa: E402
from app.core.security import hash_pw, mktoken  # noqa: E402

ROLES = ["CC_MANAGER", "CALL_TAKER", "SERVICE", "APPLICATION", "QUALITY", "TECHNICAL", "NETWORK", "FIELD_OPS", "FLEET"]


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    db = SessionLocal()
    for role in ROLES:
        db.add(User(username=role.lower(), name=role.title().replace("_", " "), role=role,
                     pw=hash_pw("testpass123"), active=True))
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
