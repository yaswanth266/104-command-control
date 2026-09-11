/* ---------- Admin: Routing Rules, Hierarchy Source, Assignment Exceptions ----------
   Phase 4 (L1-L4 hierarchy / routing engine). Same wiring approach as
   masters.js: new file, a few added lines in app.js's nav/dispatch. */
var ADMIN_ROUTING_RULES = [];
var ADMIN_HIERARCHY_CONFIG = null;
var ADMIN_ASSIGNMENT_EXCEPTIONS = [];
var ADMIN_SYNC_STATUS = null;
var EXC_FILTER = 'OPEN';

function loadAdminRoutingRules() {
  api('GET', '/admin/routing-rules').then(function (d) {
    ADMIN_ROUTING_RULES = d;
    api('GET', '/admin/categories').then(function (c) {
      ADMIN_CATEGORIES = c;
      api('GET', '/admin/zones').then(function (z) {
        ADMIN_ZONES = z;
        api('GET', '/admin/districts').then(function (dist) {
          ADMIN_DISTRICTS = dist;
          api('GET', '/admin/reasons').then(function (r) {
            ADMIN_REASONS = r;
            ADMIN_LOADED.routingrules = true;
            if (ADMIN_TAB === 'routingrules') render();
          });
        });
      });
    });
  });
}

/* Per-level occupant precedence at resolution time (see
   app/services/hierarchy.py's _resolve_level): username > role > team_code
   > default ladder - so each level gets all three input types, and an
   admin can mix them freely across levels (the client's example: L1->OE
   role, L2->DM role, L3->Helpdesk team, L4->Development team). */
function _levelSummary(r, n) {
  var u = r['l' + n + '_username'], role = r['l' + n + '_role'], t = r['l' + n + '_team_code'];
  var parts = [];
  if (u) parts.push(u);
  if (role) parts.push('role:' + role);
  if (t) parts.push('team:' + t);
  return parts.join(', ');
}

function viewAdminRoutingRules() {
  var catLabel = function (code) { var c = ADMIN_CATEGORIES.find(function (x) { return x.code === code; }); return c ? c.label : code; };
  var zoneLabel = function (id) { var z = (ADMIN_ZONES || []).find(function (x) { return x.id === id; }); return z ? z.name : ''; };
  var distLabel = function (id) { var d = (ADMIN_DISTRICTS || []).find(function (x) { return x.id === id; }); return d ? d.name : ''; };
  var subcatLabel = function (code) { var r = (ADMIN_REASONS || []).find(function (x) { return x.code === code; }); return r ? r.label : code; };
  var rows = ADMIN_ROUTING_RULES.map(function (r) {
    return '<tr><td><b>' + esc(r.code) + '</b></td><td>' + esc(catLabel(r.category_code)) + '</td>' +
      '<td>' + esc(r.subcategory_code ? subcatLabel(r.subcategory_code) : '— any —') + '</td>' +
      '<td>' + esc(distLabel(r.district_id) || '— any —') + '</td>' +
      '<td>' + esc(zoneLabel(r.zone_id) || '— any —') + '</td>' +
      '<td>' + esc(_levelSummary(r, 1)) + '</td><td>' + esc(_levelSummary(r, 2)) + '</td>' +
      '<td>' + esc(_levelSummary(r, 3)) + '</td><td>' + esc(_levelSummary(r, 4)) + '</td>' +
      '<td>' + (r.is_active ? '<span class="pill p-ok">Active</span>' : '<span class="pill p-mut">Inactive</span>') + '</td>' +
      '<td><button class="btn ' + (r.is_active ? 'r' : 'g') + ' sm" onclick="adminToggleRoutingRule(\'' + r.code + '\',' + (!r.is_active) + ')">' + (r.is_active ? 'Deactivate' : 'Activate') + '</button></td></tr>';
  }).join('');
  var catOpts = ADMIN_CATEGORIES.filter(function (c) { return c.is_active; }).map(function (c) { return '<option value="' + c.code + '">' + esc(c.label) + '</option>'; }).join('');
  var subcatOpts = '<option value="">— Any sub-category —</option>' + (ADMIN_REASONS || []).filter(function (r) { return r.is_active; }).map(function (r) { return '<option value="' + r.code + '" data-cat="' + r.category_code + '">' + esc(r.label) + '</option>'; }).join('');
  var distOpts = '<option value="">— Any district —</option>' + (ADMIN_DISTRICTS || []).filter(function (d) { return d.is_active; }).map(function (d) { return '<option value="' + d.id + '">' + esc(d.name) + '</option>'; }).join('');
  var zoneOpts = '<option value="">— Any zone —</option>' + (ADMIN_ZONES || []).filter(function (z) { return z.is_active; }).map(function (z) { return '<option value="' + z.id + '">' + esc(z.name) + '</option>'; }).join('');

  var levelFields = [1, 2, 3, 4].map(function (n) {
    return '<div class="fld"><label>L' + n + ' - Local username</label><input id="rr_l' + n + '_user" placeholder="username"></div>' +
      '<div class="fld"><label>L' + n + ' - API role (e.g. OE, DM)</label><input id="rr_l' + n + '_role" placeholder="OE"></div>' +
      '<div class="fld"><label>L' + n + ' - Team / department</label><input id="rr_l' + n + '_team" placeholder="HELPDESK"></div>';
  }).join('');

  return '<div class="card" style="margin-bottom:14px"><h4 style="margin-bottom:4px;font-size:15px">Routing Rules</h4>' +
    '<div class="muted" style="margin-bottom:10px">Explicit L1-L4 mapping for a Category, optionally narrowed to a Sub-Category, District and/or Zone - used when the Hierarchy Source is set to Local Mapping. The most specific active match wins (Sub-Category beats Category-only; District beats Zone). Each level resolves, in order: an explicit local username &gt; an external-API organizational role (OE/DM/RM/SPH/…, resolved via the synced hierarchy cache against the ticket\'s caller) &gt; a local team/department &gt; the default ladder (L1 = the category\'s routed team, L2 = that team\'s manager, L3 = L2\'s reporting manager, L4 = the Global Team Executive).</div>' +
    '<div style="overflow-x:auto"><table><thead><tr><th>Code</th><th>Category</th><th>Sub-Category</th><th>District</th><th>Zone</th><th>L1</th><th>L2</th><th>L3</th><th>L4</th><th>Status</th><th></th></tr></thead><tbody>' + rows + '</tbody></table></div></div>' +
    '<div class="card"><h4 style="margin-bottom:10px;font-size:14px">Add routing rule</h4><div class="grid3">' +
    '<div class="fld"><label>Code</label><input id="rr_code" placeholder="MACHINE-NORTH"></div>' +
    '<div class="fld"><label>Category</label><select id="rr_category">' + catOpts + '</select></div>' +
    '<div class="fld"><label>Sub-Category (optional)</label><select id="rr_subcategory">' + subcatOpts + '</select></div>' +
    '<div class="fld"><label>District (optional)</label><select id="rr_district">' + distOpts + '</select></div>' +
    '<div class="fld"><label>Zone (optional)</label><select id="rr_zone">' + zoneOpts + '</select></div>' +
    '<div></div>' +
    levelFields +
    '<div class="fld" style="display:flex;align-items:flex-end"><button class="btn" onclick="adminCreateRoutingRule()">Add rule</button></div>' +
    '</div></div>';
}

