/* ---------- Admin: Ticket Types master ----------
   New master introduced by the enterprise taxonomy work (see /admin/ticket-types).
   Loaded as its own file to keep this addition out of app.js's diff - wired
   into the existing admin nav/dispatch (app.js: aItems, loadAdminSection,
   viewAdmin) with a few added lines there, following the same table+inline-
   add-form+prompt-edit pattern as viewAdminMachines()/viewAdminTeams(). */
var ADMIN_TICKET_TYPES = [];

function loadAdminTicketTypes() {
  api('GET', '/admin/ticket-types').then(function (d) {
    ADMIN_TICKET_TYPES = d;
    ADMIN_LOADED.tickettypes = true;
    if (ADMIN_TAB === 'tickettypes') render();
  });
}

function viewAdminTicketTypes() {
  var rows = ADMIN_TICKET_TYPES.map(function (t) {
    return '<tr><td><b>' + esc(t.code) + '</b></td><td>' + esc(t.label) + '</td>' +
      '<td>' + (t.requires_approval ? '<span class="pill p-warn">Requires approval</span>' : '<span class="pill p-mut">No approval</span>') + '</td>' +
      '<td>' + (t.is_active ? '<span class="pill p-ok">Active</span>' : '<span class="pill p-mut">Inactive</span>') + '</td>' +
      '<td style="display:flex;gap:6px"><button class="btn o sm" onclick="adminRenameTicketType(\'' + t.code + '\')">Rename</button>' +
      '<button class="btn ' + (t.is_active ? 'r' : 'g') + ' sm" onclick="adminToggleTicketType(\'' + t.code + '\',' + (!t.is_active) + ')">' + (t.is_active ? 'Deactivate' : 'Activate') + '</button></td></tr>';
  }).join('');
  return '<div class="card" style="margin-bottom:14px"><h4 style="margin-bottom:4px;font-size:15px">Ticket Types</h4>' +
    '<div class="muted" style="margin-bottom:10px">Determines which workflow a ticket follows (Incident / Service Request / Change Request) and whether it needs approval before proceeding.</div>' +
    '<div style="overflow-x:auto"><table><thead><tr><th>Code</th><th>Label</th><th>Approval</th><th>Status</th><th></th></tr></thead><tbody>' + rows + '</tbody></table></div></div>' +
    '<div class="card"><h4 style="margin-bottom:10px;font-size:14px">Add ticket type</h4><div class="grid3">' +
    '<div class="fld"><label>Code</label><input id="tt_code" placeholder="PROBLEM"></div>' +
    '<div class="fld"><label>Label</label><input id="tt_label" placeholder="Problem"></div>' +
    '<div class="fld" style="display:flex;align-items:center;gap:8px;margin-top:18px"><input type="checkbox" id="tt_approval" style="width:auto"> <label style="margin:0;text-transform:none;font-size:13px;font-weight:600;color:var(--ink2)">Requires approval</label></div>' +
    '<div class="fld" style="display:flex;align-items:flex-end"><button class="btn" onclick="adminCreateTicketType()">Add ticket type</button></div>' +
    '</div></div>';
}

