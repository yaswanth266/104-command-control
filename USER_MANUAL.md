# 104 Central Command Center — User Manual

## 1. Overview

CCC is the ticketing and escalation system for 104 Mobile Medical Unit (MMU) support. Calls and field reports become tickets, tickets route to the responsible team, and Service Level Agreements (SLAs) track resolution against configurable targets. An L1–L4 ownership chain tracks who is accountable at each level and auto-escalates as the SLA clock runs down, and a full audit trail records every action.

## 2. Roles

| Role | Access |
|---|---|
| Call Taker | Register calls, view/act on own submissions |
| Team member (SERVICE, QUALITY, APPLICATION, TECHNICAL, NETWORK, FIELD_OPS, FLEET, or any admin-defined team) | Work tickets routed to their team |
| Team Executive (`is_team_manager`) | Everything a team member can do, plus assign tickets to named teammates |
| CC Manager (Global Team Executive) | Full access: any ticket, Admin Portal, reports, dashboard |
| LT (Lab Technician) | Field self-service portal only — report issues, view own history |

## 3. Application Flow (End to End)

This is the full journey a ticket takes, from the moment a vehicle or caller is selected to final closure. Each stage is expanded in its own section later in this manual.

```
Vehicle selected (Register Call)
        |
        v
Auto-fetch from cache/API: Segment Number, District, Mandal,
Secretariat, Village                         (S5.13, S7)
        |
        v
Employee/caller selected
        |
        v
Auto-fetch: Employee Code, Designation        (S5.13, S7)
        |
        v
Category selected  ---->  Sub-Category selected (scoped to Category)
        |                                     (S5.2, S5.3)
        v
Priority determined: picked directly, or derived from
Impact x Urgency matrix; VIP keyword/flag forces P1     (S10)
        |
        v
Resolution (and Response) SLA resolved: most specific of
Sub-Category > Category > Ticket Type > baseline, under
its Business Calendar                          (S5.9, S5.10, S11)
        |
        v
Ticket created (status ASSIGNED) and persisted FIRST -
routing/hierarchy below can never block ticket creation (BR-013)
        |
        v
Department/Team routing resolved: most specific active
Routing Rule (Category+Sub-Category+District/Zone) wins;
falls back to Zone-routing, then the Category's own default team
                                                (S5.11, S12)
        |
        v
L1-L4 hierarchy chain resolved for that SAME matched rule -
each level independently: named user > API role (OE/DM/RM/SPH,
resolved via the caller's synced hierarchy) > local team >
default ladder                                 (S5.11, S12)
        |
        v
Team member acknowledges -> works the ticket -> resolves
                                                (S9)
        |
        v
SLA clock runs (business-calendar-aware, pauses while PENDING)
        |
        v
30% of SLA  -> L1's occupant notified, current_level -> L1
50% of SLA  -> L2's occupant notified, current_level -> L2
70% of SLA  -> L3's occupant notified, current_level -> L3
90% of SLA  -> L4's occupant notified, current_level -> L4
100% (breach) -> CC Manager notified, ticket marked escalated
                                                (S11)
        |
        v
Resolve -> MMU/LT confirms -> Close
(Not Resolved / Reopen loop back into the work queue)  (S9)
```

Two things stay true throughout: **a ticket is never blocked** by a routing, hierarchy, lookup, or sync problem — every one of those degrades gracefully and logs the gap (an Assignment Exception, a notification, or both) rather than failing ticket creation; and **every classification a ticket carries (team, priority, SLA policy, hierarchy chain) is decided once, together, from the same match** — not re-derived piecemeal by different parts of the system.

## 4. Getting Started

1. Go to the CCC URL and sign in with your username/password.
2. Forgot password: click **Forgot password?**, verify your registered mobile number, set a new password.
3. Your role determines which sections appear in the left navigation.

## 5. Master Data & Admin Configuration

