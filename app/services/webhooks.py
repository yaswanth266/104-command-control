"""Outbound webhook notifications: push CCC's own ticket lifecycle events -
in CCC's own category/priority master-data terms, not whatever terminology an
external caller used on /intake - to an external EHR/vendor/alerting system
via signed HTTP POST.

Delivery is fire-and-forget from a background thread pool so a slow,
unreachable, or erroring receiver can never block or fail the operator's
action that triggered it (see dispatch_webhook_event). Every outbound request
carries X-CCC-Event (the event name) and X-CCC-Signature (HMAC-SHA256 over
the raw JSON body, hex-encoded, prefixed "sha256=") so the receiver can verify
the payload actually came from this CCC instance.
"""
import datetime
import hashlib
import hmac
import json
import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import (
    CCC_OUTBOUND_WEBHOOK_URL, CCC_OUTBOUND_WEBHOOK_SECRET,
    CCC_OUTBOUND_WEBHOOK_ENABLED, CCC_OUTBOUND_WEBHOOK_TIMEOUT_SECONDS,
)
from app.db.database import SessionLocal
from app.models.config import Config

logger = logging.getLogger("ccc.webhooks")

# The full event catalog an admin can subscribe/unsubscribe from - ticket
# lifecycle events plus master-data events (category/priority CRUD), so an
# external system can keep its own copy of CCC's classification in sync
# instead of drifting out of step with it. "webhook.ping" (used by the admin
# test-connectivity action) deliberately isn't in here - it's not a ticket or
# master-data event and isn't gated by the enabled-events list, so a ping can
# be used to test a not-yet-fully-enabled configuration.
WEBHOOK_EVENTS = [
    "ticket.created",
    "ticket.assigned",
    "ticket.status_changed",
    "ticket.escalated",
    "ticket.note_added",
    "category.created",
    "category.updated",
    "priority.updated",
]

_CONFIG_KEY = "webhook"
_DEFAULT_CONFIG = {
    "url": None,
    "secret": None,
    "enabled": False,
    "events": list(WEBHOOK_EVENTS),
    "timeout_seconds": CCC_OUTBOUND_WEBHOOK_TIMEOUT_SECONDS,
}

_MAX_ATTEMPTS = 3
_RETRY_BACKOFF_SECONDS = [1, 3]  # between attempts 1->2 and 2->3

# Dedicated pool so webhook delivery (incl. retry backoff sleeps) never
# competes with, or blocks on, request-handling threads. Small - this is a
# low-volume integration point, not a bulk fan-out system.
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ccc-webhook")


# ---------- configuration (DB-backed, ccc_config key 'webhook'; env vars are
# only the fallback for whatever an admin hasn't explicitly set) ----------

def get_webhook_config(db: Session) -> dict:
    cfg = dict(_DEFAULT_CONFIG)
    row = db.query(Config).filter(Config.k == _CONFIG_KEY).first()
    if row:
        try:
            cfg.update(json.loads(row.v))
        except Exception:
            logger.exception("Corrupt webhook config in ccc_config - falling back to defaults")
    if not cfg.get("url"):
        cfg["url"] = CCC_OUTBOUND_WEBHOOK_URL
    if not cfg.get("secret"):
        cfg["secret"] = CCC_OUTBOUND_WEBHOOK_SECRET
    # Only defer to the env-var enabled flag before an admin has ever saved a
    # row here - once they have, their explicit choice (including turning it
    # back off) always wins.
    if row is None and CCC_OUTBOUND_WEBHOOK_ENABLED:
        cfg["enabled"] = True
    return cfg


