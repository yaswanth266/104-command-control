/* ---------- Admin: Routing Rules, Hierarchy Source, Assignment Exceptions ----------
   Phase 4 (L1-L4 hierarchy / routing engine). Same wiring approach as
   masters.js: new file, a few added lines in app.js's nav/dispatch. */
var ADMIN_ROUTING_RULES = [];
var ADMIN_HIERARCHY_CONFIG = null;
var ADMIN_ASSIGNMENT_EXCEPTIONS = [];
var EXC_FILTER = 'OPEN';

function loadAdminRoutingRules() {
  api('GET', '/admin/routing-rules').then(function (d) {
    ADMIN_ROUTING_RULES = d;
    api('GET', '/admin/categories').then(function (c) {
      ADMIN_CATEGORIES = c;
      api('GET', '/admin/zones').then(function (z) {
        ADMIN_ZONES = z;
        ADMIN_LOADED.routingrules = true;
        if (ADMIN_TAB === 'routingrules') render();
      });
    });
  });
}

function viewAdminRoutingRules() {
  var catLabel = function (code) { var c = ADMIN_CATEGORIES.find(function (x) { return x.code === code; }); return c ? c.label : code; };
  var zoneLabel = function (id) { var z = (ADMIN_ZONES || []).find(function (x) { return x.id === id; }); return z ? z.name : ''; };
  var rows = ADMIN_ROUTING_RULES.map(function (r) {
    return '<tr><td><b>' + esc(r.code) + '</b></td><td>' + esc(catLabel(r.category_code)) + '</td>' +
      '<td>' + esc(zoneLabel(r.zone_id) || '— any —') + '</td>' +
      '<td>' + esc(r.l1_username || (r.l1_team_code || '')) + '</td><td>' + esc(r.l2_username || '') + '</td>' +
      '<td>' + esc(r.l3_username || '') + '</td><td>' + esc(r.l4_username || '') + '</td>' +
      '<td>' + (r.is_active ? '<span class="pill p-ok">Active</span>' : '<span class="pill p-mut">Inactive</span>') + '</td>' +
      '<td><button class="btn ' + (r.is_active ? 'r' : 'g') + ' sm" onclick="adminToggleRoutingRule(\'' + r.code + '\',' + (!r.is_active) + ')">' + (r.is_active ? 'Deactivate' : 'Activate') + '</button></td></tr>';
  }).join('');
  var catOpts = ADMIN_CATEGORIES.filter(function (c) { return c.is_active; }).map(function (c) { return '<option value="' + c.code + '">' + esc(c.label) + '</option>'; }).join('');
  var zoneOpts = '<option value="">— Any zone —</option>' + (ADMIN_ZONES || []).filter(function (z) { return z.is_active; }).map(function (z) { return '<option value="' + z.id + '">' + esc(z.name) + '</option>'; }).join('');

  return '<div class="card" style="margin-bottom:14px"><h4 style="margin-bottom:4px;font-size:15px">Routing Rules</h4>' +
    '<div class="muted" style="margin-bottom:10px">Explicit L1-L4 mapping for a Category (optionally narrowed to one Zone) - used when the Hierarchy Source is set to Local Mapping. Any level left blank falls back to the default ladder: L1 = the category\'s routed team, L2 = that team\'s manager, L3 = L2\'s reporting manager, L4 = the Global Team Executive.</div>' +
    '<div style="overflow-x:auto"><table><thead><tr><th>Code</th><th>Category</th><th>Zone</th><th>L1</th><th>L2</th><th>L3</th><th>L4</th><th>Status</th><th></th></tr></thead><tbody>' + rows + '</tbody></table></div></div>' +
    '<div class="card"><h4 style="margin-bottom:10px;font-size:14px">Add routing rule</h4><div class="grid3">' +
    '<div class="fld"><label>Code</label><input id="rr_code" placeholder="MACHINE-NORTH"></div>' +
    '<div class="fld"><label>Category</label><select id="rr_category">' + catOpts + '</select></div>' +
    '<div class="fld"><label>Zone (optional)</label><select id="rr_zone">' + zoneOpts + '</select></div>' +
    '<div class="fld"><label>L1 username (optional)</label><input id="rr_l1" placeholder="username"></div>' +
    '<div class="fld"><label>L2 username (optional)</label><input id="rr_l2" placeholder="username"></div>' +
    '<div class="fld"><label>L3 username (optional)</label><input id="rr_l3" placeholder="username"></div>' +
    '<div class="fld"><label>L4 username (optional)</label><input id="rr_l4" placeholder="username"></div>' +
    '<div class="fld" style="display:flex;align-items:flex-end"><button class="btn" onclick="adminCreateRoutingRule()">Add rule</button></div>' +
    '</div></div>';
}