Everything in this section lives under **Admin Portal** (CC Manager only). Master data drives the rest of the app — get these right first, in roughly this order, since later ones reference earlier ones (a Category references a Team; a Routing Rule references a Category, Sub-Category, District/Zone, and Teams/Users).

### 5.1 Teams

The department queues tickets route to (`SERVICE`, `HELPDESK`, `DEVELOPMENT`, ... — any code you define). `CC_MANAGER` is a permanent team and cannot be deactivated (it's the fallback route and the admin role).

- **Configure**: Admin → Teams → add a code + display name.
- **Used by**: Categories (default team), Zones (zone-routed team), Routing Rules (`lN_team_code`), Users (`role` = the team they belong to).
- Deactivating a team is blocked while any active Category still points to it.

### 5.2 Categories

The top-level issue classification (e.g. "Login & Access", "Laboratory / LIS"). Each Category has a **default team**, an optional **zone-routing** flag, an LT-visibility flag, and a Ticket Type (Incident / Service Request / Change Request).

- **Configure**: Admin → Categories → code, label, default team, `route_by_zone`, `visible_to_lt`, ticket type.
- **Used by**: ticket creation (the category the caller/LT picks), routing (the fallback team when no Routing Rule and no zone match applies), SLA Policies and Routing Rules (both can scope to a category).
- `route_by_zone`: when on, and the ticket's Mandal maps to an active Zone, that Zone's team is used instead of the category's own default team — see §5.4 and §12.

### 5.3 Sub-Categories

Finer-grained reasons under a Category (e.g. "Login Failure" under "Login & Access"). A Sub-Category cannot be moved to a different Category once created.

- **Configure**: Admin → Sub-Categories → code, parent category, label.
- **Used by**: ticket creation (optional, filtered to the chosen Category), SLA Policies (most specific scope), Routing Rules (most specific scope) — **this is the level the client's escalation matrix spreadsheet is keyed at**: each row (Category + Sub-Category) can carry its own Priority, Resolution SLA, and independent L1–L4 chain.

### 5.4 Geography — Districts, Zones, Mandals

The location hierarchy: **District** → **Mandal** → (optionally) **Zone**. A Zone carries a `team_code` (used only by zone-routed Categories, §5.2). District is independent of Zone and is always available once set on a ticket.

- **Configure**: Admin → Geography → add Districts, then Zones (each with a team), then Mandals (each pinned to one District and, optionally, one Zone).
- **Used by**: Routing Rules (District and/or Zone scoping), the dashboard's per-district breakdown, the Local Team Lead feature (§5.15).
- Deactivating a District/Zone is blocked while active Mandals still reference it.

### 5.5 Vehicles

The local MMU/ambulance registry (`registration_no`, an optional `last_mandal_id` hint). This is a separate, authoritative table from the **synced vehicle roster cache** (§5.13) — the registry is what the Register Call vehicle typeahead searches; the roster cache is what supplies Segment/Secretariat/Village once a vehicle is picked.

- **Configure**: Admin → Vehicles → add a registration number (or let one accumulate from tickets raised against it).
- **Used by**: Register Call's vehicle typeahead, the LT profile's home vehicle.

### 5.6 Ticket Types

`INCIDENT`, `SERVICE_REQUEST`, `CHANGE_REQUEST` (Change Request carries an approval flag). Mostly fixed; rarely needs editing.

### 5.7 Machines

The equipment master backing the LT portal's machine picker and Register Call's equipment field.

### 5.8 Priorities & Impact×Urgency Matrix

P1–P4 (label, description, severity, display order), plus a grid mapping Impact × Urgency (High/Medium/Low each) to a suggested Priority.

- **Configure**: Admin → Priorities & Matrix.
- **Used by**: Register Call (pick Priority directly, or set Impact+Urgency for a suggestion you can still override), SLA Policies (priority is part of every SLA scope), VIP detection (a caller-flagged or keyword-matched VIP always forces P1 regardless of the matrix).

### 5.9 SLA Policies

Resolution and Response SLA targets (in minutes), scoped to any combination of Priority (required) + Sub-Category / Category / Ticket Type (optional), each pointing at a Business Calendar.

- **Configure**: Admin → SLA Policies → code, priority, resolution/response minutes, calendar, and the scope (leave Sub-Category/Category/Ticket Type blank for a broader rule).
- **Resolution precedence** when a ticket is created: **Sub-Category → Category → Ticket Type → the priority's baseline** (the most specific active row wins). This is exactly the "Resolution SLA" column in a Category/Sub-Category matrix like the client's spreadsheet — one SLA Policy row per (Sub-Category, Priority).
- **Used by**: `due_at`/`response_due_at` computed at creation (and on repriority), the SLA pill (ON TRACK/AT RISK/CRITICAL/BREACHED), and the L1–L4 auto-escalation ladder (§11), which measures percent-of-this-SLA-consumed.

### 5.10 Business Calendars

`DEFAULT-24X7` (seeded, wall-clock) or a custom calendar with per-day working windows (`mon`..`sun`, `["09:00","18:00"]` or `null` for a non-working day) plus holidays.

- **Configure**: Admin → Business Calendars → create a calendar, set working hours per day, add holidays.
- **Used by**: every SLA Policy references one calendar. `due_at` is computed by walking forward only through that calendar's working minutes (skipping closed hours and holidays) — a ticket raised at 17:00 on a 9–18 calendar with a 4-hour SLA is due mid-morning the *next working day*, not at 21:00 that night. The L1–L4 escalation ladder (§11) uses the same calendar-aware math to decide percent-consumed.

### 5.11 Routing Rules (L1–L4 local mapping)

The heart of department routing and the escalation chain. Each rule scopes to a **Category**, optionally narrowed by **Sub-Category**, **District**, and/or **Zone**, and sets each of L1–L4's occupant.

**Precedence — the most specific active rule wins:**

```
Category + Sub-Category + District   (most specific)
Category + Sub-Category + Zone
Category + Sub-Category
Category + District
Category + Zone
Category only                        (the floor)
```

A rule is only *eligible* to match a ticket if every narrowing field it declares actually matches that ticket (a District-scoped rule for District A never applies to a ticket in District B); among eligible rules, the one declaring the most fields wins. This is what lets the client's spreadsheet be entered literally: "Role Mapping" (Category: User & Employee Management) can carry a completely different L1–L4 chain than its sibling Sub-Categories in the same Category, because the Sub-Category-scoped rule for it beats whatever the Category-level rule (or another Sub-Category's rule) says.