function adminCreateTicketType() {
  var code = gv('tt_code'), label = gv('tt_label');
  var requiresApproval = document.getElementById('tt_approval').checked;
  if (!code || !label) return toast('Code and label are required');
  api('POST', '/admin/ticket-types', { code: code, label: label, requires_approval: requiresApproval })
    .then(function () { toast('Ticket type added'); loadAdminTicketTypes(); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}
function adminRenameTicketType(code) {
  var t = ADMIN_TICKET_TYPES.find(function (x) { return x.code === code; });
  var label = prompt('New label for ' + code + ':', t ? t.label : ''); if (!label) return;
  api('PUT', '/admin/ticket-types/' + code, { label: label }).then(function () { toast('Renamed'); loadAdminTicketTypes(); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}
function adminToggleTicketType(code, active) {
  api('PUT', '/admin/ticket-types/' + code, { is_active: active }).then(function () { toast(active ? 'Activated' : 'Deactivated'); loadAdminTicketTypes(); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}

/* ---------- Admin: Priority master + Impact x Urgency matrix ----------
   Same wiring approach as Ticket Types above. IMPACT_LEVELS/URGENCY_LEVELS
   are fixed (app/core/config.py), so the matrix is always the same NxM grid -
   only which Priority each cell maps to is admin-editable. */
var ADMIN_PRIORITIES = [];
var ADMIN_PRIORITY_MATRIX = [];

function loadAdminPriorities() {
  api('GET', '/admin/priorities').then(function (d) {
    ADMIN_PRIORITIES = d;
    api('GET', '/admin/priority-matrix').then(function (m) {
      ADMIN_PRIORITY_MATRIX = m;
      ADMIN_LOADED.priorities = true;
      if (ADMIN_TAB === 'priorities') render();
    });
  });
}

function _matrixCell(impact, urgency) {
  var row = ADMIN_PRIORITY_MATRIX.find(function (m) { return m.impact_code === impact && m.urgency_code === urgency; });
  return row ? row.priority_code : '';
}

function viewAdminPriorities() {
  var rows = ADMIN_PRIORITIES.map(function (p) {
    return '<tr><td><b>' + esc(p.code) + '</b></td><td>' + esc(p.label) + '</td><td>' + esc(p.description || '') + '</td>' +
      '<td>' + (p.severity != null ? esc(p.severity) : '') + '</td><td>' + esc(p.display_order) + '</td>' +
      '<td>' + (p.is_active ? '<span class="pill p-ok">Active</span>' : '<span class="pill p-mut">Inactive</span>') + '</td>' +
      '<td style="display:flex;gap:6px"><button class="btn o sm" onclick="adminEditPriority(\'' + p.code + '\')">Edit</button>' +
      '<button class="btn ' + (p.is_active ? 'r' : 'g') + ' sm" onclick="adminTogglePriority(\'' + p.code + '\',' + (!p.is_active) + ')">' + (p.is_active ? 'Deactivate' : 'Activate') + '</button></td></tr>';
  }).join('');

  var activePriorityOpts = function (selected) {
    return ADMIN_PRIORITIES.filter(function (p) { return p.is_active; }).map(function (p) {
      return '<option value="' + p.code + '"' + (p.code === selected ? ' selected' : '') + '>' + esc(p.label) + ' (' + p.code + ')</option>';
    }).join('');
  };
  var impactLevels = META.impact_levels || [], urgencyLevels = META.urgency_levels || [];
  var matrixHead = '<th>Impact \\ Urgency</th>' + urgencyLevels.map(function (u) { return '<th>' + esc(u) + '</th>'; }).join('');
  var matrixRows = impactLevels.map(function (impact) {
    return '<tr><td><b>' + esc(impact) + '</b></td>' + urgencyLevels.map(function (urgency) {
      var current = _matrixCell(impact, urgency);
      return '<td><select onchange="adminSetMatrixCell(\'' + impact + '\',\'' + urgency + '\',this.value)">' + activePriorityOpts(current) + '</select></td>';
    }).join('') + '</tr>';
  }).join('');

  return '<div class="card" style="margin-bottom:14px"><h4 style="margin-bottom:4px;font-size:15px">Priority Master</h4>' +
    '<div class="muted" style="margin-bottom:10px">The four priorities (P1-P4) used for TAT, SLA tiers and routing everywhere else in the system. Codes are fixed; label/description/severity/order are editable.</div>' +
    '<div style="overflow-x:auto"><table><thead><tr><th>Code</th><th>Label</th><th>Description</th><th>Severity</th><th>Order</th><th>Status</th><th></th></tr></thead><tbody>' + rows + '</tbody></table></div></div>' +
    '<div class="card" style="margin-bottom:14px"><h4 style="margin-bottom:10px;font-size:14px">Add priority</h4><div class="grid3">' +
    '<div class="fld"><label>Code</label><input id="pr_code" placeholder="P5"></div>' +
    '<div class="fld"><label>Label</label><input id="pr_label" placeholder="Planned"></div>' +
    '<div class="fld"><label>Description</label><input id="pr_desc" placeholder="Planned change / scheduled work"></div>' +
    '<div class="fld"><label>Severity (1=highest)</label><input id="pr_severity" type="number"></div>' +
    '<div class="fld"><label>Display order</label><input id="pr_order" type="number" value="0"></div>' +
    '<div class="fld" style="display:flex;align-items:flex-end"><button class="btn" onclick="adminCreatePriority()">Add priority</button></div>' +
    '</div></div>' +
    '<div class="card"><h4 style="margin-bottom:4px;font-size:15px">Impact &times; Urgency &rarr; Priority Matrix</h4>' +
    '<div class="muted" style="margin-bottom:10px">Register Call uses this grid to suggest a Priority once both Impact and Urgency are chosen - the call taker can still override it.</div>' +
    '<div style="overflow-x:auto"><table><thead><tr>' + matrixHead + '</tr></thead><tbody>' + matrixRows + '</tbody></table></div></div>';
}

function adminCreatePriority() {
  var code = gv('pr_code'), label = gv('pr_label'), desc = gv('pr_desc');
  var severity = gv('pr_severity'), order = gv('pr_order');
  if (!code || !label) return toast('Code and label are required');
  api('POST', '/admin/priorities', {
    code: code, label: label, description: desc || undefined,
    severity: severity ? +severity : undefined, display_order: order ? +order : 0
  }).then(function () { toast('Priority added'); loadAdminPriorities(); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}
function adminEditPriority(code) {
  var p = ADMIN_PRIORITIES.find(function (x) { return x.code === code; });
  var label = prompt('Label:', p ? p.label : ''); if (label === null) return;
  var description = prompt('Description:', p ? (p.description || '') : ''); if (description === null) return;
  var order = prompt('Display order:', p ? p.display_order : 0); if (order === null) return;
  api('PUT', '/admin/priorities/' + code, { label: label, description: description, display_order: +order || 0 })
    .then(function () { toast('Updated'); loadAdminPriorities(); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}
function adminTogglePriority(code, active) {
  api('PUT', '/admin/priorities/' + code, { is_active: active }).then(function () { toast(active ? 'Activated' : 'Deactivated'); loadAdminPriorities(); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}
function adminSetMatrixCell(impact, urgency, priorityCode) {
  api('PUT', '/admin/priority-matrix', { impact_code: impact, urgency_code: urgency, priority_code: priorityCode })
    .then(function () { toast('Matrix updated'); loadAdminPriorities(); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}

/* ---------- Admin: Business Calendars + Holidays ---------- */
var ADMIN_CALENDARS = [];
var ADMIN_CAL_HOLIDAYS = {};   // {calendar_code: [holiday, ...]}
var CAL_SELECTED = null;       // which calendar's holiday list is expanded
var CAL_DAYS = [['mon', 'Mon'], ['tue', 'Tue'], ['wed', 'Wed'], ['thu', 'Thu'], ['fri', 'Fri'], ['sat', 'Sat'], ['sun', 'Sun']];

function loadAdminCalendars() {
  api('GET', '/admin/calendars').then(function (d) {
    ADMIN_CALENDARS = d;
    ADMIN_LOADED.calendars = true;
    if (ADMIN_TAB === 'calendars') render();
  });
}
function loadCalendarHolidays(code) {
  api('GET', '/admin/calendars/' + code + '/holidays').then(function (d) {
    ADMIN_CAL_HOLIDAYS[code] = d;
    if (ADMIN_TAB === 'calendars') render();
  });
}
function toggleCalendarHolidays(code) {
  CAL_SELECTED = (CAL_SELECTED === code) ? null : code;
  if (CAL_SELECTED && !ADMIN_CAL_HOLIDAYS[CAL_SELECTED]) loadCalendarHolidays(CAL_SELECTED);
  render();
}
function cal247Toggled() {
  var on = document.getElementById('cal_247').checked;
  document.getElementById('cal_hours_grid').classList.toggle('hide', on);
}
function workingHoursGrid(prefix) {
  return '<table style="margin-top:8px"><thead><tr><th>Day</th><th>Working?</th><th>Start</th><th>End</th></tr></thead><tbody>' +
    CAL_DAYS.map(function (d) {
      var day = d[0], label = d[1];
      var workingByDefault = (day !== 'sat' && day !== 'sun');
      return '<tr>' +
        '<td>' + label + '</td>' +
        '<td><input type="checkbox" id="' + prefix + '_' + day + '_on"' + (workingByDefault ? ' checked' : '') + ' onchange="document.getElementById(\'' + prefix + '_' + day + '_start\').disabled=!this.checked;document.getElementById(\'' + prefix + '_' + day + '_end\').disabled=!this.checked;"></td>' +
        '<td><input type="time" id="' + prefix + '_' + day + '_start" value="09:00"' + (workingByDefault ? '' : ' disabled') + '></td>' +
        '<td><input type="time" id="' + prefix + '_' + day + '_end" value="18:00"' + (workingByDefault ? '' : ' disabled') + '></td>' +
        '</tr>';
    }).join('') + '</tbody></table>';
}
function readWorkingHoursGrid(prefix) {
  var out = {};
  CAL_DAYS.forEach(function (d) {
    var day = d[0];
    var on = document.getElementById(prefix + '_' + day + '_on').checked;
    out[day] = on ? [document.getElementById(prefix + '_' + day + '_start').value, document.getElementById(prefix + '_' + day + '_end').value] : null;
  });
  return out;
}

function viewAdminCalendars() {
  var rows = ADMIN_CALENDARS.map(function (c) {
    var holidayRows = (ADMIN_CAL_HOLIDAYS[c.code] || []).map(function (h) {
      return '<tr><td>' + esc(h.holiday_date) + '</td><td>' + esc(h.label || '') + '</td>' +
        '<td><button class="btn r sm" onclick="adminRemoveHoliday(' + h.id + ',\'' + c.code + '\')">Remove</button></td></tr>';
    }).join('');
    var expanded = CAL_SELECTED === c.code;
    return '<tr><td><b>' + esc(c.code) + '</b></td><td>' + esc(c.name) + '</td>' +
      '<td>' + (c.is_24x7 ? '<span class="pill p-ok">24x7</span>' : '<span class="pill p-mut">Business hours</span>') + '</td>' +
      '<td>' + (c.is_active ? '<span class="pill p-ok">Active</span>' : '<span class="pill p-mut">Inactive</span>') + '</td>' +
      '<td style="display:flex;gap:6px"><button class="btn o sm" onclick="toggleCalendarHolidays(\'' + c.code + '\')">' + (expanded ? 'Hide holidays' : 'Holidays') + '</button>' +
      '<button class="btn ' + (c.is_active ? 'r' : 'g') + ' sm" onclick="adminToggleCalendar(\'' + c.code + '\',' + (!c.is_active) + ')">' + (c.is_active ? 'Deactivate' : 'Activate') + '</button></td></tr>' +
      (expanded ? ('<tr><td colspan="5"><div style="padding:10px;background:#f9fafb;border-radius:8px">' +
        '<table><thead><tr><th>Date</th><th>Label</th><th></th></tr></thead><tbody>' + (holidayRows || '<tr><td colspan="3" class="muted">No holidays yet</td></tr>') + '</tbody></table>' +
        '<div class="grid3" style="margin-top:10px">' +
        '<div class="fld"><label>Date</label><input type="date" id="hol_date_' + c.code + '"></div>' +
        '<div class="fld"><label>Label</label><input id="hol_label_' + c.code + '" placeholder="Republic Day"></div>' +
        '<div class="fld" style="display:flex;align-items:flex-end"><button class="btn sm" onclick="adminAddHoliday(\'' + c.code + '\')">Add holiday</button></div>' +
        '</div></div></td></tr>') : '');
  }).join('');

  return '<div class="card" style="margin-bottom:14px"><h4 style="margin-bottom:4px;font-size:15px">Business Calendars</h4>' +
    '<div class="muted" style="margin-bottom:10px">An SLA Policy measures its Response/Resolution minutes against one of these. A 24x7 calendar is a plain wall-clock count; a business-hours calendar only counts minutes inside the configured working windows, skipping weekends/holidays.</div>' +
    '<div style="overflow-x:auto"><table><thead><tr><th>Code</th><th>Name</th><th>Type</th><th>Status</th><th></th></tr></thead><tbody>' + rows + '</tbody></table></div></div>' +
    '<div class="card"><h4 style="margin-bottom:10px;font-size:14px">Add calendar</h4>' +
    '<div class="grid3">' +
    '<div class="fld"><label>Code</label><input id="cal_code" placeholder="BIZ-HOURS"></div>' +
    '<div class="fld"><label>Name</label><input id="cal_name" placeholder="Business Hours (Mon-Fri 9-6)"></div>' +
    '<div class="fld" style="display:flex;align-items:center;gap:8px;margin-top:18px"><input type="checkbox" id="cal_247" checked onchange="cal247Toggled()"> <label style="margin:0;text-transform:none;font-size:13px;font-weight:600;color:var(--ink2)">24x7 (no working-hours restriction)</label></div>' +
    '</div>' +
    '<div id="cal_hours_grid" class="hide">' + workingHoursGrid('cal') + '</div>' +
    '<div style="margin-top:10px"><button class="btn" onclick="adminCreateCalendar()">Add calendar</button></div>' +
    '</div>';
}

function adminCreateCalendar() {
  var code = gv('cal_code'), name = gv('cal_name');
  var is247 = document.getElementById('cal_247').checked;
  if (!code || !name) return toast('Code and name are required');
  api('POST', '/admin/calendars', {
    code: code, name: name, is_24x7: is247,
    working_hours: is247 ? undefined : readWorkingHoursGrid('cal')
  }).then(function () { toast('Calendar added'); loadAdminCalendars(); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}
function adminToggleCalendar(code, active) {
  api('PUT', '/admin/calendars/' + code, { is_active: active }).then(function () { toast(active ? 'Activated' : 'Deactivated'); loadAdminCalendars(); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}
function adminAddHoliday(code) {
  var date = document.getElementById('hol_date_' + code).value, label = gv('hol_label_' + code);
  if (!date) return toast('Date is required');
  api('POST', '/admin/calendars/' + code + '/holidays', { holiday_date: date, label: label })
    .then(function () { toast('Holiday added'); loadCalendarHolidays(code); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}
function adminRemoveHoliday(id, code) {
  api('DELETE', '/admin/calendars/holidays/' + id).then(function () { toast('Removed'); loadCalendarHolidays(code); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}

/* ---------- Admin: SLA Policies ---------- */
var ADMIN_SLA_POLICIES = [];

function loadAdminSlaPolicies() {
  api('GET', '/admin/sla-policies').then(function (d) {
    ADMIN_SLA_POLICIES = d;
    api('GET', '/admin/calendars').then(function (c) {
      ADMIN_CALENDARS = c;
      api('GET', '/admin/categories').then(function (cats) {
        ADMIN_CATEGORIES = cats;
        api('GET', '/admin/reasons').then(function (r) {
          ADMIN_REASONS = r;
          ADMIN_LOADED.slapolicies = true;
          if (ADMIN_TAB === 'slapolicies') render();
        });
      });
    });
  });
}

function _slaPolicyScopeLabel(p) {
  if (p.subcategory_code) { var r = ADMIN_REASONS.find(function (x) { return x.code === p.subcategory_code; }); return 'Sub-Category: ' + (r ? r.label : p.subcategory_code); }
  if (p.category_code) { var c = ADMIN_CATEGORIES.find(function (x) { return x.code === p.category_code; }); return 'Category: ' + (c ? c.label : p.category_code); }
  if (p.ticket_type) { return 'Ticket Type: ' + ((META.ticket_types && META.ticket_types[p.ticket_type] && META.ticket_types[p.ticket_type].label) || p.ticket_type); }
  return 'Baseline (all tickets)';
}

function viewAdminSlaPolicies() {
  var rows = ADMIN_SLA_POLICIES.map(function (p) {
    return '<tr><td><b>' + esc(p.code) + '</b></td><td>' + esc(_slaPolicyScopeLabel(p)) + '</td>' +
      '<td>' + esc(p.priority_code) + '</td><td>' + (p.response_mins || '—') + '</td><td>' + esc(p.resolution_mins) + '</td>' +
      '<td>' + esc(p.calendar_code) + '</td>' +
      '<td>' + (p.is_active ? '<span class="pill p-ok">Active</span>' : '<span class="pill p-mut">Inactive</span>') + '</td>' +
      '<td style="display:flex;gap:6px"><button class="btn o sm" onclick="adminEditSlaPolicy(\'' + p.code + '\')">Edit</button>' +
      '<button class="btn ' + (p.is_active ? 'r' : 'g') + ' sm" onclick="adminToggleSlaPolicy(\'' + p.code + '\',' + (!p.is_active) + ')">' + (p.is_active ? 'Deactivate' : 'Activate') + '</button></td></tr>';
  }).join('');

  var catOpts = '<option value="">— None —</option>' + ADMIN_CATEGORIES.filter(function (c) { return c.is_active; }).map(function (c) { return '<option value="' + c.code + '">' + esc(c.label) + '</option>'; }).join('');
  var subcatOpts = '<option value="">— None —</option>' + ADMIN_REASONS.filter(function (r) { return r.is_active; }).map(function (r) { return '<option value="' + r.code + '">' + esc(r.label) + '</option>'; }).join('');
  var ttOpts = '<option value="">— None —</option>' + Object.keys(META.ticket_types || {}).map(function (k) { return '<option value="' + k + '">' + esc(META.ticket_types[k].label) + '</option>'; }).join('');
  var prOpts = Object.keys(META.priorities || {}).sort(function (a, b) { return (META.priorities[a].display_order || 0) - (META.priorities[b].display_order || 0); }).map(function (code) { return '<option value="' + code + '">' + esc(META.priorities[code].label) + ' (' + code + ')</option>'; }).join('');
  var calOpts = ADMIN_CALENDARS.filter(function (c) { return c.is_active; }).map(function (c) { return '<option value="' + c.code + '"' + (c.code === 'DEFAULT-24X7' ? ' selected' : '') + '>' + esc(c.name) + '</option>'; }).join('');

  return '<div class="card" style="margin-bottom:14px"><h4 style="margin-bottom:4px;font-size:15px">SLA Policies</h4>' +
    '<div class="muted" style="margin-bottom:10px">The most specific match wins for a ticket: Sub-Category &gt; Category &gt; Ticket Type &gt; the Baseline row for that priority (what the old "SLA &amp; TAT" screen edits). Leave Category/Sub-Category/Ticket Type all unset only to edit a Baseline row.</div>' +
    '<div style="overflow-x:auto"><table><thead><tr><th>Code</th><th>Scope</th><th>Priority</th><th>Response (min)</th><th>Resolution (min)</th><th>Calendar</th><th>Status</th><th></th></tr></thead><tbody>' + rows + '</tbody></table></div></div>' +
    '<div class="card"><h4 style="margin-bottom:10px;font-size:14px">Add SLA policy</h4><div class="grid3">' +
    '<div class="fld"><label>Code</label><input id="sp_code" placeholder="MACHINE-P2"></div>' +
    '<div class="fld"><label>Priority</label><select id="sp_priority">' + prOpts + '</select></div>' +
    '<div class="fld"><label>Calendar</label><select id="sp_calendar">' + calOpts + '</select></div>' +
    '<div class="fld"><label>Category (optional)</label><select id="sp_category">' + catOpts + '</select></div>' +
    '<div class="fld"><label>Sub-Category (optional)</label><select id="sp_subcategory">' + subcatOpts + '</select></div>' +
    '<div class="fld"><label>Ticket Type (optional)</label><select id="sp_tickettype">' + ttOpts + '</select></div>' +
    '<div class="fld"><label>Response SLA (minutes, optional)</label><input id="sp_response" type="number"></div>' +
    '<div class="fld"><label>Resolution SLA (minutes) *</label><input id="sp_resolution" type="number"></div>' +
    '<div class="fld" style="display:flex;align-items:flex-end"><button class="btn" onclick="adminCreateSlaPolicy()">Add policy</button></div>' +
    '</div></div>';
}

function adminCreateSlaPolicy() {
  var code = gv('sp_code'), priority = document.getElementById('sp_priority').value;
  var resolution = gv('sp_resolution'), response = gv('sp_response');
  var category = document.getElementById('sp_category').value, subcategory = document.getElementById('sp_subcategory').value;
  var tickettype = document.getElementById('sp_tickettype').value, calendar = document.getElementById('sp_calendar').value;
  if (!code || !resolution) return toast('Code and Resolution SLA are required');
  api('POST', '/admin/sla-policies', {
    code: code, priority_code: priority, resolution_mins: +resolution, response_mins: response ? +response : undefined,
    category_code: category || undefined, subcategory_code: subcategory || undefined, ticket_type: tickettype || undefined,
    calendar_code: calendar
  }).then(function () { toast('SLA policy added'); loadAdminSlaPolicies(); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}
function adminEditSlaPolicy(code) {
  var p = ADMIN_SLA_POLICIES.find(function (x) { return x.code === code; });
  var resolution = prompt('Resolution SLA (minutes):', p ? p.resolution_mins : ''); if (resolution === null) return;
  var response = prompt('Response SLA (minutes, blank for none):', p && p.response_mins ? p.response_mins : ''); if (response === null) return;
  api('PUT', '/admin/sla-policies/' + code, { resolution_mins: +resolution, response_mins: response ? +response : null })
    .then(function () { toast('Updated'); loadAdminSlaPolicies(); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}
function adminToggleSlaPolicy(code, active) {
  api('PUT', '/admin/sla-policies/' + code, { is_active: active }).then(function () { toast(active ? 'Activated' : 'Deactivated'); loadAdminSlaPolicies(); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}