function adminCreateRoutingRule() {
  var code = gv('rr_code'), category = document.getElementById('rr_category').value;
  var zone = document.getElementById('rr_zone').value;
  if (!code) return toast('Code is required');
  api('POST', '/admin/routing-rules', {
    code: code, category_code: category, zone_id: zone ? +zone : undefined,
    l1_username: gv('rr_l1') || undefined, l2_username: gv('rr_l2') || undefined,
    l3_username: gv('rr_l3') || undefined, l4_username: gv('rr_l4') || undefined,
  }).then(function () { toast('Routing rule added'); loadAdminRoutingRules(); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}
function adminToggleRoutingRule(code, active) {
  api('PUT', '/admin/routing-rules/' + code, { is_active: active }).then(function () { toast(active ? 'Activated' : 'Deactivated'); loadAdminRoutingRules(); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}

/* ---------- Hierarchy Source config ---------- */

function loadAdminHierarchyConfig() {
  api('GET', '/admin/hierarchy/config').then(function (d) {
    ADMIN_HIERARCHY_CONFIG = d;
    ADMIN_LOADED.hierarchysource = true;
    if (ADMIN_TAB === 'hierarchysource') render();
  });
}

function viewAdminHierarchySource() {
  if (!ADMIN_HIERARCHY_CONFIG) return '<div class="card"><div class="empty">Loading…</div></div>';
  var cfg = ADMIN_HIERARCHY_CONFIG;
  var isExternal = cfg.mode === 'EXTERNAL_API';
  return '<div class="card" style="margin-bottom:14px"><h4 style="margin-bottom:4px;font-size:15px">Hierarchy Source</h4>' +
    '<div class="muted" style="margin-bottom:10px">Where a new ticket\'s L1-L4 chain comes from. Local Mapping uses Routing Rules (or the default ladder) and needs no network call. External API POSTs the ticket\'s classification to your organization\'s hierarchy/HR system and normalizes whatever it returns - if it fails, CCC automatically falls back to Local Mapping and logs the failure to the Assignment Exceptions queue, so a ticket is never blocked on it.</div>' +
    '<div class="grid3">' +
    '<div class="fld"><label>Mode</label><select id="hc_mode" onchange="hcModeToggled()"><option value="LOCAL"' + (!isExternal ? ' selected' : '') + '>Local Mapping</option><option value="EXTERNAL_API"' + (isExternal ? ' selected' : '') + '>External API</option></select></div>' +
    '<div class="fld"><label>Timeout (seconds)</label><input id="hc_timeout" type="number" value="' + esc(cfg.timeout_seconds) + '"></div>' +
    '<div></div>' +
    '</div>' +
    '<div id="hc_api_fields" class="grid3' + (isExternal ? '' : ' hide') + '" style="margin-top:4px">' +
    '<div class="fld"><label>API URL</label><input id="hc_url" value="' + esc(cfg.url || '') + '" placeholder="https://hr.example.org/api/hierarchy"></div>' +
    '<div class="fld"><label>Auth header name (optional)</label><input id="hc_auth_header" value="' + esc(cfg.auth_header || '') + '" placeholder="Authorization"></div>' +
    '<div class="fld"><label>Auth token / value' + (cfg.auth_token_set ? ' (already set - leave blank to keep)' : '') + '</label><input id="hc_auth_token" placeholder="' + (cfg.auth_token_set ? '••••••••' : 'Bearer …') + '"></div>' +
    '</div>' +
    '<div style="margin-top:12px;display:flex;gap:8px">' +
    '<button class="btn" onclick="adminSaveHierarchyConfig()">Save</button>' +
    (isExternal ? '<button class="btn o" onclick="adminTestHierarchyApi()">Test connection</button>' : '') +
    '</div><div id="hc_test_result" class="muted" style="margin-top:8px"></div>' +
    '</div>';
}
function hcModeToggled() {
  var external = document.getElementById('hc_mode').value === 'EXTERNAL_API';
  document.getElementById('hc_api_fields').classList.toggle('hide', !external);
}
function adminSaveHierarchyConfig() {
  var patch = { mode: document.getElementById('hc_mode').value, timeout_seconds: +gv('hc_timeout') || undefined };
  if (patch.mode === 'EXTERNAL_API') {
    patch.url = gv('hc_url');
    patch.auth_header = gv('hc_auth_header') || undefined;
    if (gv('hc_auth_token')) patch.auth_token = gv('hc_auth_token');
  }
  api('PUT', '/admin/hierarchy/config', patch).then(function () { toast('Saved'); loadAdminHierarchyConfig(); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}
function adminTestHierarchyApi() {
  document.getElementById('hc_test_result').textContent = 'Testing…';
  api('POST', '/admin/hierarchy/test', {}).then(function (r) {
    document.getElementById('hc_test_result').textContent = r.ok ?
      ('✅ Reachable (status ' + r.status_code + ', ' + r.elapsed_ms + 'ms)') :
      ('❌ ' + (r.error || ('status ' + r.status_code)) + ' (' + r.elapsed_ms + 'ms)');
  }).catch(function (e) { document.getElementById('hc_test_result').textContent = typeof e === 'string' ? e : 'Test failed'; });
}

/* ---------- Assignment Exceptions ---------- */

function loadAdminAssignmentExceptions() {
  api('GET', '/admin/assignment-exceptions' + (EXC_FILTER ? ('?status=' + EXC_FILTER) : '')).then(function (d) {
    ADMIN_ASSIGNMENT_EXCEPTIONS = d;
    ADMIN_LOADED.assignmentexceptions = true;
    if (ADMIN_TAB === 'assignmentexceptions') render();
  });
}
function excFilterChanged() {
  EXC_FILTER = document.getElementById('exc_filter').value;
  loadAdminAssignmentExceptions();
}
function viewAdminAssignmentExceptions() {
  var rows = ADMIN_ASSIGNMENT_EXCEPTIONS.map(function (e) {
    return '<tr><td>' + e.ticket_id + '</td><td>' + esc(e.reason) + '</td>' +
      '<td style="max-width:320px;white-space:normal">' + esc(e.detail || '') + '</td>' +
      '<td>' + esc(e.created_at) + '</td>' +
      '<td>' + (e.status === 'OPEN' ? '<span class="pill p-warn">Open</span>' : '<span class="pill p-ok">Resolved</span>') + '</td>' +
      '<td>' + (e.status === 'OPEN' ? ('<button class="btn g sm" onclick="adminResolveException(' + e.id + ')">Mark resolved</button>') : esc(e.resolved_by || '')) + '</td></tr>';
  }).join('');
  return '<div class="card"><h4 style="margin-bottom:4px;font-size:15px">Assignment Exceptions</h4>' +
    '<div class="muted" style="margin-bottom:10px">A ticket is never blocked on hierarchy resolution - if the External API failed (or nothing could be resolved), the ticket still routes normally and the attempt lands here for a supervisor to review.</div>' +
    '<div class="fld" style="max-width:220px;margin-bottom:10px"><label>Status</label><select id="exc_filter" onchange="excFilterChanged()">' +
    '<option value="OPEN"' + (EXC_FILTER === 'OPEN' ? ' selected' : '') + '>Open</option>' +
    '<option value="RESOLVED"' + (EXC_FILTER === 'RESOLVED' ? ' selected' : '') + '>Resolved</option>' +
    '<option value=""' + (EXC_FILTER === '' ? ' selected' : '') + '>All</option></select></div>' +
    '<div style="overflow-x:auto"><table><thead><tr><th>Ticket</th><th>Reason</th><th>Detail</th><th>At</th><th>Status</th><th></th></tr></thead><tbody>' +
    (rows || '<tr><td colspan="6" class="muted">Nothing here.</td></tr>') + '</tbody></table></div></div>';
}
function adminResolveException(id) {
  api('POST', '/admin/assignment-exceptions/' + id + '/resolve', {}).then(function () { toast('Resolved'); loadAdminAssignmentExceptions(); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}