**Each level (L1–L4) resolves independently, in this order:**

1. **A named local username** (`lN_username`) — a specific person.
2. **An API organizational role** (`lN_role`, e.g. `OE`, `DM`, `RM`, `SPH`) — resolved against the ticket's caller via the synced hierarchy cache (§5.13): "who is this caller's OE/DM/...". If that role holder has no local CCC account, they're still recorded **by name** and an Assignment Exception (`UNMAPPED_ROLE_OCCUPANT`) is raised so an admin can create their account or fix the mapping — the ticket is never blocked.
3. **A local team/department** (`lN_team_code`, e.g. `HELPDESK`, `DEVELOPMENT`, `PM_IT`, `LIS_SUPPORT`) — the whole team is the occupant, no individual named.
4. **The default ladder**, when a level has no username/role/team set at all: **L1** = the ticket's routed team; **L2** = that team's manager (or the district's Local Team Lead, §5.15, if enabled); **L3** = L2's own reporting manager; **L4** = the Global Team Executive (CC_MANAGER).

`l1_team_code` additionally drives the ticket's actual routing (which department's queue it lands in) — L1's team and the ticket's `team` field are always the same, resolved together from one rule match, never independently.

**Example — the client's two configs, entered directly as two rules:**

| | Category | Sub-Category | L1 | L2 | L3 | L4 |
|---|---|---|---|---|---|---|
| Rule A | Login & Access | Login Failure | `role: OE` | `role: DM` | `team: HELPDESK` | `team: DEVELOPMENT` |
| Rule B | Laboratory / LIS | Result Not Received | `team: HELPDESK` | `team: LIS_SUPPORT` | `team: DEVELOPMENT` | `team: PM_IT` |

