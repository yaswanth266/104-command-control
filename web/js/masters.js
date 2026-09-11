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
