# 104 Central Command Center — User Manual

## 1. Overview

CCC is the ticketing and escalation system for 104 Mobile Medical Unit (MMU) support. Calls and field reports become tickets, tickets route to the responsible team, and Service Level Agreements (SLAs) track resolution against configurable targets. An L1–L4 ownership chain tracks who is accountable at each level, and a full audit trail records every action.

## 2. Roles

| Role | Access |
|---|---|
| Call Taker | Register calls, view/act on own submissions |
| Team member (SERVICE, QUALITY, APPLICATION, TECHNICAL, NETWORK, FIELD_OPS, FLEET, …) | Work tickets routed to their team |
| Team Executive (`is_team_manager`) | Everything a team member can do, plus assign tickets to named teammates |
| CC Manager (Global Team Executive) | Full access: any ticket, Admin Portal, reports, dashboard |
| LT (Lab Technician) | Field self-service portal only — report issues, view own history |

## 3. Getting Started

1. Go to the CCC URL and sign in with your username/password.
2. Forgot password: click **Forgot password?**, verify your registered mobile number, set a new password.
3. Your role determines which sections appear in the left navigation.

## 4. Ticket Queue

- **All Tickets / Open / Closed** quick filters, plus **TAT Breached / At Risk / Critical / Escalated / Unassigned** shortcuts.
- Toolbar filters: search, Status, Priority, Location, Department, Date range, Sort order. Location includes an **Unassigned District** bucket for tickets with no district on record.
- Each row shows: ticket number, Priority pill, VIP/ESC badges, MMU/location, category, team, status, raised time, and the SLA countdown pill (ON TRACK / AT RISK / CRITICAL / BREACHED).
- Click a row to open the ticket detail modal.
- **Export** downloads the current filtered view to Excel.

## 5. Registering a Call

CC Manager and Call Taker only. Open **Register Call** and fill in, by section:

1. **MMU Vehicle & Location** — vehicle (searchable), District, Mandal. Selecting a vehicle also auto-fills Segment Number, Secretariat, and Village when the vehicle lookup is configured (Admin > Hierarchy Source); otherwise enter them manually.
2. **Caller & Reporter Information** — name, phone; flag if the caller is an LT (lets you look up and link to their existing portal ticket instead of duplicating it). An optional employee search auto-fills Designation and Employee ID when the employee lookup is configured; otherwise type the caller's details directly.
3. **Equipment & Diagnostic Details** — machine, error code, operational impact (free text).
4. **Problem Statement & SLA Routing**:
   - Issue Category (drives routing preview) and Ticket Type (Incident / Service Request / Change Request).
   - Optional Sub-Category, scoped to the chosen category.
   - **Priority** — pick directly, or set **Impact** + **Urgency** to get a suggested Priority from the configured matrix (you can still override it; overrides are recorded on the ticket).
   - Attach photos/evidence (multiple files supported).

Submitting creates the ticket, computes its Resolution (and, if configured, Response) SLA target, and resolves its L1–L4 ownership chain.

## 6. LT Field Portal

LT role only, two screens:

- **Report an Issue** — pick a category (only categories flagged LT-visible appear), one or more reasons (sub-categories), machine, priority (P1/P2 only), problem description, photos. Works offline — submissions queue locally and sync when connectivity returns.
- **My Tickets** — your own submission history and status, including a **Not Resolved** action if a "fixed" ticket didn't actually fix the issue, and **Reopen** for a closed ticket within the reopen window.

## 7. Working a Ticket

Open a ticket to see its full detail: classification, SLA dates, hierarchy chain, action buttons, attachments, and audit trail.

### 7.1 Status actions

| From status | Action | Notes |
|---|---|---|
| New / Assigned | Acknowledge | Starts your response clock |
| Acknowledged | Start investigation | |
| In Progress / Pending | Save update | Diagnosis, action taken, root cause, parts — non-terminal |
| Acknowledged / In Progress / Pending | Mark pending | Requires a reason; pauses the SLA clock until resumed |
| Acknowledged / In Progress / Pending | Resolve | Requires resolution notes |
| Resolved | Confirm with MMU | Requires who confirmed it |
| Resolved | Not resolved | Sends it back to In Progress with a reason |
| Closure Confirmation | Close | Final state |
| Closed (within reopen window) | Reopen | Requires a reason |
| Any open ticket, non-CC-Manager | Escalate | Requires a reason; notifies the Global Team Executive |

CC Manager / Call Taker can also **re-route** a ticket to a different team, and change its **Priority** (recomputes the SLA target and TAT).

### 7.2 Assigning to an engineer

CC Manager (any team) or a Team Executive (their own team) can assign the ticket to a named teammate from the roster dropdown. This updates the ticket's current hierarchy level and is recorded in its assignment history.

### 7.3 Hierarchy (L1–L4) & Assignment History