def update_webhook_config(db: Session, patch: dict) -> dict:
    cfg = get_webhook_config(db)
    if "url" in patch:
        url = (patch["url"] or "").strip() or None
        if url and not (url.startswith("http://") or url.startswith("https://")):
            raise HTTPException(400, "Webhook URL must start with http:// or https://")
        cfg["url"] = url
    if "secret" in patch:
        cfg["secret"] = (patch["secret"] or "").strip() or None
    if "events" in patch:
        events = patch["events"]
        if not isinstance(events, list) or not events:
            raise HTTPException(400, "'events' must be a non-empty list")
        unknown = [e for e in events if e not in WEBHOOK_EVENTS]
        if unknown:
            raise HTTPException(400, f"Unknown event(s) {unknown} - must be one of {WEBHOOK_EVENTS}")
        cfg["events"] = events
    if "timeout_seconds" in patch:
        try:
            t = float(patch["timeout_seconds"])
        except (TypeError, ValueError):
            raise HTTPException(400, "'timeout_seconds' must be a number")
        if not (0 < t <= 30):
            raise HTTPException(400, "'timeout_seconds' must be between 0 and 30")
        cfg["timeout_seconds"] = t
    if "enabled" in patch:
        cfg["enabled"] = bool(patch["enabled"])
    if cfg["enabled"] and not cfg.get("url"):
        raise HTTPException(400, "Cannot enable outbound webhooks without a target URL")

    row = db.query(Config).filter(Config.k == _CONFIG_KEY).first()
    if row:
        row.v = json.dumps(cfg)
    else:
        db.add(Config(k=_CONFIG_KEY, v=json.dumps(cfg)))
    db.commit()
    return cfg


# ---------- signing ----------

def sign_payload(secret: str, payload_bytes: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()


def verify_signature(secret: str, payload_bytes: bytes, signature_header: str) -> bool:
    """What an external receiver does on their end - kept here too so it's
    exercised by our own tests and so callers/tests have one source of truth
    for the header format instead of re-deriving it."""
    if not signature_header:
        return False
    expected = sign_payload(secret, payload_bytes)
    return hmac.compare_digest(expected, signature_header)


def build_envelope(event: str, data: dict) -> dict:
    return {
        "event": event,
        "delivery_id": str(uuid.uuid4()),
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "data": data,
    }


# ---------- delivery ----------

def _post_once(url: str, headers: dict, payload_bytes: bytes, timeout: float) -> httpx.Response:
    with httpx.Client(timeout=timeout) as client:
        return client.post(url, content=payload_bytes, headers=headers)


def _send(url: str, secret: Optional[str], timeout: float, event: str, envelope: dict):
    """Runs on a background thread pool worker - retries are fine to block
    here, they never touch the request that triggered the dispatch."""
    payload_bytes = json.dumps(envelope, default=str).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "X-CCC-Event": event,
        "X-CCC-Delivery": envelope["delivery_id"],
    }
    if secret:
        headers["X-CCC-Signature"] = sign_payload(secret, payload_bytes)

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            resp = _post_once(url, headers, payload_bytes, timeout)
            if resp.status_code < 300:
                logger.info("Webhook %s delivered to %s (delivery_id=%s, status=%s)",
                            event, url, envelope["delivery_id"], resp.status_code)
                return
            logger.warning("Webhook %s to %s returned %s (attempt %d/%d, delivery_id=%s)",
                            event, url, resp.status_code, attempt, _MAX_ATTEMPTS, envelope["delivery_id"])
        except httpx.HTTPError as exc:
            logger.warning("Webhook %s to %s failed (attempt %d/%d, delivery_id=%s): %s",
                            event, url, attempt, _MAX_ATTEMPTS, envelope["delivery_id"], exc)
        if attempt < _MAX_ATTEMPTS:
            time.sleep(_RETRY_BACKOFF_SECONDS[attempt - 1])
    logger.error("Webhook %s to %s permanently failed after %d attempts (delivery_id=%s)",
                 event, url, _MAX_ATTEMPTS, envelope["delivery_id"])


def dispatch_webhook_event(event: str, data: dict, db: Optional[Session] = None):
    """Fire-and-forget: looks up config, then hands the actual HTTP call off
    to a background thread and returns immediately. Never raises - a webhook
    problem (bad config, unreachable host, DB hiccup looking up config) must
    never surface as a failure of the ticket action that triggered it."""
    if event not in WEBHOOK_EVENTS:
        logger.error("Refusing to dispatch unknown webhook event '%s'", event)
        return
    try:
        owns_db = db is None
        db = db or SessionLocal()
        try:
            cfg = get_webhook_config(db)
        finally:
            if owns_db:
                db.close()
    except Exception:
        logger.exception("Failed to load webhook config - skipping dispatch of '%s'", event)
        return

    if not cfg.get("enabled") or not cfg.get("url") or event not in (cfg.get("events") or []):
        return

    envelope = build_envelope(event, data)
    try:
        _executor.submit(_send, cfg["url"], cfg.get("secret"),
                          cfg.get("timeout_seconds", CCC_OUTBOUND_WEBHOOK_TIMEOUT_SECONDS), event, envelope)
    except Exception:
        logger.exception("Failed to submit webhook dispatch for '%s'", event)