- **Configure**: Admin → Routing Rules → Code, Category, optional Sub-Category/District/Zone, then per level pick **one** of Local username / API role / Team.
- Identity/scope (Category, Sub-Category, District, Zone) can't be changed after a rule is created — deactivate it and create a new one instead.

### 5.12 Hierarchy Source (Local vs External API)

Where a ticket's L1–L4 chain comes from, independent of Routing Rules' role mapping:

- **Local Mapping** (default) — uses Routing Rules / the default ladder, no network call.
- **External API** — POSTs the ticket's classification to your hierarchy/HR system and normalizes whatever it returns (either a full per-level mapping, or a flat pool of people assigned L1..L4 in order; entries carrying an organizational role instead of a level are mapped through the matched Routing Rule's `lN_role`, same as Local Mapping). On failure it **automatically falls back to Local Mapping** so a ticket is never blocked, and logs both the attempt (for audit) and an Assignment Exception (for follow-up).
- **Configure**: Admin → Hierarchy Source → Mode, URL, auth header/token, timeout. **Test connection** before relying on it.

### 5.13 Master-Data Sync (vehicle / employee / hierarchy roster cache)

A local cache of three more external endpoints — read-only, refreshed on a timer — so Register Call's lookups and Routing Rules' role resolution don't depend on a live external call per ticket:

| Cache table | Synced from | Backs |
|---|---|---|
| Vehicle roster | `vehicle_roster_url` | Segment/District/Mandal/Secretariat/Village auto-fill after picking a vehicle |
| Employee roster | `employee_roster_url` | Employee search typeahead (Designation/Employee ID auto-fill) |
| Hierarchy roster | `hierarchy_roster_url` | Routing Rules' `lN_role` resolution (§5.11) — "who is this employee's OE/DM/RM/SPH" |

- **Configure**: Admin → Hierarchy Source → **Master-Data Sync** card → the three roster URLs, then **Sync automatically every few minutes** (off by default; interval is `CCC_MASTER_SYNC_SECONDS`, 300s/5 min by default). **Sync now** runs all three jobs immediately regardless of the toggle, for testing.
- The **Sync Status** table on the same screen shows each job's last result, row count, and age — check this first if auto-fill or role mapping looks stale.
- **Lookups are cache-first**: a vehicle/employee lookup checks this cache before ever falling back to the older single-item lookup URLs (Vehicle/Employee Lookup card, still supported independently). A sync that returns an empty or drastically smaller roster than what's cached is **rejected** (logged as an error, existing cache kept) rather than wiping good data from a flaky upstream response.
- These cache tables are entirely separate from the local Vehicle registry (§5.5) and local Users (§5.15) — nothing here can corrupt local master data; an admin still explicitly creates the local account for a role holder they want ticket assignment to resolve to a real person (§5.11 point 2).

### 5.14 Assignment Exceptions

The recovery queue for anything that couldn't fully resolve a ticket's hierarchy — reviewed and marked resolved by an admin. Reasons you'll see:

| Reason | Meaning |
|---|---|
| `API_FAILURE` | External Hierarchy API call failed; fell back to Local Mapping |
| `RESOLUTION_FAILURE` | Unexpected error resolving the chain at all |
| `UNMAPPED_ROLE_OCCUPANT` | A Routing Rule's role (OE/DM/...) resolved to a real, synced person with no local CCC account |
| `NO_OCCUPANT_AT_LEVEL` | An escalation level had neither a user nor a team to notify |

