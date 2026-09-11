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