function adminCreateRoutingRule() {
  var code = gv('rr_code'), category = document.getElementById('rr_category').value;
  var subcategory = document.getElementById('rr_subcategory').value;
  var district = document.getElementById('rr_district').value;
  var zone = document.getElementById('rr_zone').value;
  if (!code) return toast('Code is required');
  var body = {
    code: code, category_code: category, subcategory_code: subcategory || undefined,
    district_id: district ? +district : undefined, zone_id: zone ? +zone : undefined,
  };
  [1, 2, 3, 4].forEach(function (n) {
    body['l' + n + '_username'] = gv('rr_l' + n + '_user') || undefined;
    body['l' + n + '_role'] = gv('rr_l' + n + '_role') || undefined;
    body['l' + n + '_team_code'] = gv('rr_l' + n + '_team') || undefined;
  });
  api('POST', '/admin/routing-rules', body).then(function () { toast('Routing rule added'); loadAdminRoutingRules(); })
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
    api('GET', '/admin/sync/status').then(function (s) {
      ADMIN_SYNC_STATUS = s;
      ADMIN_LOADED.hierarchysource = true;
      if (ADMIN_TAB === 'hierarchysource') render();
    });
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
    '</div>' +

    '<div class="card" style="margin-bottom:14px"><h4 style="margin-bottom:4px;font-size:15px">Vehicle &amp; Employee Lookup</h4>' +
    '<div class="muted" style="margin-bottom:10px">Same external system and auth above, two more read-only endpoints on it. Register Call uses these to auto-fill Segment Number/Secretariat/Village from the selected MMU vehicle, and Designation/Employee ID from a searched employee. Leave a URL blank to keep those fields manual-entry only - a ticket is never blocked on either lookup. Checked only on a cache miss once Master-Data Sync below is populated.</div>' +
    '<div class="grid2">' +
    '<div class="fld"><label>Vehicle lookup URL</label><input id="hc_vehicle_url" value="' + esc(cfg.vehicle_lookup_url || '') + '" placeholder="https://hr.example.org/api/vehicles"></div>' +
    '<div class="fld"><label>Employee lookup URL</label><input id="hc_employee_url" value="' + esc(cfg.employee_lookup_url || '') + '" placeholder="https://hr.example.org/api/employees"></div>' +
    '</div>' +
    '<div style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap">' +
    '<button class="btn" onclick="adminSaveLookupConfig()">Save</button>' +
    (cfg.vehicle_lookup_url ? '<button class="btn o" onclick="adminTestLookupApi(\'vehicle\')">Test vehicle lookup</button>' : '') +
    (cfg.employee_lookup_url ? '<button class="btn o" onclick="adminTestLookupApi(\'employee\')">Test employee lookup</button>' : '') +
    '</div><div id="hc_lookup_test_result" class="muted" style="margin-top:8px"></div>' +
    '</div>' +

    _viewSyncCard(cfg);
}