None of these ever block ticket creation or escalation — the ticket keeps moving, and this queue is where the gap gets fixed.

### 5.15 Users

Accounts, roles, team-manager flag, reporting manager, `hr_emp_code` (the join key for role resolution, §5.11), and profile fields (district/mandal/vehicle, for LT accounts).

- **Local Team Lead routing** (Admin → SLA & TAT, off by default): once enabled, a Team Executive with a District set on their profile becomes that district's Local Team Lead — new tickets in their district and the L2 default-ladder occupant (§5.11 point 4) prefer them over the statewide Team Executive.

### 5.16 Webhooks

Outbound event integration (ticket lifecycle events, signed HTTP POST) to an external system, using CCC's own category/priority terminology.

### 5.17 SLA & TAT

Legacy per-priority TAT minutes editor (writes the same baseline SLA Policy rows as §5.9), SLA pill thresholds (AT RISK/CRITICAL floors), and the **L1–L4 auto-escalation** percentages — see §11.

### 5.18 Audit Log

Every admin/master-data change, who made it and when — read-only.

## 6. Ticket Queue

- **All Tickets / Open / Closed** quick filters, plus **TAT Breached / At Risk / Critical / Escalated / Unassigned** shortcuts.
- Toolbar filters: search, Status, Priority, Location, Department, Date range, Sort order. Location includes an **Unassigned District** bucket for tickets with no district on record.
- Each row shows: ticket number, Priority pill, VIP/ESC badges, MMU/location, category, team, status, raised time, and the SLA countdown pill (ON TRACK / AT RISK / CRITICAL / BREACHED).
- Click a row to open the ticket detail modal.
- **Export** downloads the current filtered view to Excel.

## 7. Registering a Call

CC Manager and Call Taker only. Open **Register Call** and fill in, by section:

1. **MMU Vehicle & Location** — vehicle (searchable), District, Mandal. Selecting a vehicle auto-fills Segment Number, Secretariat, and Village from the master-data sync cache when populated (§5.13), or a live lookup as a fallback; otherwise enter them manually.
2. **Caller & Reporter Information** — name, phone; flag if the caller is an LT (lets you look up and link to their existing portal ticket instead of duplicating it). An employee search auto-fills Designation and Employee ID the same cache-first way; otherwise type the caller's details directly. The employee's ID (`caller_emp_id`) is also the key the L1–L4 role mapping (§5.11) resolves against.
3. **Equipment & Diagnostic Details** — machine, error code, operational impact (free text).
4. **Problem Statement & SLA Routing**:
   - Issue Category (drives routing preview) and Ticket Type (Incident / Service Request / Change Request).
   - Optional Sub-Category, scoped to the chosen category.
   - **Priority** — pick directly, or set **Impact** + **Urgency** to get a suggested Priority from the configured matrix (you can still override it; overrides are recorded on the ticket).
   - Attach photos/evidence (multiple files supported).

Submitting creates the ticket, computes its Resolution (and, if configured, Response) SLA target from the matching SLA Policy, and resolves its L1–L4 ownership chain from the matching Routing Rule — see §3 and §12 for the full flow.

## 8. LT Field Portal

LT role only, two screens:

- **Report an Issue** — pick a category (only categories flagged LT-visible appear), one or more reasons (sub-categories), machine, priority (P1/P2 only), problem description, photos. Works offline — submissions queue locally and sync when connectivity returns.
- **My Tickets** — your own submission history and status, including a **Not Resolved** action if a "fixed" ticket didn't actually fix the issue, and **Reopen** for a closed ticket within the reopen window.

## 9. Working a Ticket

Open a ticket to see its full detail: classification, SLA dates, hierarchy chain, action buttons, attachments, and audit trail.

### 9.1 Status actions

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
| Any open ticket, non-CC-Manager | Escalate | Requires a reason; notifies the Global Team Executive directly and advances the ticket past its current auto-escalation level so the automatic sweep doesn't re-page a level you already went around |