# ---------- ticket payload (CCC's own master data, not the caller's terms) ----------

def _ticket_payload(db: Session, ticket, actor: str, old_status: Optional[str], extra: Optional[dict]) -> dict:
    from app.crud.crud_category import get_category_map
    from app.crud.crud_team import get_team_map
    from app.crud.crud_priority import get_priority_map

    cat_info = get_category_map(db).get(ticket.category, {})
    team_map = get_team_map(db)
    data = {
        "ticket_id": ticket.id,
        "ticket_no": ticket.ticket_no,
        "status": ticket.status,
        "old_status": old_status,
        # CCC's own master-data codes + human-readable labels - this is what
        # lets the external system consume CCC's classification directly
        # instead of maintaining its own category/priority mapping.
        "category": ticket.category,
        "category_label": cat_info.get("label"),
        "priority": ticket.priority,
        "priority_label": get_priority_map(db).get(ticket.priority),
        "team": ticket.team,
        "team_label": team_map.get(ticket.team, ticket.team),
        "mmu_vehicle": ticket.mmu_vehicle,
        "district": ticket.district,
        "problem": ticket.problem,
        "resolution": ticket.resolution,
        "vip": bool(ticket.vip),
        "due_at": ticket.due_at.isoformat() if ticket.due_at else None,
        "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
        "actor": actor,
    }
    if extra:
        data.update(extra)
    return data


def dispatch_ticket_event(db: Session, event: str, ticket, actor: str,
                           old_status: Optional[str] = None, **extra):
    """Convenience wrapper used by ticket_service/tickets/intake/sla_sweep -
    builds the standard ticket payload (CCC's own category/priority master
    data) and dispatches it."""
    data = _ticket_payload(db, ticket, actor, old_status, extra)
    dispatch_webhook_event(event, data, db=db)


# ---------- master-data payloads (category/priority CRUD) ----------
#
# So a subscribed external system can keep its own copy of CCC's
# classification (the same category/priority master data ticket events carry)
# in sync as an admin adds/edits it here, rather than only finding out about
# a code the next time a ticket happens to use it.

def dispatch_category_event(db: Session, event: str, category, actor: str):
    data = {
        "code": category.code,
        "label": category.label,
        "team_code": category.team_code,
        "default_owner": category.default_owner,
        "is_active": category.is_active,
        "route_by_zone": category.route_by_zone,
        "visible_to_lt": category.visible_to_lt,
        "actor": actor,
    }
    dispatch_webhook_event(event, data, db=db)


def dispatch_priority_event(db: Session, priority_code: str, tat_minutes: int, actor: str):
    from app.crud.crud_priority import get_priority_map
    data = {
        "priority": priority_code,
        "priority_label": get_priority_map(db).get(priority_code),
        "tat_minutes": tat_minutes,
        "actor": actor,
    }
    dispatch_webhook_event("priority.updated", data, db=db)


# ---------- admin "test connectivity" ping ----------

def send_test_ping(db: Session) -> dict:
    """Synchronous (bounded by timeout_seconds) since this is an explicit
    admin action wanting an immediate connectivity result - unlike ticket
    events, which are always fire-and-forget."""
    cfg = get_webhook_config(db)
    if not cfg.get("url"):
        raise HTTPException(400, "No webhook URL configured - set one first")

    envelope = build_envelope("webhook.ping", {
        "message": "This is a test ping from CCC (104 Central Command Center)",
    })
    payload_bytes = json.dumps(envelope, default=str).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "X-CCC-Event": "webhook.ping",
        "X-CCC-Delivery": envelope["delivery_id"],
    }
    if cfg.get("secret"):
        headers["X-CCC-Signature"] = sign_payload(cfg["secret"], payload_bytes)

    timeout = cfg.get("timeout_seconds", CCC_OUTBOUND_WEBHOOK_TIMEOUT_SECONDS)
    started = time.monotonic()
    try:
        resp = _post_once(cfg["url"], headers, payload_bytes, timeout)
        return {"ok": resp.status_code < 300, "status_code": resp.status_code,
                "elapsed_ms": round((time.monotonic() - started) * 1000),
                "delivery_id": envelope["delivery_id"]}
    except httpx.HTTPError as exc:
        return {"ok": False, "error": str(exc),
                "elapsed_ms": round((time.monotonic() - started) * 1000),
                "delivery_id": envelope["delivery_id"]}
