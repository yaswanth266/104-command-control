import os

DB_HOST = os.environ.get("CCC_DB_HOST", "127.0.0.1")
DB_USER = os.environ.get("CCC_DB_USER", "root")
DB_PW = os.environ.get("CCC_DB_PW", "")
DB_NAME = os.environ.get("CCC_DB_NAME", "ccc")

SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PW}@{DB_HOST}/{DB_NAME}?charset=utf8mb4"

WEB_DIR = os.environ.get("CCC_WEB", "/opt/ccc/web")

ROUTING = {
    "MACHINE":     {"label": "Machine / Instrument Breakdown", "team": "SERVICE",     "owner": "Service Engineer"},
    "QC":          {"label": "QC Failure / Quality Issue",     "team": "QUALITY",     "owner": "Quality Person / Application Person"},
    "APPLICATION": {"label": "Application / Software Issue",   "team": "APPLICATION", "owner": "Application Person"},
    "TECHNICAL":   {"label": "General Technical Issue",        "team": "TECHNICAL",   "owner": "Technical Team (5 members)"},
    "LIS":         {"label": "LIS Connection / Data Transfer", "team": "NETWORK",     "owner": "Network Team (4 members)"},
    "NETWORK":     {"label": "Network / Connectivity Issue",   "team": "NETWORK",     "owner": "Network Team (4 members)"},
    "FIELD":       {"label": "Field Operational Issue",        "team": "FIELD_OPS",   "owner": "Field Operations Team"},
    "FLEET":       {"label": "Fleet / Vehicle Issue",          "team": "FLEET",       "owner": "Fleet Team"},
    "OTHER":       {"label": "Other / Unclear Issue",          "team": "CC_MANAGER",  "owner": "CC Manager / Technical Team"},
}

TEAMS = {
    "SERVICE": "Service Team", "QUALITY": "Quality / Application", "APPLICATION": "Application Team",
    "TECHNICAL": "Technical Team", "NETWORK": "Network Team", "FIELD_OPS": "Field Operations Team",
    "FLEET": "Fleet Team", "CC_MANAGER": "CC Manager / Technical Team",
}

FLOW = ["NEW", "ASSIGNED", "ACKNOWLEDGED", "IN_PROGRESS", "PENDING", "RESOLVED", "CLOSURE_CONFIRMATION", "CLOSED"]

TAT_DEFAULT = {"P1": 240, "P2": 480, "P3": 1440, "P4": 4320}

PRIORITY = {
    "P1": "Critical - MMU unable to operate / major service interruption",
    "P2": "High - major equipment/application/network issue affecting operations",
    "P3": "Medium - issue with workaround available",
    "P4": "Low - non-critical request / information issue",
}

ROLES = ["CC_MANAGER", "CALL_TAKER", "SERVICE", "APPLICATION", "QUALITY", "TECHNICAL", "NETWORK", "FIELD_OPS", "FLEET"]