CC Manager / Call Taker can also **re-route** a ticket to a different team, and change its **Priority** (recomputes the SLA target and TAT from the matching SLA Policy).

### 9.2 Assigning to an engineer

CC Manager (any team) or a Team Executive (their own team) can assign the ticket to a named teammate from the roster dropdown. This updates the ticket's **current hierarchy level's** occupant (not necessarily L1 — an already-escalated ticket handed to someone updates whichever level it's currently sitting at) and is recorded in its assignment history.

### 9.3 Hierarchy (L1–L4) & Assignment History

Shows the current occupant of each level (a named person or a team) and the full history of who has held each level, with source tags:
- `LOCAL` — resolved from Routing Rules / the default team-manager-chain ladder
- `EXTERNAL_API` — resolved from a configured external hierarchy system
- `MANUAL` — set via the Assign action

### 9.4 Attachments & Audit Trail

Upload supporting files at any stage. The audit trail is a permanent, append-only log of every action taken on the ticket, including every automatic escalation with the percent-of-SLA that triggered it.

## 10. Priority, Impact & Urgency

- Priorities (P1–P4) carry a label, description, severity, and display order — configurable in Admin (§5.8).
- The **Impact × Urgency matrix** (Admin → Priorities & Matrix) maps combinations of Impact/Urgency (High/Medium/Low) to a suggested Priority. Register Call uses this live.
- A caller-flagged or keyword-detected VIP situation always forces P1, regardless of the matrix.

## 11. SLA, Business Calendars & Auto-Escalation

- Every ticket gets a **Resolution SLA** (`due_at`) and, where configured, a **Response SLA** (`response_due_at`) from the matching SLA Policy (§5.9) — Sub-Category → Category → Ticket Type → the priority's baseline.
- SLA Policies reference a **Business Calendar** (§5.10): 24×7 (default) counts wall-clock minutes; a business-hours calendar counts only minutes inside its configured working windows, skipping weekends and holidays. `due_at` and the escalation ladder below both use this same calendar-aware math — a ticket is never falsely flagged (or missed) just because it was raised near closing time.
- The queue/ticket SLA pill (ON TRACK / AT RISK / CRITICAL / BREACHED) reflects wall-clock time-to-deadline and is independent of the escalation ladder below.

### 11.1 The L1–L4 auto-escalation ladder

As a ticket consumes its Resolution SLA, it climbs its own L1–L4 chain (§5.11/§12) automatically:

```
 30% of SLA consumed  -> L1's occupant notified, current_level = L1
 50% of SLA consumed  -> L2's occupant notified, current_level = L2
 70% of SLA consumed  -> L3's occupant notified, current_level = L3
 90% of SLA consumed  -> L4's occupant notified, current_level = L4
100% (SLA breached)   -> CC Manager notified, ticket marked escalated
```

- The occupant notified at each level is whoever that ticket's own hierarchy chain resolved to (§9.3) — a named person if one was mapped, otherwise their team.
- Only one level fires per check; an already-notified level is never re-notified for the same crossing. A level with genuinely nobody to notify (no user and no team — only possible via a sparse External API response) is logged as an `NO_OCCUPANT_AT_LEVEL` Assignment Exception and the ticket keeps climbing to the next level in the same pass rather than stalling.
- The four percentages are admin-configurable (Admin → SLA & TAT → **L1–L4 auto-escalation**) and must be strictly ascending; 100%/breach is fixed and not configurable.
- A human using the **Escalate** action (§9.1) advances the ticket past its current level manually, so the automatic sweep won't immediately re-notify a level you already bypassed.

## 12. L1–L4 Hierarchy Resolution — the flow in detail

This is what happens, in order, every time a ticket is created (Register Call, LT Portal, or gov-EHR intake all follow the same path):

```
Category + Sub-Category + District/Mandal(->Zone) known
        |
        v
Match the most specific active Routing Rule
(see the precedence ladder in S5.11)
        |
        v
        +---------------------------+
        |                           |
   rule found                  no rule found
        |                           |
        v                           v
 rule.l1_team_code        Category's route_by_zone?
 overrides routing?                 |
        |                    yes -> Zone's team (if Mandal maps to one)
        v                    no  -> Category's own default team
 ticket.team = that team            |
        |<---------------------------+
        v
For EACH level L1..L4, independently:
  named username set?  -> that person
  role set (OE/DM/..)? -> resolve via synced hierarchy cache against
                           the ticket's caller_emp_id; found but no
                           local account -> record by name + raise
                           an Assignment Exception; not found at all
                           -> fall through
  team set?             -> that team, no individual
  nothing set           -> default ladder (L1=routed team, L2=team
                           manager/Local Team Lead, L3=L2's manager,
                           L4=CC_MANAGER)
        |
        v
Chain recorded (source LOCAL or EXTERNAL_API); ticket.current_level = L1
```

If Hierarchy Source (§5.12) is set to External API, the same rule match is still used for its role-label mapping, but the chain itself comes from the external system's response first, falling back to the Local path above only on failure.

## 13. Notifications

The bell icon shows unread alerts: new tickets, SLA warnings/escalations at each L1–L4 level, TAT breaches, assignments, rejected resolutions. Click to jump to the ticket.

## 14. Dashboard & Reports

CC Manager / Team Executives see KPI tiles (open, breached, at risk, escalated, by status/team/category), filterable by time window (including a custom date range), district, department, and vehicle.

- **Ticket-Wise Trend Analysis** — a daily ticket-volume chart with Week / Month / Custom Date Range views; the custom view shows every day in the chosen range, not just days with activity.
- **Priority breakdown** — a donut chart of open tickets by priority alongside the trend chart.
- **District table** — per-district counts with **View Tickets** (jumps to the Queue filtered to that district) and **Filter Dash** (narrows the whole dashboard to it); includes an Unassigned District row and a search box to filter the table itself.

**Reports** exports ticket-level and summary Excel workbooks, honoring the same date-range and district filters (including Unassigned District).

## 15. Admin Portal — Screen Index

Quick reference; see §5 for what each screen configures and how it's used.

| Screen | Purpose |
|---|---|
| Teams | Team master, active/inactive (§5.1) |
| Categories | Issue categories, routing team, zone-routing toggle, LT visibility, ticket type (§5.2) |
| Geography | Districts, Zones, Mandals (§5.4) |
| Vehicles | MMU/ambulance registry (§5.5) |
| Ticket Types | Incident / Service Request / Change Request, approval flag (§5.6) |
| Sub-Categories | Fault/request reasons under each category (§5.3) |
| Machines | Equipment master for the LT portal picker (§5.7) |
| Priorities & Matrix | Priority master + Impact×Urgency grid (§5.8) |
| SLA Policies | Response/Resolution targets by scope and priority (§5.9) |
| Business Calendars | Working hours + holidays per calendar (§5.10) |
| Routing Rules | L1–L4 local mapping — username/role/team per level, scoped by Category/Sub-Category/District/Zone (§5.11) |
| Hierarchy Source | Local vs External API configuration + test; single-item vehicle/employee lookup URLs; **Master-Data Sync** roster URLs, toggle, and status (§5.12, §5.13) |
| Assignment Exceptions | Hierarchy resolution recovery queue (§5.14) |
| SLA & TAT | Per-priority resolution minutes, SLA pill thresholds, and **L1–L4 auto-escalation** percentages (§5.17, §11.1) |
| Users | User accounts, roles, team-manager flag, reporting manager, profile fields (§5.15) |
| Webhooks | Outbound event integration config + test ping (§5.16) |
| Audit Log | Every admin/master-data change (§5.18) |

## 16. My Profile

Click your name (top right) to view your team, district/mandal/vehicle assignment, reporting manager, and to change your password.