Shows the current occupant of each level (team or named person) and the full history of who has held each level, with source tags:
- `LOCAL` — resolved from routing rules / the default team-manager-chain ladder
- `EXTERNAL_API` — resolved from a configured external hierarchy system
- `MANUAL` — set via the Assign action

### 7.4 Attachments & Audit Trail

Upload supporting files at any stage. The audit trail is a permanent, append-only log of every action taken on the ticket.

## 8. Priority, Impact & Urgency

- Priorities (P1–P4) carry a label, description, severity, and display order — configurable in Admin.
- The **Impact × Urgency matrix** (Admin → Priorities & Matrix) maps combinations of Impact/Urgency (High/Medium/Low) to a suggested Priority. Register Call uses this live.
- A caller-flagged or keyword-detected VIP situation always forces P1, regardless of the matrix.

## 9. SLA & Business Calendars

- Every ticket gets a **Resolution SLA** (`due_at`) and, where configured, a **Response SLA** (`response_due_at`) — measured against whichever SLA Policy matches most specifically: Sub-Category → Category → Ticket Type → the priority's baseline.
- SLA Policies reference a **Business Calendar**: 24×7 (default) counts wall-clock minutes; a business-hours calendar counts only minutes inside its configured working windows, skipping weekends and holidays.
- The queue/ticket SLA pill (ON TRACK / AT RISK / CRITICAL / BREACHED) and automatic escalation notifications (50% → assignee, 80% → team manager, 100% → CC Manager) run off these targets continuously.

## 10. L1–L4 Hierarchy Configuration

- **Routing Rules** (Admin) let you pin explicit L1–L4 usernames (and/or an L1 team override) to a Category, optionally narrowed to one Zone. Unset levels fall back to the default ladder: L1 = routed team, L2 = that team's manager, L3 = L2's reporting manager, L4 = CC Manager.
- **Hierarchy Source** (Admin) switches how new tickets resolve their chain:
  - **Local Mapping** (default) — uses Routing Rules / the default ladder, no network call.
  - **External API** — POSTs the ticket's classification to your configured URL and normalizes the response. On failure it automatically falls back to Local Mapping so no ticket is ever blocked; use **Test connection** to check connectivity first.
  - **Vehicle & Employee Lookup** — the same screen also holds two optional URLs, using the same auth as above: one returns Segment Number/District/Mandal/Secretariat/Village for a vehicle, the other searches employees for Designation/Employee ID. Both back the Register Call auto-fill fields and degrade to manual entry when left blank or unreachable. Each has its own **Test** button.
- **Assignment Exceptions** (Admin) lists tickets where hierarchy resolution had a problem (e.g. the external API was unreachable) — review and mark resolved once addressed.

## 11. Notifications

The bell icon shows unread alerts: new tickets, SLA warnings/breaches, assignments, escalations, rejected resolutions. Click to jump to the ticket.

## 12. Dashboard & Reports

CC Manager / Team Executives see KPI tiles (open, breached, at risk, escalated, by status/team/category), filterable by time window (including a custom date range), district, department, and vehicle.

- **Ticket-Wise Trend Analysis** — a daily ticket-volume chart with Week / Month / Custom Date Range views; the custom view shows every day in the chosen range, not just days with activity.
- **Priority breakdown** — a donut chart of open tickets by priority alongside the trend chart.
- **District table** — per-district counts with **View Tickets** (jumps to the Queue filtered to that district) and **Filter Dash** (narrows the whole dashboard to it); includes an Unassigned District row and a search box to filter the table itself.

**Reports** exports ticket-level and summary Excel workbooks, honoring the same date-range and district filters (including Unassigned District).

## 13. Admin Portal (CC Manager only)

| Screen | Purpose |
|---|---|
| Teams | Team master, active/inactive |
| Categories | Issue categories, routing team, zone-routing toggle, LT visibility, ticket type |
| Geography | Districts, Zones, Mandals |
| Vehicles | MMU/ambulance registry |
| Ticket Types | Incident / Service Request / Change Request, approval flag |
| Sub-Categories | Fault/request reasons under each category |
| Machines | Equipment master for the LT portal picker |
| Priorities & Matrix | Priority master + Impact×Urgency grid |
| SLA Policies | Response/Resolution targets by scope and priority |
| Business Calendars | Working hours + holidays per calendar |
| Routing Rules | L1–L4 local mapping overrides |
| Hierarchy Source | Local vs External API configuration + test; vehicle/employee lookup URLs for Register Call auto-fill |
| Assignment Exceptions | Hierarchy resolution failure queue |
| SLA & TAT | Legacy quick editor for per-priority resolution minutes (writes the same baseline SLA Policy rows) and SLA warning thresholds |
| Users | User accounts, roles, team-manager flag, reporting manager, profile fields |
| Webhooks | Outbound event integration config + test ping |
| Audit Log | Every admin/master-data change |

## 14. My Profile

Click your name (top right) to view your team, district/mandal/vehicle assignment, reporting manager, and to change your password.
