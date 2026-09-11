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
        d_clean = district.strip().lower()
        if d_clean in ("__unassigned__", "unassigned", "unassigned district"):
            narrow_clauses.append("(district IS NULL OR district = '' OR TRIM(district) = '')")
        else:
            narrow_clauses.append("district LIKE :district")
            params["district"] = f"%{district}%"
    if mmu_vehicle:
        narrow_clauses.append("mmu_vehicle LIKE :mmu_vehicle")
        params["mmu_vehicle"] = f"%{mmu_vehicle}%"
    if team:
        narrow_clauses.append("team = :team")
        params["team"] = team
    narrow = (" AND " + " AND ".join(narrow_clauses)) if narrow_clauses else ""

    date_filter = ""
    if date_from or date_to:
        created_conds, closed_conds = [], []
        if date_from:
            d_from_str = f"{date_from} 00:00:00" if len(date_from) == 10 else date_from
            created_conds.append("created_at >= :date_from_start")
            closed_conds.append("closed_at >= :date_from_start")
            params["date_from_start"] = d_from_str
            params["date_from"] = date_from[:10]
        if date_to:
            d_to_str = f"{date_to} 23:59:59" if len(date_to) == 10 else date_to
            created_conds.append("created_at <= :date_to_end")
            closed_conds.append("closed_at <= :date_to_end")
            params["date_to_end"] = d_to_str
            params["date_to"] = date_to[:10]
        today_created = " AND ".join(created_conds)
        today_closed = " AND ".join(closed_conds)
        date_filter = f" AND {today_created}"
        window_active = True
    else:
        today_created = "DATE(created_at)=CURDATE()"
        today_closed = "DATE(closed_at)=CURDATE()"
        window_active = False

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
            "tickets": o(f"SELECT COUNT(*) n FROM ccc_ticket WHERE 1=1{date_filter}{narrow}"),
            "closed": o(f"SELECT COUNT(*) n FROM ccc_ticket WHERE status='CLOSED'{date_filter}{narrow}"),
            "open": o(f"SELECT COUNT(*) n FROM ccc_ticket WHERE status<>'CLOSED'{date_filter}{narrow}"),
            "escalated": o(f"SELECT COUNT(*) n FROM ccc_ticket WHERE escalated=1{date_filter}{narrow}"),
            "breached": o(f"SELECT COUNT(*) n FROM ccc_ticket WHERE (breached=1 OR (status<>'CLOSED' AND due_at<NOW())){date_filter}{narrow}"),
            "critical": o(f"SELECT COUNT(*) n FROM ccc_ticket WHERE status<>'CLOSED' AND due_at>=NOW() AND {critical_sql}{date_filter}{narrow}"),
            "at_risk": o(f"SELECT COUNT(*) n FROM ccc_ticket WHERE status<>'CLOSED' AND due_at>=NOW() AND {at_risk_sql} AND NOT ({critical_sql}){date_filter}{narrow}"),
            "pending": o(f"SELECT COUNT(*) n FROM ccc_ticket WHERE status='PENDING'{date_filter}{narrow}"),
            "awaiting_confirmation": o(f"SELECT COUNT(*) n FROM ccc_ticket WHERE status='RESOLVED'{date_filter}{narrow}"),
            "p1_open": o(f"SELECT COUNT(*) n FROM ccc_ticket WHERE status<>'CLOSED' AND priority='P1'{date_filter}{narrow}"),
            "unassigned": o(f"SELECT COUNT(*) n FROM ccc_ticket WHERE status<>'CLOSED' AND (assignee IS NULL OR assignee=''){date_filter}{narrow}"),
            "escalated_from_field": o(f"SELECT COUNT(*) n FROM ccc_ticket WHERE escalated=1 AND source='LT_PORTAL'{date_filter}{narrow}"),
        },
        "by_category": q(f"SELECT category, COUNT(*) n, SUM(status<>'CLOSED') open_n FROM ccc_ticket WHERE 1=1{date_filter}{narrow} GROUP BY category ORDER BY n DESC"),
        "by_team": q(f"SELECT team, COUNT(*) n, SUM(status<>'CLOSED') open_n, SUM(breached) breach_n, "
                     f"SUM(status<>'CLOSED' AND (assignee IS NULL OR assignee='')) unassigned_n "
                     f"FROM ccc_ticket WHERE 1=1{date_filter}{narrow} GROUP BY team ORDER BY n DESC"),
        "by_priority": q(f"SELECT priority, COUNT(*) n, SUM(status<>'CLOSED') open_n FROM ccc_ticket WHERE 1=1{date_filter}{narrow} GROUP BY priority ORDER BY priority"),
        "by_status": q(f"SELECT status, COUNT(*) n FROM ccc_ticket WHERE 1=1{date_filter}{narrow} GROUP BY status"),
        "by_category_mmu": q(f"SELECT category, mmu_vehicle, COUNT(*) n FROM ccc_ticket WHERE mmu_vehicle IS NOT NULL AND mmu_vehicle<>''{date_filter}{narrow} GROUP BY category, mmu_vehicle ORDER BY category, n DESC"),
        "repeat_vehicles": q(f"SELECT mmu_vehicle, COUNT(*) n FROM ccc_ticket WHERE mmu_vehicle IS NOT NULL AND mmu_vehicle<>''{date_filter}{narrow} GROUP BY mmu_vehicle HAVING n>1 ORDER BY n DESC LIMIT 10"),
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
        "daily": q(f"SELECT DATE(created_at) d, COUNT(*) n, SUM(status='CLOSED') closed_n FROM ccc_ticket WHERE 1=1{date_filter}{narrow} GROUP BY d ORDER BY d DESC LIMIT 14"),
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

    # Section A: 12 Dashboard KPI Cards
    total_tickets_count = o(f"SELECT COUNT(*) n FROM ccc_ticket WHERE 1=1{date_filter}{narrow}")
    new_tickets_count = o(f"SELECT COUNT(*) n FROM ccc_ticket WHERE status IN ('NEW', 'ASSIGNED'){date_filter}{narrow}")
    in_progress_count = o(f"SELECT COUNT(*) n FROM ccc_ticket WHERE status IN ('IN_PROGRESS', 'ACKNOWLEDGED'){date_filter}{narrow}")
    pending_count = o(f"SELECT COUNT(*) n FROM ccc_ticket WHERE status='PENDING'{date_filter}{narrow}")
    resolved_count = o(f"SELECT COUNT(*) n FROM ccc_ticket WHERE status IN ('RESOLVED', 'CLOSURE_CONFIRMATION'){date_filter}{narrow}")
    closed_count = o(f"SELECT COUNT(*) n FROM ccc_ticket WHERE status='CLOSED'{date_filter}{narrow}")
    p1_count = o(f"SELECT COUNT(*) n FROM ccc_ticket WHERE priority='P1'{date_filter}{narrow}")
    p2_count = o(f"SELECT COUNT(*) n FROM ccc_ticket WHERE priority='P2'{date_filter}{narrow}")
    at_risk_count = o(f"SELECT COUNT(*) n FROM ccc_ticket WHERE status<>'CLOSED' AND due_at>=NOW() AND {at_risk_sql}{date_filter}{narrow}")
    breaches_count = o(f"SELECT COUNT(*) n FROM ccc_ticket WHERE (breached=1 OR (status<>'CLOSED' AND due_at<NOW())){date_filter}{narrow}")
    escalated_count = o(f"SELECT COUNT(*) n FROM ccc_ticket WHERE escalated=1{date_filter}{narrow}")
    kpi_tot = o(f"SELECT COUNT(*) n FROM ccc_ticket WHERE status='CLOSED'{date_filter}{narrow}")
    kpi_met = o(f"SELECT COUNT(*) n FROM ccc_ticket WHERE status='CLOSED' AND breached=0{date_filter}{narrow}")
    compliance_pct = round(100.0 * kpi_met / kpi_tot, 1) if kpi_tot > 0 else 100.0

    d["kpi_cards"] = {
        "total_tickets": total_tickets_count,
        "new_tickets": new_tickets_count,
        "in_progress": in_progress_count,
        "pending_tickets": pending_count,
        "resolved_tickets": resolved_count,
        "closed_tickets": closed_count,
        "p1_critical": p1_count,
        "p2_high": p2_count,
        "sla_at_risk": at_risk_count,
        "sla_breaches": breaches_count,
        "escalated_tickets": escalated_count,
        "sla_compliance_pct": compliance_pct,
    }

    # Section B: Ticket-Wise Trend Analysis (Created vs Resolved)
    trend_where_clauses = []
    if date_from:
        trend_where_clauses.append("d_table.d >= :date_from")
    if date_to:
        trend_where_clauses.append("d_table.d <= :date_to")
    trend_where = (" WHERE " + " AND ".join(trend_where_clauses)) if trend_where_clauses else ""

    trend_rows = q(f"""
        SELECT 
            d_table.d,
            COALESCE(c.created_n, 0) as created_count,
            COALESCE(r.resolved_n, 0) as resolved_count
        FROM (
            SELECT DISTINCT DATE(created_at) as d FROM ccc_ticket WHERE created_at IS NOT NULL {narrow}
            UNION
            SELECT DISTINCT DATE(resolved_at) as d FROM ccc_ticket WHERE resolved_at IS NOT NULL {narrow}
            UNION
            SELECT DISTINCT DATE(closed_at) as d FROM ccc_ticket WHERE closed_at IS NOT NULL {narrow}
        ) d_table
        LEFT JOIN (
            SELECT DATE(created_at) as d, COUNT(*) as created_n 
            FROM ccc_ticket WHERE 1=1 {narrow} GROUP BY d
        ) c ON d_table.d = c.d
        LEFT JOIN (
            SELECT DATE(COALESCE(resolved_at, closed_at)) as d, COUNT(*) as resolved_n 
            FROM ccc_ticket WHERE (resolved_at IS NOT NULL OR closed_at IS NOT NULL) {narrow} GROUP BY d
        ) r ON d_table.d = r.d
        {trend_where}
        ORDER BY d_table.d ASC
    """)
    for r in trend_rows:
        if r.get("d"):
            r["d"] = str(r["d"])
        r["created_count"] = int(r.get("created_count") or 0)
        r["resolved_count"] = int(r.get("resolved_count") or 0)
    d["trend"] = trend_rows

    # Section C: Priority Distribution (Donut Chart Data)
    raw_pri = q(f"SELECT priority, COUNT(*) as count FROM ccc_ticket WHERE 1=1{date_filter}{narrow} GROUP BY priority")
    total_pri_count = max(1, sum(int(r.get("count") or 0) for r in raw_pri))
    pri_defs = [
        {"code": "P1", "label": "P1 – Critical", "color": "#DC2626"},
        {"code": "P2", "label": "P2 – High", "color": "#EA580C"},
        {"code": "P3", "label": "P3 – Medium", "color": "#D97706"},
        {"code": "P4", "label": "P4 – Low", "color": "#2563EB"}
    ]
    pri_counts = {r["priority"]: int(r.get("count") or 0) for r in raw_pri}
    priority_distribution = []
    for pdef in pri_defs:
        c = pri_counts.get(pdef["code"], 0)
        pct = round(100.0 * c / total_pri_count, 1)
        priority_distribution.append({
            "code": pdef["code"],
            "label": pdef["label"],
            "color": pdef["color"],
            "count": c,
            "pct": pct
        })
    d["priority_distribution"] = priority_distribution

    # Section D: Ticket Ageing Analysis (Duration Buckets)
    ageing_raw = q(f"""
        SELECT 
            SUM(CASE WHEN TIMESTAMPDIFF(HOUR, created_at, NOW()) < 4 THEN 1 ELSE 0 END) as under_4h,
            SUM(CASE WHEN TIMESTAMPDIFF(HOUR, created_at, NOW()) >= 4 AND TIMESTAMPDIFF(HOUR, created_at, NOW()) < 8 THEN 1 ELSE 0 END) as h_4_8,
            SUM(CASE WHEN TIMESTAMPDIFF(HOUR, created_at, NOW()) >= 8 AND TIMESTAMPDIFF(HOUR, created_at, NOW()) < 24 THEN 1 ELSE 0 END) as h_8_24,
            SUM(CASE WHEN TIMESTAMPDIFF(DAY, created_at, NOW()) >= 1 AND TIMESTAMPDIFF(DAY, created_at, NOW()) < 3 THEN 1 ELSE 0 END) as d_1_3,
            SUM(CASE WHEN TIMESTAMPDIFF(DAY, created_at, NOW()) >= 3 THEN 1 ELSE 0 END) as over_3d
        FROM ccc_ticket
        WHERE status <> 'CLOSED' {date_filter} {narrow}
    """, one=True) or {}

    total_open_ageing = max(1, sum(int(ageing_raw.get(k) or 0) for k in ("under_4h", "h_4_8", "h_8_24", "d_1_3", "over_3d")))
    ticket_ageing = [
        {"bracket": "< 4 Hours", "desc": "Standard Emergency TAT window", "count": int(ageing_raw.get("under_4h") or 0), "color": "#16A34A"},
        {"bracket": "4 – 8 Hours", "desc": "Short duration pending", "count": int(ageing_raw.get("h_4_8") or 0), "color": "#EAB308"},
        {"bracket": "8 – 24 Hours", "desc": "Same day pending", "count": int(ageing_raw.get("h_8_24") or 0), "color": "#F97316"},
        {"bracket": "1 – 3 Days", "desc": "Multi-day delayed", "count": int(ageing_raw.get("d_1_3") or 0), "color": "#EF4444"},
        {"bracket": "> 3 Days", "desc": "Severely aged tickets", "count": int(ageing_raw.get("over_3d") or 0), "color": "#991B1B"}
    ]
    for b in ticket_ageing:
        b["pct"] = round(100.0 * b["count"] / total_open_ageing, 1)
    d["ticket_ageing"] = ticket_ageing

    # Section E: Application / Role-Wise Tickets
    app_raw = q(f"SELECT COALESCE(source, 'CALL') as app_code, COUNT(*) as count FROM ccc_ticket WHERE 1=1 {date_filter} {narrow} GROUP BY app_code ORDER BY count DESC")
    total_app_tickets = max(1, sum(int(r.get("count") or 0) for r in app_raw))
    app_names = {
        "CALL": "104 Inbound Telephony (Intake Portal)",
        "LT_PORTAL": "MMU Mobile Diagnostic Field App"
    }
    by_application = []
    for r in app_raw:
        code = r["app_code"]
        c = int(r["count"])
        by_application.append({
            "code": code,
            "name": app_names.get(code, code),
            "count": c,
            "pct": round(100.0 * c / total_app_tickets, 1)
        })
    d["by_application"] = by_application

    role_date_filter = date_filter.replace("created_at", "t.created_at")
    role_raw = q(f"""
        SELECT COALESCE(u.role, 'UNASSIGNED') as role_code, COUNT(*) as count 
        FROM ccc_ticket t 
        LEFT JOIN ccc_user u ON t.assignee = u.username 
        WHERE 1=1 {role_date_filter} {narrow} 
        GROUP BY role_code 
        ORDER BY count DESC
    """)
    total_role_tickets = max(1, sum(int(r.get("count") or 0) for r in role_raw))
    role_names = {
        "CDA": "Biomedical Engineer (CDA)",
        "SERVICE": "Field Equipment Service Engineer",
        "FLEET": "Fleet Operations Lead",
        "APPLICATION": "Software & Network Support",
        "CALL_TAKER": "104 Call Intake Agent",
        "CC_MANAGER": "Command Center Executive",
        "LT": "Lab Technician (Field)",
        "UNASSIGNED": "Unassigned Support Queue"
    }
    by_role = []
    for r in role_raw:
        rc = r["role_code"]
        c = int(r["count"])
        by_role.append({
            "code": rc,
            "name": role_names.get(rc, rc.replace('_', ' ').title()),
            "count": c,
            "pct": round(100.0 * c / total_role_tickets, 1)
        })
    d["by_role"] = by_role

    # Section F: Category-Wise Tickets (Enhanced with percentage)
    total_cat_tickets = max(1, sum(int(r.get("n") or 0) for r in d["by_category"]))
    for r in d["by_category"]:
        r["pct"] = round(100.0 * int(r.get("n") or 0) / total_cat_tickets, 1)
        r["open_n"] = int(r.get("open_n") or 0)
        r["n"] = int(r.get("n") or 0)

    # Section G: District-Wise Tickets
    dist_raw = q(f"""
        SELECT 
            COALESCE(NULLIF(TRIM(district), ''), 'Unassigned District') as district,
            COUNT(*) as total,
            SUM(CASE WHEN status <> 'CLOSED' THEN 1 ELSE 0 END) as open_n,
            SUM(CASE WHEN status IN ('RESOLVED', 'CLOSURE_CONFIRMATION') THEN 1 ELSE 0 END) as resolved_n,
            SUM(CASE WHEN status = 'PENDING' THEN 1 ELSE 0 END) as pending_n,
            SUM(CASE WHEN breached = 1 OR (status <> 'CLOSED' AND due_at < NOW()) THEN 1 ELSE 0 END) as breach_n
        FROM ccc_ticket
        WHERE 1=1 {date_filter} {narrow}
        GROUP BY COALESCE(NULLIF(TRIM(district), ''), 'Unassigned District')
        ORDER BY total DESC
    """)
    by_district = []
    for r in dist_raw:
        by_district.append({
            "district": r["district"],
            "total": int(r.get("total") or 0),
            "open": int(r.get("open_n") or 0),
            "resolved": int(r.get("resolved_n") or 0),
            "pending": int(r.get("pending_n") or 0),
            "breaches": int(r.get("breach_n") or 0),
        })
    d["by_district"] = by_district

    # Section H: Live Alerts & Recent Activities
    recent_activities = q(f"""
        SELECT 
            e.id, 
            e.ticket_id, 
            t.ticket_no, 
            e.at, 
            e.actor, 
            e.actor_role, 
            e.action, 
            e.detail, 
            t.priority, 
            t.district,
            t.mmu_vehicle,
            t.status as current_status
        FROM ccc_event e
        JOIN ccc_ticket t ON e.ticket_id = t.id
        WHERE 1=1 {narrow}
        ORDER BY e.at DESC, e.id DESC
        LIMIT 30
    """)
    for r in recent_activities:
        if r.get("at"):
            r["at"] = str(r["at"])[:19]
    d["recent_activities"] = recent_activities

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