function _viewSyncCard(cfg) {
  var jobLabels = { vehicles: 'Vehicle roster', employees: 'Employee roster', hierarchy: 'Hierarchy roster' };
  var status = ADMIN_SYNC_STATUS || {};
  var rows = Object.keys(jobLabels).map(function (job) {
    var s = status[job] || {};
    var pill = !s.status ? '<span class="pill p-mut">Never run</span>' :
      s.status === 'SUCCESS' ? '<span class="pill p-ok">OK</span>' : '<span class="pill p-warn">Error</span>';
    var age = s.age_minutes != null ? (s.age_minutes + ' min ago') : '—';
    return '<tr><td>' + jobLabels[job] + '</td><td>' + pill + '</td>' +
      '<td>' + (s.rows_upserted != null ? s.rows_upserted : '—') + '</td>' +
      '<td>' + age + '</td>' +
      '<td style="max-width:280px;white-space:normal">' + esc(s.error_message || '') + '</td></tr>';
  }).join('');
  return '<div class="card"><h4 style="margin-bottom:4px;font-size:15px">Master-Data Sync</h4>' +
    '<div class="muted" style="margin-bottom:10px">Polls three more read-only endpoints on the same external system every few minutes into a local cache (vehicle roster, employee roster, and the employee-to-role hierarchy used by Routing Rules\' API-role mapping), so Register Call\'s lookups and L1-L4 role resolution don\'t depend on a live call per ticket. Off by default - existing single-item lookups above keep working unchanged either way.</div>' +
    '<div class="grid3">' +
    '<div class="fld"><label>Vehicle roster URL</label><input id="hc_vroster_url" value="' + esc(cfg.vehicle_roster_url || '') + '" placeholder="https://hr.example.org/api/vehicles/all"></div>' +
    '<div class="fld"><label>Employee roster URL</label><input id="hc_eroster_url" value="' + esc(cfg.employee_roster_url || '') + '" placeholder="https://hr.example.org/api/employees/all"></div>' +
    '<div class="fld"><label>Hierarchy roster URL</label><input id="hc_hroster_url" value="' + esc(cfg.hierarchy_roster_url || '') + '" placeholder="https://hr.example.org/api/hierarchy/all"></div>' +
    '</div>' +
    '<div class="fld" style="max-width:260px;margin-top:4px"><label><input type="checkbox" id="hc_sync_enabled"' + (cfg.sync_enabled ? ' checked' : '') + '> Sync automatically every few minutes</label></div>' +
    '<div style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap">' +
    '<button class="btn" onclick="adminSaveSyncConfig()">Save</button>' +
    '<button class="btn o" onclick="adminRunSyncNow()">Sync now</button>' +
    '</div>' +
    '<div style="overflow-x:auto;margin-top:12px"><table><thead><tr><th>Job</th><th>Last result</th><th>Rows</th><th>When</th><th>Error</th></tr></thead><tbody>' + rows + '</tbody></table></div>' +
    '</div>';
}
function adminSaveSyncConfig() {
  var patch = {
    vehicle_roster_url: gv('hc_vroster_url') || '', employee_roster_url: gv('hc_eroster_url') || '',
    hierarchy_roster_url: gv('hc_hroster_url') || '', sync_enabled: document.getElementById('hc_sync_enabled').checked,
  };
  api('PUT', '/admin/hierarchy/config', patch).then(function () { toast('Saved'); loadAdminHierarchyConfig(); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}
function adminRunSyncNow() {
  toast('Syncing…');
  api('POST', '/admin/sync/run', {}).then(function () { toast('Sync complete'); loadAdminHierarchyConfig(); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Sync failed'); });
}
function adminSaveLookupConfig() {
  var patch = { vehicle_lookup_url: gv('hc_vehicle_url') || '', employee_lookup_url: gv('hc_employee_url') || '' };
  api('PUT', '/admin/hierarchy/config', patch).then(function () { toast('Saved'); loadAdminHierarchyConfig(); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}
function adminTestLookupApi(kind) {
  document.getElementById('hc_lookup_test_result').textContent = 'Testing…';
  api('POST', '/admin/hierarchy/test-' + kind + '-lookup', {}).then(function (r) {
    document.getElementById('hc_lookup_test_result').textContent = r.ok ?
      ('✅ Reachable (status ' + r.status_code + ', ' + r.elapsed_ms + 'ms)') :
      ('❌ ' + (r.error || ('status ' + r.status_code)) + ' (' + r.elapsed_ms + 'ms)');
  }).catch(function (e) { document.getElementById('hc_lookup_test_result').textContent = typeof e === 'string' ? e : 'Test failed'; });
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
