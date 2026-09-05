import os

DB_HOST = os.environ.get("CCC_DB_HOST", "127.0.0.1")
DB_USER = os.environ.get("CCC_DB_USER", "root")
DB_PW = os.environ.get("CCC_DB_PW", "root")
DB_NAME = os.environ.get("CCC_DB_NAME", "ccc")

SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PW}@{DB_HOST}/{DB_NAME}?charset=utf8mb4"

# Dynamically resolve local web directory if CCC_WEB is not set
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WEB_DIR = os.environ.get("CCC_WEB", os.path.join(BASE_DIR, "web"))

# Where LT-uploaded ticket photos are stored - served back out under /uploads
# (see main.py). Local disk is the right call for the current single-server
# systemd+nginx deployment; revisit only if that changes.
UPLOAD_DIR = os.environ.get("CCC_UPLOADS", os.path.join(BASE_DIR, "uploads"))

# Shared secret the field-app/gov-EHR integration must send as X-Intake-Key on
# POST /intake. Required - see app/api/routers/intake.py.
INTAKE_API_KEY = os.environ.get("CCC_INTAKE_KEY")

# How often the SLA sweep (auto-escalation + notifications) runs. Kept as a
# startup-time setting, unlike the actual SLA thresholds (see
# app/crud/crud_settings.py) - changing the sweep cadence doesn't need to be
# live-editable the way the thresholds themselves do.
SLA_SWEEP_SECONDS = int(os.environ.get("CCC_SLA_SWEEP_SECONDS", 60))

# Outbound webhook integration (see app/services/webhooks.py): pushes CCC's
# own ticket lifecycle events - using CCC's own category/priority master data,
# not whatever terminology the external system sent in on /intake - to an
# external EHR/vendor system via signed HTTP POST. These env vars are only the
# fallback target; an admin can instead (or additionally) configure this via
# PUT /cccapi/admin/webhooks/config, which is DB-backed (ccc_config, key
# 'webhook') and takes priority once set.
CCC_OUTBOUND_WEBHOOK_URL = os.environ.get("CCC_OUTBOUND_WEBHOOK_URL")
CCC_OUTBOUND_WEBHOOK_SECRET = os.environ.get("CCC_OUTBOUND_WEBHOOK_SECRET")
CCC_OUTBOUND_WEBHOOK_ENABLED = os.environ.get("CCC_OUTBOUND_WEBHOOK_ENABLED", "false").strip().lower() in ("1", "true", "yes")
CCC_OUTBOUND_WEBHOOK_TIMEOUT_SECONDS = float(os.environ.get("CCC_OUTBOUND_WEBHOOK_TIMEOUT_SECONDS", 5))

# Team/category routing and SLA-tier thresholds are now admin-editable and
# DB-backed (ccc_team, ccc_category, ccc_config's 'sla' key - see
# app/crud/crud_team.py, crud_category.py, crud_settings.py) rather than
# hardcoded here. TAT-per-priority was already DB-backed via ccc_config's
# 'tat' key (crud_ticket.get_tat_map).

FLOW = ["NEW", "ASSIGNED", "ACKNOWLEDGED", "IN_PROGRESS", "PENDING", "RESOLVED", "CLOSURE_CONFIRMATION", "CLOSED"]

TAT_DEFAULT = {"P1": 240, "P2": 480, "P3": 1440, "P4": 4320}

PRIORITY = {
    "P1": "Critical - MMU unable to operate / major service interruption",
    "P2": "High - major equipment/application/network issue affecting operations",
    "P3": "Medium - issue with workaround available",
    "P4": "Low - non-critical request / information issue",
}
