from sqlalchemy.orm import Session
from sqlalchemy import text
from app.crud.crud_settings import get_sla_config

def build_report_data(db: Session, district: str = "", mmu_vehicle: str = "", team: str = "",
                       date_from: str = "", date_to: str = "") -> dict:
    """Same shape app/api/routers/dashboard.py has always returned (today,
    by_category, by_team, by_priority, by_status, repeat_vehicles, daily,
    kpi), generalized with optional filters - district/mmu_vehicle/team are
    bound SQL parameters (never f-string interpolated, unlike the trusted
    admin-config numbers below) since they're user-supplied. With every
    param left empty/default this produces byte-identical SQL to what the
    dashboard always ran, so GET /dashboard with no query params is
    unchanged. Adds one new breakdown, by_category_mmu (which MMUs raised
    tickets, per category)."""
    sla = get_sla_config(db)
    at_risk_sql = f"due_at<=DATE_ADD(NOW(),INTERVAL GREATEST({sla['at_risk_minutes']}, tat_mins*{sla['at_risk_fraction']}) MINUTE)"
    critical_sql = f"due_at<=DATE_ADD(NOW(),INTERVAL GREATEST({sla['critical_minutes']}, tat_mins*{sla['critical_fraction']}) MINUTE)"

    narrow_clauses = []
    params = {}
    if district:
        narrow_clauses.append("district LIKE :district")
        params["district"] = f"%{district}%"
    if mmu_vehicle:
        narrow_clauses.append("mmu_vehicle LIKE :mmu_vehicle")
        params["mmu_vehicle"] = f"%{mmu_vehicle}%"
    if team:
        narrow_clauses.append("team = :team")
        params["team"] = team
    narrow = (" AND " + " AND ".join(narrow_clauses)) if narrow_clauses else ""

    if date_from or date_to:
        created_conds, closed_conds = [], []
        if date_from:
            created_conds.append("created_at >= :date_from")
            closed_conds.append("closed_at >= :date_from")
            params["date_from"] = date_from
        if date_to:
            created_conds.append("created_at < :date_to_end")
            closed_conds.append("closed_at < :date_to_end")
            params["date_to_end"] = f"{date_to} 23:59:59"
        today_created = " AND ".join(created_conds)
        today_closed = " AND ".join(closed_conds)
    else:
        today_created = "DATE(created_at)=CURDATE()"
        today_closed = "DATE(closed_at)=CURDATE()"

    def q(sql, one=False):
        result = db.execute(text(sql), params)
        if one:
            row = result.fetchone()
            return dict(row._mapping) if row else None
        return [dict(r._mapping) for r in result.fetchall()]

    def o(sql):
        res = q(sql, one=True)
        return res.get("n", 0) if res else 0

    d = {
        "today": {
            "tickets": o(f"SELECT COUNT(*) n FROM ccc_ticket WHERE {today_created}{narrow}"),
            "closed": o(f"SELECT COUNT(*) n FROM ccc_ticket WHERE {today_closed}{narrow}"),
            "open": o(f"SELECT COUNT(*) n FROM ccc_ticket WHERE status<>'CLOSED'{narrow}"),
            "escalated": o(f"SELECT COUNT(*) n FROM ccc_ticket WHERE escalated=1 AND status<>'CLOSED'{narrow}"),
            "breached": o(f"SELECT COUNT(*) n FROM ccc_ticket WHERE status<>'CLOSED' AND due_at<NOW(){narrow}"),
            "critical": o(f"SELECT COUNT(*) n FROM ccc_ticket WHERE status<>'CLOSED' AND due_at>=NOW() AND {critical_sql}{narrow}"),
            "at_risk": o(f"SELECT COUNT(*) n FROM ccc_ticket WHERE status<>'CLOSED' AND due_at>=NOW() AND {at_risk_sql} AND NOT ({critical_sql}){narrow}"),
            "pending": o(f"SELECT COUNT(*) n FROM ccc_ticket WHERE status='PENDING'{narrow}"),
            "awaiting_confirmation": o(f"SELECT COUNT(*) n FROM ccc_ticket WHERE status='RESOLVED'{narrow}"),
            "p1_open": o(f"SELECT COUNT(*) n FROM ccc_ticket WHERE status<>'CLOSED' AND priority='P1'{narrow}"),
            "unassigned": o(f"SELECT COUNT(*) n FROM ccc_ticket WHERE status<>'CLOSED' AND (assignee IS NULL OR assignee=''){narrow}"),
            "escalated_from_field": o(f"SELECT COUNT(*) n FROM ccc_ticket WHERE escalated=1 AND source='LT_PORTAL' AND status<>'CLOSED'{narrow}"),
        },
        "by_category": q(f"SELECT category, COUNT(*) n, SUM(status<>'CLOSED') open_n FROM ccc_ticket WHERE 1=1{narrow} GROUP BY category ORDER BY n DESC"),
        "by_team": q(f"SELECT team, COUNT(*) n, SUM(status<>'CLOSED') open_n, SUM(breached) breach_n, "
                     f"SUM(status<>'CLOSED' AND (assignee IS NULL OR assignee='')) unassigned_n "
                     f"FROM ccc_ticket WHERE 1=1{narrow} GROUP BY team ORDER BY n DESC"),
        "by_priority": q(f"SELECT priority, COUNT(*) n, SUM(status<>'CLOSED') open_n FROM ccc_ticket WHERE 1=1{narrow} GROUP BY priority ORDER BY priority"),
        "by_status": q(f"SELECT status, COUNT(*) n FROM ccc_ticket WHERE 1=1{narrow} GROUP BY status"),
        "by_category_mmu": q(f"SELECT category, mmu_vehicle, COUNT(*) n FROM ccc_ticket WHERE mmu_vehicle IS NOT NULL AND mmu_vehicle<>''{narrow} GROUP BY category, mmu_vehicle ORDER BY category, n DESC"),
        "repeat_vehicles": q(f"SELECT mmu_vehicle, COUNT(*) n FROM ccc_ticket WHERE mmu_vehicle IS NOT NULL AND mmu_vehicle<>''{narrow} GROUP BY mmu_vehicle HAVING n>1 ORDER BY n DESC LIMIT 10"),
        # Chronic equipment watchdog: MMUs/analyzers with >=3 breakdowns in the
        # last 30 days - candidates for warranty replacement / root-cause
        # overhaul rather than another one-off repair ticket.
        "chronic_equipment": q(f"""SELECT mmu_vehicle, district, COUNT(*) n,
                                          SUM(CASE WHEN status<>'CLOSED' THEN 1 ELSE 0 END) open_n,
                                          GROUP_CONCAT(DISTINCT category) categories,
                                          MAX(created_at) last_breakdown_at
                                   FROM ccc_ticket
                                   WHERE mmu_vehicle IS NOT NULL AND mmu_vehicle<>''
                                     AND created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY) {narrow}
                                   GROUP BY mmu_vehicle, district
                                   HAVING n >= 3
                                   ORDER BY n DESC, open_n DESC LIMIT 15"""),
        "daily": q(f"SELECT DATE(created_at) d, COUNT(*) n, SUM(status='CLOSED') closed_n FROM ccc_ticket WHERE 1=1{narrow} GROUP BY d ORDER BY d DESC LIMIT 14"),
    }

    tot = o(f"SELECT COUNT(*) n FROM ccc_ticket WHERE status='CLOSED'{narrow}")
    met = o(f"SELECT COUNT(*) n FROM ccc_ticket WHERE status='CLOSED' AND breached=0{narrow}")
    ack = q(f"SELECT AVG(TIMESTAMPDIFF(MINUTE,created_at,acknowledged_at)) a FROM ccc_ticket WHERE acknowledged_at IS NOT NULL{narrow}", one=True)
    res = q(f"SELECT AVG(TIMESTAMPDIFF(MINUTE,created_at,resolved_at)) a FROM ccc_ticket WHERE resolved_at IS NOT NULL{narrow}", one=True)
    total_tickets = max(1, o(f"SELECT COUNT(*) n FROM ccc_ticket WHERE 1=1{narrow}"))

    d["kpi"] = {
        "closed_total": tot,
        "tat_compliance_pct": round(100.0 * met / tot, 1) if tot else None,
        "tat_breach_pct": round(100.0 * (tot - met) / tot, 1) if tot else None,
        "avg_ack_mins": round(float(ack["a"]), 1) if ack and ack.get("a") is not None else None,
        "avg_resolution_mins": round(float(res["a"]), 1) if res and res.get("a") is not None else None,
        "escalation_pct": round(100.0 * o(f"SELECT COUNT(*) n FROM ccc_ticket WHERE escalated=1{narrow}") / total_tickets, 1),
    }

    for r in d["daily"]:
        if r.get("d"):
            r["d"] = str(r["d"])

    for r in d["chronic_equipment"]:
        if r.get("last_breakdown_at"):
            r["last_breakdown_at"] = str(r["last_breakdown_at"])[:16]

    # Cast decimals to int/float for JSON serialization
    for k in ("by_category", "by_team", "by_priority", "daily", "by_category_mmu", "repeat_vehicles",
              "chronic_equipment", "by_status"):
        for r in d[k]:
            for key, val in r.items():
                if hasattr(val, 'quantize'):  # Decimal
                    r[key] = int(val) if val % 1 == 0 else float(val)

    return d
