var API = '/cccapi', TOK = sessionStorage.getItem('ccc_tok') || '', ME = null, META = null, TAB = 'queue', ROWS = [], ROWTOTAL = 0, DASH = null,
  FILT = { status: 'open', scope: '', priority: '', category: '', mmu_vehicle: '', district: '', date_from: '', date_to: '', q: '', page: 1, page_size: 50, sort_by: '', sort_desc: false },
  NOTIFS = [], NOTIF_OPEN = false, POLL_TIMER = null, CLOCK_TIMER = null,
  ADMIN_TAB = 'teams', ADMIN_TEAMS = [], ADMIN_CATEGORIES = [], ADMIN_SLA = null, ADMIN_DISPATCH = null, ADMIN_USERS = [], ADMIN_USERS_Q = '', ADMIN_ROLES = [], ADMIN_AUDIT = [], ADMIN_LOADED = {},
  ADMIN_DISTRICTS = [], ADMIN_ZONES = [], ADMIN_MANDALS = [], ADMIN_VEHICLES = [], ADMIN_REASONS = [], ADMIN_MACHINES = [],
  LT_CATEGORIES = [], LT_REASONS = [], LT_SELECTED_REASONS = [], LT_MACHINE_RESULTS = [], LT_TICKETS = [];
function esc(s) { return (s == null ? '' : String(s)).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
function api(m, p, b) {
  var h = { 'Content-Type': 'application/json' }; if (TOK) h.Authorization = 'Bearer ' + TOK;
  return fetch(API + p, { method: m, headers: h, body: b ? JSON.stringify(b) : undefined }).then(function (r) {
    if (r.status === 401) { logout(); throw 'auth'; }
    return r.json().then(function (d) { if (!r.ok) throw (d.detail || ('HTTP ' + r.status)); return d; });
  });
}
function toast(m) { var t = document.createElement('div'); t.className = 'toast'; t.textContent = m; document.body.appendChild(t); setTimeout(function () { t.style.transition = 'all 0.3s ease'; t.style.opacity = '0'; t.style.transform = 'translateX(-50%) translateY(20px)'; setTimeout(function () { t.remove(); }, 300); }, 3000); }
/* Reusable second-layer modal (stacks above #modal, e.g. an Admin Portal
   edit while nothing else is open) - replaces window.prompt() with a proper
   in-app form pre-filled with the record's current values, matching the
   same .ovl/.sheet/.sh/.sb shell the ticket-detail modal already uses. */
function openModal2(html) { document.getElementById('modal2').innerHTML = html; }
function closeModal2() { document.getElementById('modal2').innerHTML = ''; }
function editModal(title, fieldsHtml, onSave) {
  openModal2('<div class="ovl" onclick="if(event.target===this)closeModal2()"><div class="sheet" style="max-width:460px">' +
    '<div class="sh"><div style="font-size:16px;font-weight:800">' + esc(title) + '</div>' +
    '<button class="x" onclick="closeModal2()" aria-label="Close">&times;</button></div>' +
    '<div class="sb">' + fieldsHtml +
    '<div style="display:flex;gap:10px;justify-content:flex-end;margin-top:6px">' +
    '<button class="btn o sm" onclick="closeModal2()">Cancel</button>' +
    '<button class="btn sm" id="em_save_btn">Save</button>' +
    '</div></div></div></div>');
  document.getElementById('em_save_btn').onclick = onSave;
  setTimeout(function () { var first = document.querySelector('#modal2 input,#modal2 select'); if (first) first.focus(); }, 50);
}
function doLogin() {
  var u = document.getElementById('u').value.trim(), p = document.getElementById('p').value;
  document.getElementById('lerr').textContent = '';
  api('POST', '/auth', { username: u, password: p }).then(function (d) { TOK = d.token; ME = d.user; sessionStorage.setItem('ccc_tok', TOK); sessionStorage.setItem('ccc_me', JSON.stringify(d.user)); boot(); })
    .catch(function (e) { document.getElementById('lerr').textContent = (e === 'auth' ? '' : (e || 'Login failed')); });
}
function logout() { TOK = ''; ME = null; TAB = 'queue'; sessionStorage.clear(); if (POLL_TIMER) clearInterval(POLL_TIMER); if (CLOCK_TIMER) clearInterval(CLOCK_TIMER); var _u = document.getElementById('u'), _p = document.getElementById('p'), _e = document.getElementById('lerr'); if (_u) _u.value = ''; if (_p) _p.value = ''; if (_e) _e.textContent = ''; document.getElementById('app').classList.add('hide'); document.getElementById('login').classList.remove('hide'); }
function roleLabel(r) {
  return ({
    CC_MANAGER: 'Global Team Executive',
    CALL_TAKER: 'Call Taker',
    SERVICE: 'Service Engineer',
    APPLICATION: 'Application Person',
    QUALITY: 'Quality Person',
    TECHNICAL: 'Technical Team',
    NETWORK: 'Network Team',
    FIELD_OPS: 'Field Operations',
    FLEET: 'Fleet Team',
    LT: 'Lab Technician'
  })[r] || r;
}
function tickClock() {
  if (TAB === 'queue') {
    var act = document.activeElement;
    var isTyping = act && (act.tagName === 'INPUT' || act.tagName === 'TEXTAREA' || act.tagName === 'SELECT');
    if (!isTyping) updateQueueTableOnly();
  }
}
function setFilt(k, v) {
  TAB = 'queue';
  FILT[k] = v;
  if (k === 'status') FILT.scope = '';
  FILT.page = 1;
  render();
  load(true);
}
function boot() {
  document.getElementById('login').classList.add('hide'); document.getElementById('app').classList.remove('hide');
  try { ME = ME || JSON.parse(sessionStorage.getItem('ccc_me')); } catch (e) { }
  if (ME) {
    document.getElementById('who').innerHTML = '<b>' + esc(ME.name) + '</b>' + esc(roleLabel(ME.role));
    if (ME.role === 'LT') TAB = 'report';
  }
  api('GET', '/meta').then(function (m) { META = m; render(); load(); loadNotifs(); startPolling(); });
}
function startPolling() {
  if (POLL_TIMER) clearInterval(POLL_TIMER);
  if (CLOCK_TIMER) clearInterval(CLOCK_TIMER);
  POLL_TIMER = setInterval(function () { load(); loadNotifs(); }, 18000);
  CLOCK_TIMER = setInterval(tickClock, 30000);
}
var NAV_EXPANDED = { queue: true, admin: true };

function toggleNavGroup(k) {
  NAV_EXPANDED[k] = !NAV_EXPANDED[k];
  renderNavTree();
}

function toggleSidebar() {
  var sb = document.getElementById('sidebar');
  if (sb) sb.classList.toggle('show');
}

function setQueueStatus(st) {
  TAB = 'queue';
  FILT.status = st;
  FILT.scope = '';
  FILT.page = 1;
  NAV_EXPANDED.queue = true;
  render();
  load(true);
}

function setQueueScope(sc) {
  TAB = 'queue';
  FILT.status = 'open';
  FILT.scope = sc;
  FILT.page = 1;
  NAV_EXPANDED.queue = true;
  render();
  load(true);
}

function renderNavTree() {
  var el = document.getElementById('nav_tree');
  if (!el || !ME) return;
  var html = '';

  // 1. Ticket Queue (Parent with sub-filters)
  if (ME.role !== 'LT') {
    var isQueue = (TAB === 'queue');
    var isScope = function(sc) { return isQueue && FILT.scope === sc; };
    var isStatus = function(st) { return isQueue && !FILT.scope && FILT.status === st; };

    var qSubFilters = [
      { label: 'Open', icon: '🟢', active: isStatus('open'), onclick: "setQueueStatus('open')" },
      { label: 'All', icon: '⚪', active: isStatus(''), onclick: "setQueueStatus('')" },
      { label: 'Closed', icon: '🟣', active: isStatus('CLOSED'), onclick: "setQueueStatus('CLOSED')" },
      { label: 'TAT Breached', icon: '🚨', active: isScope('breach'), onclick: "setQueueScope('breach')" },
      { label: 'At Risk', icon: '⚠️', active: isScope('risk'), onclick: "setQueueScope('risk')" },
      { label: 'Critical', icon: '🔥', active: isScope('critical'), onclick: "setQueueScope('critical')" },
      { label: 'Escalated', icon: '⚡', active: isScope('escalated'), onclick: "setQueueScope('escalated')" },
      { label: 'Unassigned', icon: '👤', active: isScope('unassigned'), onclick: "setQueueScope('unassigned')" }
    ];

    html += '<div class="nav-group">' +
      '<div class="nav-parent ' + (NAV_EXPANDED.queue ? 'open ' : '') + (isQueue ? 'active-branch' : '') + '" onclick="toggleNavGroup(\'queue\')">' +
        '<div class="nav-parent-left"><span class="nav-parent-icon">🎫</span><span class="nav-parent-title">Ticket Queue</span></div>' +
        '<span class="nav-chevron">&#9654;</span>' +
      '</div>' +
      '<div class="nav-children' + (NAV_EXPANDED.queue ? '' : ' hide') + '">' +
        qSubFilters.map(function(item) {
          return '<div class="nav-subitem' + (item.active ? ' on' : '') + '" onclick="' + item.onclick + '">' +
            '<span class="nav-subitem-icon">' + item.icon + '</span><span>' + esc(item.label) + '</span>' +
          '</div>';
        }).join('') +
      '</div>' +
    '</div>';
  }

  // 2. Register Call (Parent item)
  if (ME.role === 'CALL_TAKER' || ME.role === 'CC_MANAGER') {
    var isNew = (TAB === 'new');
    html += '<div class="nav-group">' +
      '<div class="nav-parent ' + (isNew ? 'active-branch' : '') + '" onclick="go(\'new\')">' +
        '<div class="nav-parent-left"><span class="nav-parent-icon">📞</span><span class="nav-parent-title">Register Call</span></div>' +
      '</div>' +
    '</div>';
  }

  // 3. Lab Tech Options (if LT)
  if (ME.role === 'LT') {
    html += '<div class="nav-group">' +
      '<div class="nav-parent ' + (TAB === 'report' ? 'active-branch' : '') + '" onclick="go(\'report\')">' +
        '<div class="nav-parent-left"><span class="nav-parent-icon">📝</span><span class="nav-parent-title">Report an Issue</span></div>' +
      '</div>' +
    '</div>';
    html += '<div class="nav-group">' +
      '<div class="nav-parent ' + (TAB === 'mine' ? 'active-branch' : '') + '" onclick="go(\'mine\')">' +
        '<div class="nav-parent-left"><span class="nav-parent-icon">🎫</span><span class="nav-parent-title">My Tickets</span></div>' +
      '</div>' +
    '</div>';
  }

  // 4. Daily Monitoring (Parent item)
  if (ME.role === 'CC_MANAGER') {
    var isDash = (TAB === 'dash');
    html += '<div class="nav-group">' +
      '<div class="nav-parent ' + (isDash ? 'active-branch' : '') + '" onclick="go(\'dash\')">' +
        '<div class="nav-parent-left"><span class="nav-parent-icon">📊</span><span class="nav-parent-title">Daily Monitoring</span></div>' +
      '</div>' +
    '</div>';
  }

  // 5. Routing Matrix (Parent item)
  if (ME.role !== 'LT') {
    var isMatrix = (TAB === 'matrix');
    html += '<div class="nav-group">' +
      '<div class="nav-parent ' + (isMatrix ? 'active-branch' : '') + '" onclick="go(\'matrix\')">' +
        '<div class="nav-parent-left"><span class="nav-parent-icon">🔀</span><span class="nav-parent-title">Routing Matrix</span></div>' +
      '</div>' +
    '</div>';
  }

  // 6. Admin Portal (Parent with sub-fields)
  if (ME.role === 'CC_MANAGER') {
    var isAdmin = (TAB === 'admin');
    var aItems = [
      { id: 'teams', label: 'Teams', icon: '🏢' },
      { id: 'categories', label: 'Categories', icon: '🏷️' },
      { id: 'geo', label: 'Geography', icon: '🗺️' },
      { id: 'vehicles', label: 'Vehicles', icon: '🚐' },
      { id: 'reasons', label: 'LT Reasons', icon: '⚠️' },
      { id: 'machines', label: 'Machines', icon: '🔬' },
      { id: 'sla', label: 'SLA & TAT', icon: '⏱️' },
      { id: 'users', label: 'Users', icon: '👥' },
      { id: 'audit', label: 'Audit Log', icon: '📜' }
    ];
    html += '<div class="nav-group">' +
      '<div class="nav-parent ' + (NAV_EXPANDED.admin ? 'open ' : '') + (isAdmin ? 'active-branch' : '') + '" onclick="toggleNavGroup(\'admin\')">' +
        '<div class="nav-parent-left"><span class="nav-parent-icon">⚙️</span><span class="nav-parent-title">Admin Portal</span></div>' +
        '<span class="nav-chevron">&#9654;</span>' +
      '</div>' +
      '<div class="nav-children' + (NAV_EXPANDED.admin ? '' : ' hide') + '">' +
        aItems.map(function(item) {
          var on = (TAB === 'admin' && ADMIN_TAB === item.id) ? ' on' : '';
          return '<div class="nav-subitem' + on + '" onclick="goAdminItem(\'' + item.id + '\')">' +
            '<span class="nav-subitem-icon">' + item.icon + '</span><span>' + esc(item.label) + '</span>' +
          '</div>';
        }).join('') +
      '</div>' +
    '</div>';
  }

  el.innerHTML = html;
}

function goAdminItem(subTab) {
  TAB = 'admin';
  ADMIN_TAB = subTab;
  NAV_EXPANDED.admin = true;
  render();
  loadAdminSection(subTab);
}

function render() {
  renderNavTree();
  var b = document.getElementById('body');
  if (ME.role === 'LT') {
    if (TAB === 'mine') b.innerHTML = viewLTMine();
    else { b.innerHTML = viewLTReport(); setTimeout(loadLTCategories, 0); }
    return;
  }
  if (TAB === 'new') { b.innerHTML = viewNew(); setTimeout(function () { previewRoute(); loadNewCallGeo(); }, 0); }
  else if (TAB === 'dash') b.innerHTML = viewDash();
  else if (TAB === 'matrix') b.innerHTML = viewMatrix();
  else if (TAB === 'admin') b.innerHTML = viewAdmin();
  else b.innerHTML = viewQueue();
}
function go(t) { TAB = t; render(); load(); if (t === 'admin') loadAdminSection(ADMIN_TAB); }
function queueQS() {
  var keys = ['status', 'scope', 'priority', 'category', 'mmu_vehicle', 'district', 'date_from', 'date_to', 'page', 'page_size', 'sort_by', 'sort_desc'];
  return keys.map(function (k) { return k + '=' + encodeURIComponent(FILT[k] || (k === 'sort_desc' ? false : '')); }).join('&') + '&q_=' + encodeURIComponent(FILT.q || '');
}
function load(forced) {
  if (ME.role === 'LT') { if (TAB === 'mine') loadLTMine(); return; }
  if (TAB === 'queue') {
    api('GET', '/tickets?' + queueQS()).then(function (d) {
      ROWS = d.rows || []; ROWTOTAL = d.total || 0;
      var act = document.activeElement;
      var isTyping = act && (act.tagName === 'INPUT' || act.tagName === 'TEXTAREA' || act.tagName === 'SELECT');
      if (forced || !isTyping) {
        render();
      } else {
        updateQueueTableOnly();
      }
    });
  }
  if (TAB === 'dash') { api('GET', '/dashboard').then(function (d) { DASH = d; render(); }); }
}
function setFilt(k, v) { FILT[k] = v; FILT.page = 1; load(true); }
function gotoPage(p) { if (p < 1) return; FILT.page = p; load(true); }

/* ---------- queue ---------- */
function parseDT(s) { if (!s) return null; var p = s.split(/[- :]/); return new Date(+p[0], +p[1] - 1, +p[2], +p[3] || 0, +p[4] || 0, 0); }
function computeTier(dueAt, tatMins) {
  var d = parseDT(dueAt); if (!d) return null; var mins = (d.getTime() - Date.now()) / 60000;
  var sla = (META && META.sla) || { at_risk_minutes: 60, at_risk_fraction: .2, critical_minutes: 15, critical_fraction: .05 };
  var tm = tatMins || 240;
  if (mins < 0) return { state: 'BREACHED', mins: mins };
  if (mins <= Math.max(sla.critical_minutes, tm * sla.critical_fraction)) return { state: 'CRITICAL', mins: mins };
  if (mins <= Math.max(sla.at_risk_minutes, tm * sla.at_risk_fraction)) return { state: 'AT RISK', mins: mins };
  return { state: 'ON TRACK', mins: mins };
}
function tickClock() {
  if (TAB !== 'queue' || !ROWS.length) return;
  ROWS.forEach(function (t) { if (t.status === 'CLOSED') return; var r = computeTier(t.due_at, t.tat_mins); if (r) { t.tat_state = r.state; t.mins_left = Math.round(r.mins); } });
  var act = document.activeElement;
  var isTyping = act && (act.tagName === 'INPUT' || act.tagName === 'TEXTAREA' || act.tagName === 'SELECT');
  if (!isTyping) render();
  else updateQueueTableOnly();
}
function tatPill(t) {
  var s = t.tat_state; var k = s === 'BREACHED' ? 'p-crit' : (s === 'CRITICAL' ? 'p-critical' : (s === 'AT RISK' ? 'p-warn' : (s === 'MET' || s === 'ON TRACK' ? 'p-ok' : 'p-mut')));
  var extra = (t.mins_left != null && t.status !== 'CLOSED') ? (' · ' + (t.mins_left < 0 ? ('+' + Math.abs(t.mins_left)) : t.mins_left) + 'm') : '';
  return '<span class="pill ' + k + '">' + esc(s) + extra + '</span>';
}
function gv(i) { var e = document.getElementById(i); return e ? e.value.trim() : ''; }
function applyFilters() {
  FILT.mmu_vehicle = gv('qf_veh'); FILT.district = gv('qf_dist'); FILT.q = gv('qf_q');
  FILT.priority = gv('qf_pri'); FILT.category = gv('qf_cat'); FILT.date_from = gv('qf_from'); FILT.date_to = gv('qf_to'); FILT.page = 1; load(true);
}
function clearFilters() { FILT.mmu_vehicle = ''; FILT.district = ''; FILT.q = ''; FILT.priority = ''; FILT.category = ''; FILT.date_from = ''; FILT.date_to = ''; FILT.page = 1; load(true); render(); }
function downloadExcel(path, filename) {
  var h = { 'Accept': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' };
  if (TOK) h.Authorization = 'Bearer ' + TOK;
  toast('Generating export...');
  fetch(API + path, { method: 'GET', headers: h }).then(function(r) {
    if (!r.ok) { toast('Export failed: HTTP ' + r.status); return; }
    r.blob().then(function(b) {
      var a = document.createElement('a');
      a.href = window.URL.createObjectURL(b);
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
    });
  }).catch(function() { toast('Export failed'); });
}
function exportQueue() {
  downloadExcel('/reports/tickets.xlsx?' + queueQS(), 'Tickets_Export.xlsx');
}
function updateQueueTableOnly() {
  var tb = document.querySelector('#queue_table_wrap tbody');
  if (!tb) return;
  if (!ROWS.length) {
    tb.innerHTML = '<tr><td colspan="8" class="empty">No tickets in this view.</td></tr>';
    return;
  }
  tb.innerHTML = ROWS.map(function (t) {
    return '<tr class="row" onclick="openT(' + t.id + ')">' +
      '<td><b>' + esc(t.ticket_no) + '</b><div class="muted">' + esc(t.source) + '</div></td>' +
      '<td>' + esc(t.mmu_vehicle || '—') + '<div class="muted">' + esc(t.district || '') + '</div></td>' +
      '<td>' + esc(t.category_label || '') + '</td>' +
      '<td><span class="pill p-' + esc(t.priority) + '">' + esc(t.priority) + '</span>' + (t.vip ? ' <span class="pill p-crit">VIP</span>' : '') + '</td>' +
      '<td>' + esc(t.team_label || '') + '</td>' +
      '<td><span class="pill p-mut">' + esc((t.status || '').replace(/_/g, ' ')) + '</span>' + (t.escalated ? ' <span class="pill p-crit">ESC</span>' : '') + '</td>' +
      '<td>' + tatPill(t) + '<div class="muted">' + esc(t.due_at || '') + '</div></td>' +
      '<td style="max-width:280px">' + esc((t.problem || '').slice(0, 90)) + '</td></tr>';
  }).join('');
}
function sortQueue(col) {
  if (FILT.sort_by === col) {
    FILT.sort_desc = !FILT.sort_desc;
  } else {
    FILT.sort_by = col;
    FILT.sort_desc = false;
  }
  FILT.page = 1;
  load(true);
}
function viewQueue() {
  var filterTitle = 'All Tickets';
  if (FILT.scope === 'breach') filterTitle = 'TAT Breached Tickets';
  else if (FILT.scope === 'risk') filterTitle = 'At Risk Tickets';
  else if (FILT.scope === 'critical') filterTitle = 'Critical Priority Tickets';
  else if (FILT.scope === 'escalated') filterTitle = 'Escalated Tickets';
  else if (FILT.scope === 'unassigned') filterTitle = 'Unassigned Tickets';
  else if (FILT.status === 'open') filterTitle = 'Open Tickets';
  else if (FILT.status === 'CLOSED') filterTitle = 'Closed Tickets';

  var cats = (META && META.routing) ? '<option value="">Any category</option>' + Object.keys(META.routing).map(function (k) { return '<option value="' + k + '"' + (FILT.category === k ? ' selected' : '') + '>' + esc(META.routing[k].label) + '</option>'; }).join('') : '';
  var pris = (META && META.priority) ? '<option value="">Any priority</option>' + Object.keys(META.priority).map(function (k) { return '<option value="' + k + '"' + (FILT.priority === k ? ' selected' : '') + '>' + k + '</option>'; }).join('') : '';
  
  var bar = '<div class="card" style="margin-bottom:14px">' +
    '<div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;margin-bottom:14px">' +
      '<div>' +
        '<div style="font-size:16px;font-weight:800;color:var(--ink)">📋 ' + esc(filterTitle) + '</div>' +
        '<div style="font-size:12.5px;color:var(--ink2);margin-top:2px">Filter and search tickets by MMU, district, category, and date</div>' +
      '</div>' +
      '<div style="display:flex;gap:8px;align-items:center;">' +
        '<div style="font-size:13px;font-weight:700;background:rgba(99,32,238,0.08);color:var(--pur);padding:5px 12px;border-radius:20px">' +
          ROWTOTAL + ' ticket' + (ROWTOTAL === 1 ? '' : 's') +
        '</div>' +
      '</div>' +
    '</div>' +
    '<div class="grid3">' +
      '<div class="fld"><label>Vehicle</label><input id="qf_veh" value="' + esc(FILT.mmu_vehicle) + '" placeholder="e.g. AP39..." onkeydown="if(event.key===\'Enter\')applyFilters()"></div>' +
      '<div class="fld"><label>District</label><input id="qf_dist" value="' + esc(FILT.district) + '" placeholder="District name" onkeydown="if(event.key===\'Enter\')applyFilters()"></div>' +
      '<div class="fld"><label>Keyword</label><input id="qf_q" value="' + esc(FILT.q) + '" placeholder="ticket / problem text" onkeydown="if(event.key===\'Enter\')applyFilters()"></div>' +
      '<div class="fld"><label>Priority</label><select id="qf_pri">' + pris + '</select></div>' +
      '<div class="fld"><label>Category</label><select id="qf_cat">' + cats + '</select></div>' +
      '<div class="fld"><label>Created from</label><input id="qf_from" type="date" value="' + esc(FILT.date_from) + '"></div>' +
      '<div class="fld"><label>Created to</label><input id="qf_to" type="date" value="' + esc(FILT.date_to) + '"></div>' +
      '<div class="fld" style="display:flex;align-items:flex-end;gap:8px"><button class="btn sm" onclick="applyFilters()">Apply Filters</button><button class="btn o sm" onclick="clearFilters()">Reset</button>' +
      '<button class="btn g sm" onclick="exportQueue()">Export to Excel</button></div>' +
    '</div>' +
  '</div>';
  if (!ROWS.length) return bar + '<div class="card" id="queue_table_wrap"><div class="empty">No tickets matching this view.</div></div>';
  var rows = ROWS.map(function (t) {
    return '<tr class="row" onclick="openT(' + t.id + ')">' +
      '<td><b>' + esc(t.ticket_no) + '</b><div class="muted">' + esc(t.source) + '</div></td>' +
      '<td>' + esc(t.mmu_vehicle || '—') + '<div class="muted">' + esc(t.district || '') + '</div></td>' +
      '<td>' + esc(t.category_label || '') + '</td>' +
      '<td><span class="pill p-' + esc(t.priority) + '">' + esc(t.priority) + '</span>' + (t.vip ? ' <span class="pill p-crit">VIP</span>' : '') + '</td>' +
      '<td>' + esc(t.team_label || '') + '</td>' +
      '<td><span class="pill p-mut">' + esc((t.status || '').replace(/_/g, ' ')) + '</span>' + (t.escalated ? ' <span class="pill p-crit">ESC</span>' : '') + '</td>' +
      '<td>' + tatPill(t) + '<div class="muted">' + esc(t.due_at || '') + '</div></td>' +
      '<td style="max-width:280px">' + esc((t.problem || '').slice(0, 90)) + '</td></tr>';
  }).join('');
  var pages = Math.max(1, Math.ceil(ROWTOTAL / FILT.page_size));
  var pager = '<div class="pager"><span>' + ROWTOTAL + ' ticket' + (ROWTOTAL === 1 ? '' : 's') + ' &middot; page ' + FILT.page + ' of ' + pages + '</span>' +
    '<button class="btn o sm" ' + (FILT.page <= 1 ? 'disabled' : '') + ' onclick="gotoPage(' + (FILT.page - 1) + ')">&larr; Prev</button>' +
    '<button class="btn o sm" ' + (FILT.page >= pages ? 'disabled' : '') + ' onclick="gotoPage(' + (FILT.page + 1) + ')">Next &rarr;</button></div>';
  
  var th_t = '<th onclick="sortQueue(\'ticket_no\')" style="cursor:pointer;user-select:none">Ticket ' + (FILT.sort_by === 'ticket_no' ? (FILT.sort_desc ? '&#8595;' : '&#8593;') : '&#8597;') + '</th>';
  var th_p = '<th onclick="sortQueue(\'priority\')" style="cursor:pointer;user-select:none">Pri ' + (FILT.sort_by === 'priority' ? (FILT.sort_desc ? '&#8595;' : '&#8593;') : '&#8597;') + '</th>';
  var th_d = '<th onclick="sortQueue(\'due_at\')" style="cursor:pointer;user-select:none">TAT ' + (FILT.sort_by === 'due_at' ? (FILT.sort_desc ? '&#8595;' : '&#8593;') : '&#8597;') + '</th>';
  
  return bar + '<div class="card" id="queue_table_wrap"><div style="overflow-x:auto"><table><thead><tr>' + th_t + '<th>MMU / District</th><th>Category</th>' + th_p + '<th>Team</th><th>Status</th>' + th_d + '<th>Problem</th></tr></thead><tbody>' + rows + '</tbody></table></div></div>' + pager;
}

var FORM_ACCORDION_OPEN = {
  geo: true,
  caller: true,
  equip: true,
  issue: true
};

function toggleFormAccordion(k) {
  FORM_ACCORDION_OPEN[k] = !FORM_ACCORDION_OPEN[k];
  var grp = document.getElementById('fa_' + k);
  if (grp) {
    grp.classList.toggle('active', FORM_ACCORDION_OPEN[k]);
    var b = grp.querySelector('.form-accordion-body');
    if (b) b.classList.toggle('hide', !FORM_ACCORDION_OPEN[k]);
  }
}

/* ---------- register call ---------- */
function viewNew() {
  var cats = Object.keys(META.routing).map(function (k) { return '<option value="' + k + '">' + esc(META.routing[k].label) + '</option>'; }).join('');
  var pri = Object.keys(META.priority).map(function (k) { return '<option value="' + k + '">' + k + ' — ' + esc(META.priority[k]) + '</option>'; }).join('');
  
  return '<div class="card" style="margin-bottom:18px"><h3 style="margin-bottom:4px">Register a Toll-Free Breakdown Call</h3>' +
    '<div class="muted">SOP §4 — complete required fields below. Click any section on the left to expand or collapse sub-fields.</div></div>' +

    // 1. Vehicle & Location
    '<div class="form-accordion-group ' + (FORM_ACCORDION_OPEN.geo ? 'active' : '') + '" id="fa_geo">' +
      '<div class="form-accordion-header" onclick="toggleFormAccordion(\'geo\')">' +
        '<div class="form-accordion-title"><span class="form-accordion-num">1</span><span>MMU Vehicle &amp; Location</span><span class="form-accordion-summary">— Vehicle No, District &amp; Mandal</span></div>' +
        '<span class="form-accordion-chevron">&#9654;</span>' +
      '</div>' +
      '<div class="form-accordion-body' + (FORM_ACCORDION_OPEN.geo ? '' : ' hide') + '">' +
        '<div class="grid2">' +
          '<div class="fld"><label>MMU / Vehicle number *</label><div style="position:relative"><input id="f_veh" placeholder="Search MMU (e.g. AP39...)" oninput="vehicleSearchInput()" onfocus="showVehDropdown()" onblur="hideVehDropdown(event)" autocomplete="off" style="width:100%"><div id="veh_dropdown" class="hide" style="position:absolute;top:100%;left:0;right:0;max-height:200px;overflow-y:auto;background:var(--card);border:1px solid var(--line);border-radius:8px;z-index:100;box-shadow:0 10px 25px rgba(0,0,0,0.05);padding:4px"></div><input type="hidden" id="f_vehicle_id"></div></div>' +
          '<div class="fld"><label>District</label><select id="f_district_id" onchange="districtChanged()"><option value="">Loading…</option></select></div>' +
          '<div class="fld"><label>Mandal</label><select id="f_mandal_id"><option value="">Select district first</option></select></div>' +
          '<div class="fld"><label>Specific Location / Village</label><input id="f_loc" placeholder="Village / Landmark / PHC"></div>' +
        '</div>' +
      '</div>' +
    '</div>' +

    // 2. Caller Details
    '<div class="form-accordion-group ' + (FORM_ACCORDION_OPEN.caller ? 'active' : '') + '" id="fa_caller">' +
      '<div class="form-accordion-header" onclick="toggleFormAccordion(\'caller\')">' +
        '<div class="form-accordion-title"><span class="form-accordion-num">2</span><span>Caller &amp; Reporter Information</span><span class="form-accordion-summary">— Name &amp; Contact</span></div>' +
        '<span class="form-accordion-chevron">&#9654;</span>' +
      '</div>' +
      '<div class="form-accordion-body' + (FORM_ACCORDION_OPEN.caller ? '' : ' hide') + '">' +
        '<div class="grid2">' +
          '<div class="fld"><label>Caller name</label><input id="f_cname" placeholder="Dr. / Staff name"></div>' +
          '<div class="fld"><label>Caller contact</label><input id="f_cph" placeholder="10-digit mobile number"></div>' +
        '</div>' +
        '<div class="fld" style="display:flex;align-items:center;gap:8px;margin-top:8px;margin-bottom:0"><input type="checkbox" id="rc_is_lt" style="width:auto" onchange="ltCallerToggled()"> ' +
        '<label style="margin:0;text-transform:none;font-size:13px;font-weight:600;color:var(--ink2)">Caller is a Lab Technician reporting a field issue</label></div>' +
        '<div id="rc_lt_block" class="hide" style="margin-top:12px">' +
          '<div class="fld"><label>Already reported through the LT portal?</label>' +
          '<select id="rc_lt_already" onchange="ltAlreadyChanged()"><option value="no">No — register as a new call below</option><option value="yes">Yes — link this call to the existing ticket</option></select></div>' +
          '<div id="rc_lt_lookup" class="hide"><div class="grid3">' +
          '<div class="fld"><label>Portal ticket number</label><input id="rc_lt_ticketno" placeholder="CCC-20260828-0001"></div>' +
          '<div class="fld" style="display:flex;align-items:flex-end"><button class="btn o sm" onclick="lookupPortalTicket()">Look up</button></div>' +
          '</div><div id="rc_lt_result"></div></div>' +
        '</div>' +
      '</div>' +
    '</div>' +

    // 3. Equipment & Diagnostics
    '<div class="form-accordion-group ' + (FORM_ACCORDION_OPEN.equip ? 'active' : '') + '" id="fa_equip">' +
      '<div class="form-accordion-header" onclick="toggleFormAccordion(\'equip\')">' +
        '<div class="form-accordion-title"><span class="form-accordion-num">3</span><span>Equipment &amp; Diagnostic Details</span><span class="form-accordion-summary">— Machine &amp; Error</span></div>' +
        '<span class="form-accordion-chevron">&#9654;</span>' +
      '</div>' +
      '<div class="form-accordion-body' + (FORM_ACCORDION_OPEN.equip ? '' : ' hide') + '">' +
        '<div class="grid3">' +
          '<div class="fld"><label>Equipment / machine</label><input id="f_eq" list="machListDL" placeholder="Start typing…" oninput="equipmentSearchInput()" autocomplete="off"><datalist id="machListDL"></datalist><input type="hidden" id="f_machine_id"></div>' +
          '<div class="fld"><label>Error message / code</label><input id="f_err" placeholder="e.g. ERR-OPT-01"></div>' +
          '<div class="fld"><label>Operational impact</label><input id="f_imp" placeholder="MMU stopped / partial / none"></div>' +
        '</div>' +
      '</div>' +
    '</div>' +

    // 4. Issue Description & SLA Routing
    '<div class="form-accordion-group ' + (FORM_ACCORDION_OPEN.issue ? 'active' : '') + '" id="fa_issue">' +
      '<div class="form-accordion-header" onclick="toggleFormAccordion(\'issue\')">' +
        '<div class="form-accordion-title"><span class="form-accordion-num">4</span><span>Problem Statement &amp; SLA Routing</span><span class="form-accordion-summary">— Category &amp; Priority</span></div>' +
        '<span class="form-accordion-chevron">&#9654;</span>' +
      '</div>' +
      '<div class="form-accordion-body' + (FORM_ACCORDION_OPEN.issue ? '' : ' hide') + '">' +
        '<div class="fld"><label>Nature of the problem *</label><textarea id="f_prob" rows="3" placeholder="What exactly is happening?"></textarea></div>' +
        '<div class="grid2">' +
          '<div class="fld"><label>Priority level *</label><select id="f_pri">' + pri + '</select></div>' +
          '<div class="fld"><label>Issue category *</label><select id="f_cat" onchange="previewRoute()">' + cats + '</select></div>' +
        '</div>' +
        '<div class="route" id="rpre" style="margin-top:10px"></div>' +
      '</div>' +
    '</div>' +

    '<div style="display:flex;gap:12px;margin-top:16px">' +
      '<button class="btn" style="min-width:220px" onclick="createT()">Create Ticket &amp; Route</button>' +
    '</div>';
}
function ltCallerToggled() {
  var on = document.getElementById('rc_is_lt').checked;
  document.getElementById('rc_lt_block').classList.toggle('hide', !on);
  if (!on) { document.getElementById('rc_lt_lookup').classList.add('hide'); document.getElementById('rc_lt_result').innerHTML = ''; document.getElementById('rc_lt_already').value = 'no'; }
}
function ltAlreadyChanged() {
  var yes = document.getElementById('rc_lt_already').value === 'yes';
  document.getElementById('rc_lt_lookup').classList.toggle('hide', !yes);
  if (!yes) document.getElementById('rc_lt_result').innerHTML = '';
}
function lookupPortalTicket() {
  var no = gv('rc_lt_ticketno');
  if (!no) return toast('Enter the portal ticket number');
  api('GET', '/ticket/by-number/' + encodeURIComponent(no)).then(function (t) {
    document.getElementById('rc_lt_result').innerHTML =
      '<div class="card" style="margin-top:10px"><b>' + esc(t.ticket_no) + '</b> &middot; ' + esc(t.team_label || t.team) + ' &middot; <span class="pill p-mut">' + esc((t.status || '').replace(/_/g, ' ')) + '</span>' +
      '<div class="muted" style="margin-top:6px">' + esc((t.problem || '').slice(0, 160)) + '</div>' +
      '<div class="fld" style="margin-top:10px"><label>Note about this call (optional)</label><input id="rc_lt_note" placeholder="e.g. caller asking for an update"></div>' +
      '<button class="btn g sm" onclick="logCallAgainstTicket(' + t.id + ')">Log this call against it — no new ticket</button></div>';
  }).catch(function (e) { toast(typeof e === 'string' ? e : 'Ticket not found'); document.getElementById('rc_lt_result').innerHTML = ''; });
}
function logCallAgainstTicket(id) {
  api('POST', '/ticket/' + id + '/log-call', { caller_name: gv('f_cname'), caller_phone: gv('f_cph'), note: gv('rc_lt_note') })
    .then(function (d) { toast('Call logged against ' + d.ticket_no); TAB = 'queue'; render(); load(); openT(id); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Could not log call'); });
}
function previewRoute() {
  var c = document.getElementById('f_cat').value, r = META.routing[c];
  document.getElementById('rpre').innerHTML = 'Routes to <b>' + esc(META.teams[r.team]) + '</b> &mdash; initial owner <b>' + esc(r.owner) + '</b>';
}
var NEW_DISTRICTS = [], VEH_DEBOUNCE = null, VEH_RESULTS = [];
function loadNewCallGeo() {
  api('GET', '/districts').then(function (rows) {
    NEW_DISTRICTS = rows;
    var sel = document.getElementById('f_district_id');
    if (sel) sel.innerHTML = '<option value="">Select district…</option>' + rows.map(function (d) { return '<option value="' + d.id + '">' + esc(d.name) + '</option>'; }).join('');
  }).catch(function () { });
}
function districtChanged() {
  var did = document.getElementById('f_district_id').value;
  var msel = document.getElementById('f_mandal_id');
  if (!msel) return;
  if (!did) { msel.innerHTML = '<option value="">Select district first</option>'; return; }
  msel.innerHTML = '<option value="">Loading…</option>';
  api('GET', '/mandals?district_id=' + did).then(function (rows) {
    msel.innerHTML = '<option value="">Select mandal…</option>' + rows.map(function (m) { return '<option value="' + m.id + '">' + esc(m.name) + '</option>'; }).join('');
  }).catch(function () { });
}
function vehicleSearchInput() {
  clearTimeout(VEH_DEBOUNCE);
  var q = document.getElementById('f_veh').value.trim();
  document.getElementById('f_vehicle_id').value = '';
  document.getElementById('veh_dropdown').classList.remove('hide');
  if (q.length < 2) {
    document.getElementById('veh_dropdown').innerHTML = '<div style="padding:8px;color:var(--mut)">Type at least 2 chars...</div>';
    return;
  }
  document.getElementById('veh_dropdown').innerHTML = '<div style="padding:8px;color:var(--mut)">Searching...</div>';
  VEH_DEBOUNCE = setTimeout(function () {
    api('GET', '/vehicles/search?q=' + encodeURIComponent(q)).then(function (rows) {
      VEH_RESULTS = rows;
      if (!rows.length) {
        document.getElementById('veh_dropdown').innerHTML = '<div style="padding:8px;color:var(--mut)">No matches found</div>';
        return;
      }
      document.getElementById('veh_dropdown').innerHTML = rows.map(function (v) { 
        return '<div class="dropdown-item" onmousedown="selectVeh(\'' + esc(v.registration_no) + '\', ' + v.id + ')" style="padding:8px;cursor:pointer;">' + esc(v.registration_no) + '</div>'; 
      }).join('');
    }).catch(function () { 
      document.getElementById('veh_dropdown').innerHTML = '<div style="padding:8px;color:var(--mut)">Error loading vehicles</div>';
    });
  }, 300);
}
function showVehDropdown() {
  document.getElementById('veh_dropdown').classList.remove('hide');
  vehicleSearchInput();
}
function hideVehDropdown(e) {
  setTimeout(function(){ 
    var dd = document.getElementById('veh_dropdown');
    if(dd) dd.classList.add('hide'); 
  }, 200);
}
function selectVeh(reg, id) {
  document.getElementById('f_veh').value = reg;
  document.getElementById('f_vehicle_id').value = id;
  document.getElementById('veh_dropdown').classList.add('hide');
}
var MACH_DEBOUNCE = null;
function equipmentSearchInput() {
  clearTimeout(MACH_DEBOUNCE);
  var q = document.getElementById('f_eq').value.trim();
  document.getElementById('f_machine_id').value = '';
  if (q.length < 1) return;
  MACH_DEBOUNCE = setTimeout(function () {
    api('GET', '/machines/search?q=' + encodeURIComponent(q)).then(function (rows) {
      document.getElementById('machListDL').innerHTML = rows.map(function (m) { return '<option value="' + esc(m.name) + '">'; }).join('');
      var exact = rows.find(function (m) { return m.name.toLowerCase() === q.toLowerCase(); });
      if (exact) document.getElementById('f_machine_id').value = exact.id;
    }).catch(function () { });
  }, 300);
}
function createT() {
  var g = function (i) { var e = document.getElementById(i); return e ? e.value.trim() : ''; };
  if (!g('f_prob')) return toast('Nature of the problem is required');
  var districtId = g('f_district_id'), mandalId = g('f_mandal_id'), vehicleId = g('f_vehicle_id'), machineId = g('f_machine_id');
  var districtName = districtId ? ((NEW_DISTRICTS.find(function (d) { return String(d.id) === districtId; }) || {}).name || '') : '';
  api('POST', '/ticket', {
    mmu_vehicle: g('f_veh'), vehicle_id: vehicleId ? +vehicleId : null, district: districtName,
    district_id: districtId ? +districtId : null, mandal_id: mandalId ? +mandalId : null, machine_id: machineId ? +machineId : null,
    location: g('f_loc'), caller_name: g('f_cname'),
    caller_phone: g('f_cph'), equipment: g('f_eq'), problem: g('f_prob'), error_code: g('f_err'), impact: g('f_imp'),
    category: g('f_cat'), priority: g('f_pri')
  })
    .then(function (d) { toast('Ticket ' + d.ticket_no + ' created → ' + d.team + (d.vip ? ' (VIP: bumped to P1)' : '')); TAB = 'queue'; render(); load(); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}

/* ---------- ticket detail ---------- */
var MODAL_TICK = null;
function openT(id) { api('GET', '/ticket/' + id).then(function (d) { renderT(d.ticket, d.events); loadAttachments(id); }); }
function closeT() { document.getElementById('modal').innerHTML = ''; if (MODAL_TICK) { clearInterval(MODAL_TICK); MODAL_TICK = null; } }
function reopenT(id) {
  var reason = prompt('Reason for reopening this ticket (required):'); if (reason === null) return; if (!reason.trim()) { toast('A reason is required to reopen'); return; }
  api('POST', '/ticket/action', { id: id, action: 'reopen', note: reason.trim() }).then(function () { toast('Ticket reopened'); closeT(); load(); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Reopen failed'); });
}
function updateModalCountdown(t) {
  var el = document.getElementById('modalTat'); if (!el) return;
  var r = computeTier(t.due_at, t.tat_mins); if (!r) return; t.tat_state = r.state; t.mins_left = Math.round(r.mins); el.outerHTML = tatPill(t).replace('<span ', '<span id="modalTat" ');
}
function row(k, v) { return v ? ('<div style="display:flex;gap:10px;padding:5px 0;border-bottom:1px solid #f4eff8"><div class="muted" style="min-width:130px">' + esc(k) + '</div><div>' + esc(v) + '</div></div>') : ''; }
function renderT(t, evs) {
  var mine = (ME.role === t.team) || ME.role === 'CC_MANAGER' || ME.role === 'CALL_TAKER';
  var A = [];
  if (mine) {
    if (t.status === 'NEW' || t.status === 'ASSIGNED') A.push('<button class="btn" onclick="act(' + t.id + ',\'acknowledge\')">Acknowledge</button>');
    if (t.status === 'ACKNOWLEDGED') A.push('<button class="btn" onclick="act(' + t.id + ',\'start\')">Start investigation</button>');
    if (t.status === 'PENDING') A.push('<button class="btn" onclick="act(' + t.id + ',\'start\')">Resume work</button>');
    if (['ACKNOWLEDGED', 'IN_PROGRESS', 'PENDING'].indexOf(t.status) >= 0) {
      A.push('<button class="btn o" onclick="act(' + t.id + ',\'update\')">Save update</button>');
      A.push('<button class="btn w" onclick="act(' + t.id + ',\'pending\')">Mark pending</button>');
      A.push('<button class="btn g" onclick="act(' + t.id + ',\'resolve\')">Resolve</button>');
    }
    if (t.status === 'RESOLVED') A.push('<button class="btn g" onclick="act(' + t.id + ',\'confirm\')">Confirm with MMU</button>');
    if (t.status === 'CLOSURE_CONFIRMATION') A.push('<button class="btn" onclick="act(' + t.id + ',\'close\')">Close ticket</button>');
    if (t.status !== 'CLOSED') A.push('<button class="btn r" onclick="act(' + t.id + ',\'escalate\')">Escalate to Global Team Executive</button>');
  }
  if ((ME.role === 'CC_MANAGER' || ME.role === 'CALL_TAKER') && t.status === 'CLOSED') {
    var closedDt = parseDT(t.closed_at), windowH = (META.sla && META.sla.reopen_window_hours) || 24;
    var withinWindow = closedDt ? ((Date.now() - closedDt.getTime()) / 3600000 <= windowH) : true;
    if (withinWindow) A.push('<button class="btn o" onclick="reopenT(' + t.id + ')">Reopen</button>');
    else A.push('<span class="muted">Reopen window (' + windowH + 'h) has passed - register a new ticket</span>');
  }
  var reroute = (ME.role === 'CC_MANAGER' || ME.role === 'CALL_TAKER') ?
    ('<div class="grid2" style="margin-top:12px"><div class="fld"><label>Re-route to team</label><select id="a_team">' +
      Object.keys(META.teams).map(function (k) { return '<option value="' + k + '"' + (k === t.team ? ' selected' : '') + '>' + esc(META.teams[k]) + '</option>'; }).join('') +
      '</select><button class="btn o sm" style="margin-top:7px" onclick="act(' + t.id + ',\'reassign\')">Apply re-route</button></div>' +
      '<div class="fld"><label>Change priority</label><select id="a_pri">' + Object.keys(META.priority).map(function (k) { return '<option value="' + k + '"' + (k === t.priority ? ' selected' : '') + '>' + k + '</option>'; }).join('') +
      '</select><button class="btn o sm" style="margin-top:7px" onclick="act(' + t.id + ',\'repriority\')">Apply priority</button></div></div>') : '';
  var canAssign = t.status !== 'CLOSED' && ((ME.role === t.team && ME.is_team_manager) || ME.role === 'CC_MANAGER');
  var assignBlock = canAssign ? ('<div class="fld" style="margin-top:12px"><label>Assign to engineer</label>' +
    '<select id="a_assignee_sel"><option value="">Loading roster…</option></select> ' +
    '<button class="btn o sm" onclick="act(' + t.id + ',\'assign\')">Assign</button></div>') : '';
  var form = (mine && t.status !== 'CLOSED') ? ('<div class="grid2" style="margin-top:6px">' +
    '<div class="fld"><label>Diagnosis</label><textarea id="a_diag" rows="2">' + esc(t.diagnosis || '') + '</textarea></div>' +
    '<div class="fld"><label>Action taken</label><textarea id="a_act" rows="2">' + esc(t.action_taken || '') + '</textarea></div>' +
    '<div class="fld"><label>Root cause</label><input id="a_rc" value="' + esc(t.root_cause || '') + '"></div>' +
    '<div class="fld"><label>Parts / replacement</label><input id="a_parts" value="' + esc(t.parts || '') + '"></div>' +
    '<div class="fld"><label>Resolution (required to resolve)</label><textarea id="a_res" rows="2">' + esc(t.resolution || '') + '</textarea></div>' +
    '<div class="fld"><label>Pending reason (required to hold)</label><input id="a_pend" value="' + esc(t.pending_reason || '') + '"></div>' +
    '<div class="fld"><label>Confirmed by (MMU / field)</label><input id="a_conf" value="' + esc(t.confirmed_by || '') + '" placeholder="Name at the MMU who confirmed"></div>' +
    '<div class="fld"><label>Note</label><input id="a_note" placeholder="Escalation / re-route remark"></div></div>') : '';
  
  document.getElementById('modal').innerHTML = '<div class="ovl" onclick="if(event.target===this)closeT()"><div class="sheet">' +
    '<div class="sh"><div><div style="font-size:19px;font-weight:800">' + esc(t.ticket_no) + ' &middot; ' + esc(t.category_label) + (t.vip ? ' <span class="pill p-crit">VIP</span>' : '') + '</div>' +
    '<div style="font-size:12.5px;opacity:.9;margin-top:3px">' + esc(t.mmu_vehicle || '—') + ' &middot; ' + esc(t.district || '') + ' &middot; ' + esc(t.team_label) + ' &middot; ' + esc(t.priority) + '</div></div>' +
    '<button class="x" onclick="closeT()">&times;</button></div><div class="sb">' +
    '<div style="display:flex;gap:9px;flex-wrap:wrap;margin-bottom:14px"><span class="pill p-mut">' + esc((t.status || '').replace(/_/g, ' ')) + '</span>' + tatPill(t).replace('<span ', '<span id="modalTat" ') +
    (t.escalated ? '<span class="pill p-crit">ESCALATED</span>' : '') + '<span class="pill p-mut">TAT ' + esc(t.tat_mins) + ' min</span>' +
    (t.paused_minutes ? '<span class="pill p-mut">Paused ' + esc(t.paused_minutes) + 'm so far</span>' : '') + '</div>' +
    '<div class="grid2"><div>' + row('Problem', t.problem) + row('Equipment', t.equipment) + row('Error code', t.error_code) + row('Impact', t.impact) +
    row('Caller', (t.caller_name || '') + (t.caller_phone ? (' · ' + t.caller_phone) : '')) + row('Location', t.location) + '</div>' +
    '<div>' + row('Created', t.created_at) + row('Due (TAT)', t.due_at) + row('Acknowledged', t.acknowledged_at) + row('Resolved', t.resolved_at) +
    row('Assigned to', t.assignee) + row('Confirmed by', t.confirmed_by) + row('Closed', t.closed_at) + row('Owner', t.owner) + '</div></div>' +
    form + reroute + assignBlock +
    '<div style="display:flex;gap:9px;flex-wrap:wrap;margin-top:14px">' + A.join('') + '</div>' +
    '<h4 style="margin:18px 0 8px;font-size:14px">Attachments / Evidence</h4>' +
    '<div id="modal_attachments"><div class="muted">Loading attachments...</div></div>' +
    '<h4 style="margin:18px 0 8px;font-size:14px">Audit trail</h4><div class="tl">' +
    (evs || []).map(function (e) { return '<div class="e"><b>' + esc(e.action) + '</b> — ' + esc(e.detail || '') + '<div class="muted">' + esc(e.at) + ' · ' + esc(e.actor) + ' (' + esc(e.actor_role) + ')</div></div>'; }).join('') +
    '</div></div></div></div>';
  if (canAssign) {
    var rosterUrl = '/users/team-roster' + (ME.role === 'CC_MANAGER' ? ('?team=' + encodeURIComponent(t.team)) : '');
    api('GET', rosterUrl).then(function (rows) {
      var sel = document.getElementById('a_assignee_sel');
      if (sel) sel.innerHTML = '<option value="">Select engineer…</option>' + rows.map(function (u) { return '<option value="' + esc(u.username) + '"' + (u.username === t.assignee ? ' selected' : '') + '>' + esc(u.name) + '</option>'; }).join('');
    }).catch(function () { });
  }
  if (MODAL_TICK) clearInterval(MODAL_TICK);
  if (t.status !== 'CLOSED') MODAL_TICK = setInterval(function () { updateModalCountdown(t); }, 30000);
}
function act(id, a) {
  var g = function (i) { var e = document.getElementById(i); return e ? e.value.trim() : undefined; };
  var b = {
    id: id, action: a, diagnosis: g('a_diag'), action_taken: g('a_act'), root_cause: g('a_rc'), parts: g('a_parts'),
    resolution: g('a_res'), pending_reason: g('a_pend'), confirmed_by: g('a_conf'), note: g('a_note'),
    team: g('a_team'), priority: g('a_pri'), assignee: g('a_assignee_sel')
  };
  api('POST', '/ticket/action', b).then(function () { toast('Done: ' + a); closeT(); load(); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Action failed'); });
}

function loadAttachments(id) {
  var box = document.getElementById('modal_attachments');
  if (!box) return;
  api('GET', '/ticket/' + id + '/attachments').then(function(rows) {
    var list = rows.length ? rows.map(function(a) {
      return '<div style="display:flex;align-items:center;justify-content:space-between;padding:8px 0;border-bottom:1px solid #f3f4f6">' +
        '<div><a href="/uploads/' + esc(a.filename) + '" target="_blank" style="color:var(--pur);font-weight:600;text-decoration:none">' + esc(a.original_name) + '</a>' +
        '<div class="muted">' + esc(a.uploaded_by) + ' (' + esc(a.uploaded_by_role) + ') &middot; ' + esc(a.created_at) + (a.note ? ' &middot; ' + esc(a.note) : '') + '</div></div>' +
        '</div>';
    }).join('') : '<div class="muted">No attachments yet.</div>';
    var form = '<div style="margin-top:12px;display:flex;gap:8px;align-items:flex-end;background:#f9fafb;padding:12px;border-radius:10px;border:1px dashed var(--line)">' +
      '<div style="flex:1"><label>File</label><input type="file" id="a_file" style="padding:8px;background:#fff"></div>' +
      '<div style="flex:1"><label>Note (optional)</label><input id="a_file_note" placeholder="What is this?"></div>' +
      '<button class="btn sm" onclick="uploadAttachment(' + id + ')">Upload</button></div>';
    box.innerHTML = list + form;
  }).catch(function() {
    box.innerHTML = '<div class="muted">Failed to load attachments</div>';
  });
}

function uploadAttachment(id) {
  var fileInput = document.getElementById('a_file');
  var file = fileInput.files[0];
  var note = document.getElementById('a_file_note').value;
  if (!file) return toast('Please select a file to upload');
  
  var fd = new FormData();
  fd.append('file', file);
  fd.append('note', note);
  
  toast('Uploading...');
  apiForm('/ticket/' + id + '/attachments', fd).then(function() {
    toast('Attachment uploaded');
    loadAttachments(id); // Reload the list
  }).catch(function(e) {
    toast(typeof e === 'string' ? e : 'Upload failed');
  });
}

/* ---------- notifications ---------- */
function loadNotifs() { api('GET', '/notifications').then(function (d) { NOTIFS = d.rows || []; renderBell(); if (NOTIF_OPEN) renderNotifPanel(); }).catch(function () { }); }
function renderBell() {
  var n = NOTIFS.filter(function (x) { return !x.read_at; }).length; var b = document.getElementById('nbadge');
  if (!b) return; if (n > 0) { b.textContent = n > 99 ? '99+' : n; b.classList.remove('hide'); } else { b.classList.add('hide'); }
}
function toggleNotifs() { NOTIF_OPEN = !NOTIF_OPEN; if (NOTIF_OPEN) { renderNotifPanel(); } else { document.getElementById('npanel').innerHTML = ''; } }
function renderNotifPanel() {
  var body = !NOTIFS.length ? '<div class="empty" style="padding:24px">No notifications</div>' :
    NOTIFS.map(function (n) {
      return '<div class="ni' + (n.read_at ? '' : ' unread') + '" onclick="openNotif(' + n.id + ',' + (n.ticket_id || 'null') + ')">' +
        '<div class="t">' + esc((n.type || '').replace(/_/g, ' ')) + '</div><div>' + esc(n.message) + '</div><div class="muted">' + esc(n.created_at) + '</div></div>';
    }).join('');
  document.getElementById('npanel').innerHTML = '<div class="npanel"><div class="nh">Notifications</div>' + body + '</div>';
}
function openNotif(id, ticketId) {
  var n = NOTIFS.find(function (x) { return x.id === id; });
  if (n && !n.read_at) { api('POST', '/notifications/' + id + '/read', {}).then(function () { n.read_at = 'now'; renderBell(); if (NOTIF_OPEN) renderNotifPanel(); }).catch(function () { }); }
  NOTIF_OPEN = false; document.getElementById('npanel').innerHTML = '';
  if (ticketId) { TAB = 'queue'; render(); openT(ticketId); }
}

/* ---------- dashboard ---------- */
function attnGoto(status, scope, priority) {
  TAB = 'queue'; FILT.status = status || ''; FILT.scope = scope || ''; FILT.priority = priority || '';
  FILT.mmu_vehicle = ''; FILT.district = ''; FILT.q = ''; FILT.category = ''; FILT.date_from = ''; FILT.date_to = ''; FILT.page = 1; render(); load();
}
function exportDash() {
  downloadExcel('/reports/summary.xlsx?period=daily', 'Dashboard_Summary.xlsx');
}
function viewDash() {
  if (!DASH) return '<div class="card"><div class="empty">Loading daily monitoring…</div></div>';
  var t = DASH.today || {}, k = DASH.kpi || {};
  var kpi = function (n, l, c) { return '<div class="kpi"><div class="n" style="color:' + (c || 'var(--pur)') + '">' + esc(n == null ? '—' : n) + '</div><div class="l">' + esc(l) + '</div></div>'; };
  var attn = function (n, l, c, onclick) { return '<button class="c" onclick="' + onclick + '"><div class="n" style="color:' + c + '">' + esc(n == null ? 0 : n) + '</div><div class="l">' + esc(l) + '</div></button>'; };
  var tbl = function (title, rows, cols) {
    return '<div class="card" style="margin-bottom:14px"><h4 style="margin-bottom:10px;font-size:14px">' + esc(title) + '</h4>' +
      '<table><thead><tr>' + cols.map(function (c) { return '<th>' + esc(c[0]) + '</th>'; }).join('') + '</tr></thead><tbody>' +
      (rows || []).map(function (r) { return '<tr>' + cols.map(function (c) { return '<td>' + esc(c[1](r)) + '</td>'; }).join('') + '</tr>'; }).join('') +
      '</tbody></table></div>';
  };
  return '<div class="card" style="margin-bottom:14px;display:flex;justify-content:space-between;align-items:center;">' +
    '<h4 style="margin:0;font-size:14px">Attention required</h4>' +
    '<button class="btn g sm" onclick="exportDash()">Export Summary (Excel)</button>' +
    '</div><div class="attn">' +
    attn(t.p1_open, 'P1 open', "var(--crit)", "attnGoto('open','','P1')") +
    attn(t.breached, 'TAT breached', "var(--crit)", "attnGoto('open','breach','')") +
    attn(t.critical, 'Critical', "#a3300c", "attnGoto('open','critical','')") +
    attn(t.at_risk, 'At risk', "var(--warn)", "attnGoto('open','risk','')") +
    attn(t.pending, 'Pending', "var(--org)", "attnGoto('PENDING','','')") +
    attn(t.awaiting_confirmation, 'Awaiting MMU confirmation', "var(--pur)", "attnGoto('RESOLVED','','')") +
    attn(t.escalated, 'Escalated', "var(--mag)", "attnGoto('open','escalated','')") +
    attn(t.escalated_from_field, 'Escalated from field', "var(--mag)", "attnGoto('open','escalated','')") +
    attn(t.unassigned, 'Unassigned', "var(--org)", "attnGoto('open','unassigned','')") +
    '</div>' +
    '<div class="kpis">' +
    kpi(t.tickets, 'Tickets today') + kpi(t.open, 'Open tickets') + kpi(t.closed, 'Closed today', 'var(--ok)') +
    kpi(t.breached, 'TAT breached', 'var(--crit)') + kpi(t.at_risk, 'At risk', 'var(--warn)') + kpi(t.escalated, 'Escalated', 'var(--mag)') +
    '</div>' +
    '<div class="kpis">' +
    kpi(k.tat_compliance_pct == null ? '—' : k.tat_compliance_pct + '%', 'TAT compliance', 'var(--ok)') +
    kpi(k.tat_breach_pct == null ? '—' : k.tat_breach_pct + '%', 'TAT breach %', 'var(--crit)') +
    kpi(k.avg_ack_mins == null ? '—' : k.avg_ack_mins + 'm', 'Avg acknowledgement') +
    kpi(k.avg_resolution_mins == null ? '—' : k.avg_resolution_mins + 'm', 'Avg resolution') +
    kpi(k.escalation_pct + '%', 'Escalation %', 'var(--mag)') + kpi(k.closed_total, 'Closed (all time)') +
    '</div>' +
    '<div class="grid2">' +
    tbl('Tickets by category', DASH.by_category, [['Category', function (r) { return (META.routing[r.category] || {}).label || r.category; }], ['Total', function (r) { return r.n; }], ['Open', function (r) { return r.open_n; }]]) +
    tbl('Tickets by responsible team', DASH.by_team, [['Team', function (r) { return META.teams[r.team] || r.team; }], ['Total', function (r) { return r.n; }], ['Open', function (r) { return r.open_n; }], ['Breached', function (r) { return r.breach_n; }]]) +
    tbl('By priority', DASH.by_priority, [['Priority', function (r) { return r.priority; }], ['Total', function (r) { return r.n; }], ['Open', function (r) { return r.open_n; }]]) +
    tbl('By status', DASH.by_status, [['Status', function (r) { return (r.status || '').replace(/_/g, ' '); }], ['Count', function (r) { return r.n; }]]) +
    tbl('Repeat issues by MMU', DASH.repeat_vehicles, [['MMU / Vehicle', function (r) { return r.mmu_vehicle; }], ['Tickets', function (r) { return r.n; }]]) +
    tbl('Daily volume (14 days)', DASH.daily, [['Date', function (r) { return r.d; }], ['Created', function (r) { return r.n; }], ['Closed', function (r) { return r.closed_n; }]]) +
    '</div>';
}

/* ---------- routing matrix ---------- */
function viewMatrix() {
  var rows = Object.keys(META.routing).map(function (k) {
    var r = META.routing[k];
    return '<tr><td><b>' + esc(r.label) + '</b></td><td>' + esc(META.teams[r.team]) + '</td><td>' + esc(r.owner) + '</td></tr>';
  }).join('');
  var tat = Object.keys(META.tat).map(function (k) { return '<tr><td><span class="pill p-' + k + '">' + k + '</span></td><td>' + esc(META.priority[k]) + '</td><td><b>' + esc(META.tat[k]) + ' min</b></td></tr>'; }).join('');
  return '<div class="card" style="margin-bottom:14px"><h4 style="margin-bottom:4px;font-size:15px">Issue routing matrix</h4>' +
    '<div class="muted" style="margin-bottom:12px">SOP §5 — every classified issue routes to one responsible team with a named initial owner.</div>' +
    '<table><thead><tr><th>Issue type</th><th>Responsible team</th><th>Initial owner</th></tr></thead><tbody>' + rows + '</tbody></table></div>' +
    '<div class="card" style="margin-bottom:14px"><h4 style="margin-bottom:4px;font-size:15px">Priority &amp; TAT</h4>' +
    '<div class="muted" style="margin-bottom:12px">SOP §8 — TAT drives the countdown, at-risk warning and breach flag on every ticket.</div>' +
    '<table><thead><tr><th>Priority</th><th>Example</th><th>TAT</th></tr></thead><tbody>' + tat + '</tbody></table></div>' +
    '<div class="card"><h4 style="margin-bottom:4px;font-size:15px">Ticket status flow</h4>' +
    '<div class="muted" style="margin-bottom:12px">SOP §11</div><div style="display:flex;gap:8px;flex-wrap:wrap">' +
    META.flow.map(function (s, i) { return '<span class="pill p-mut">' + (i + 1) + '. ' + esc(s.replace(/_/g, ' ')) + '</span>'; }).join('<span class="muted">→</span>') + '</div></div>';
}

/* ---------- LT self-service portal ----------
   Deliberately its own minimal view (not a stripped-down copy of the
   department Ticket Queue/modal) - an LT never needs filters, re-routing or
   the audit trail table, just "report a problem" and "check on what I
   reported", so keeping this separate avoids dragging in UI complexity that
   would only confuse a first-time field user. */
function loadLTCategories() {
  api('GET', '/lt-categories').then(function (rows) {
    LT_CATEGORIES = rows;
    var sel = document.getElementById('lt_cat');
    if (sel) sel.innerHTML = '<option value="">Select issue type…</option>' + rows.map(function (c) { return '<option value="' + c.code + '">' + esc(c.label) + '</option>'; }).join('');
  }).catch(function () { });
}
function ltCategoryChanged() {
  var cat = document.getElementById('lt_cat').value;
  LT_SELECTED_REASONS = [];
  var box = document.getElementById('lt_reasons_box');
  if (!box) return;
  if (!cat) { box.innerHTML = '<div class="muted">Select an issue type first</div>'; return; }
  box.innerHTML = '<div class="muted">Loading…</div>';
  api('GET', '/reasons?category=' + encodeURIComponent(cat)).then(function (rows) {
    LT_REASONS = rows;
    box.innerHTML = rows.length ? rows.map(function (r) {
      return '<label class="ltreason"><input type="checkbox" value="' + esc(r.code) + '" onchange="ltReasonToggle(this)"> ' + esc(r.label) + '</label>';
    }).join('') : '<div class="muted">No reasons configured for this issue type yet — contact the Global Team Executive.</div>';
  }).catch(function () { box.innerHTML = '<div class="muted">Could not load reasons</div>'; });
}
function ltReasonToggle(cb) {
  if (cb.checked) { if (LT_SELECTED_REASONS.indexOf(cb.value) < 0) LT_SELECTED_REASONS.push(cb.value); }
  else LT_SELECTED_REASONS = LT_SELECTED_REASONS.filter(function (x) { return x !== cb.value; });
}
var LT_MACH_DEBOUNCE = null;
function ltMachineSearchInput() {
  clearTimeout(LT_MACH_DEBOUNCE);
  var q = document.getElementById('lt_machine').value.trim();
  document.getElementById('lt_machine_id').value = '';
  if (q.length < 1) return;
  LT_MACH_DEBOUNCE = setTimeout(function () {
    api('GET', '/machines/search?q=' + encodeURIComponent(q)).then(function (rows) {
      LT_MACHINE_RESULTS = rows;
      document.getElementById('lt_machineDL').innerHTML = rows.map(function (m) { return '<option value="' + esc(m.name) + '">'; }).join('');
      var exact = rows.find(function (m) { return m.name.toLowerCase() === q.toLowerCase(); });
      if (exact) document.getElementById('lt_machine_id').value = exact.id;
    }).catch(function () { });
  }, 300);
}
function ltPhotoPreview() {
  var f = document.getElementById('lt_photo').files[0], prev = document.getElementById('lt_photo_prev');
  if (!f) { prev.innerHTML = ''; return; }
  prev.innerHTML = '<img src="' + URL.createObjectURL(f) + '" style="max-width:160px;max-height:160px;border-radius:10px;margin-top:8px;object-fit:cover">';
}
function viewLTReport() {
  return '<div class="card"><h3 style="margin-bottom:4px">Report an Issue</h3>' +
    '<div class="muted" style="margin-bottom:16px">Tell us what\'s wrong — it goes straight to your district\'s support team.</div>' +
    '<div class="fld"><label>What kind of issue? *</label><select id="lt_cat" onchange="ltCategoryChanged()"><option value="">Loading…</option></select></div>' +
    '<div class="fld"><label>What\'s wrong? (select all that apply) *</label><div id="lt_reasons_box" class="ltreasons"><div class="muted">Select an issue type first</div></div></div>' +
    '<div class="fld"><label>Machine (optional)</label><input id="lt_machine" list="lt_machineDL" placeholder="Start typing the machine name…" oninput="ltMachineSearchInput()" autocomplete="off"><datalist id="lt_machineDL"></datalist><input type="hidden" id="lt_machine_id"></div>' +
    '<div class="fld"><label>Add a photo (optional)</label><input type="file" id="lt_photo" accept="image/*" onchange="ltPhotoPreview()"><div id="lt_photo_prev"></div></div>' +
    '<div class="fld"><label>Anything else? (optional)</label><textarea id="lt_notes" rows="3" placeholder="Extra details, if any"></textarea></div>' +
    '<div class="fld"><label>How urgent is this?</label><select id="lt_pri"><option value="P1">Urgent — work has stopped</option><option value="P2" selected>Can wait a bit</option></select></div>' +
    '<button class="btn" style="margin-top:10px" onclick="submitLTTicket()">Submit report</button></div>';
}
function apiForm(p, fd) {
  var h = {}; if (TOK) h.Authorization = 'Bearer ' + TOK;
  return fetch(API + p, { method: 'POST', headers: h, body: fd }).then(function (r) {
    if (r.status === 401) { logout(); throw 'auth'; }
    return r.json().then(function (d) { if (!r.ok) throw (d.detail || ('HTTP ' + r.status)); return d; });
  });
}
function submitLTTicket() {
  var cat = gv('lt_cat') || document.getElementById('lt_cat').value;
  if (!cat) return toast('Select an issue type');
  if (!LT_SELECTED_REASONS.length) return toast('Select at least one reason');
  var fd = new FormData();
  fd.append('category', cat);
  fd.append('reason_codes', JSON.stringify(LT_SELECTED_REASONS));
  var mid = gv('lt_machine_id'); if (mid) fd.append('machine_id', mid);
  fd.append('priority', document.getElementById('lt_pri').value);
  fd.append('problem', gv('lt_notes'));
  var photo = document.getElementById('lt_photo').files[0];
  if (photo) fd.append('photo', photo);
  apiForm('/lt/tickets', fd).then(function (d) { toast('Reported! Ticket ' + d.ticket_no + ' sent to the right team'); TAB = 'mine'; render(); load(); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Could not submit report'); });
}
function loadLTMine() { api('GET', '/lt/tickets').then(function (rows) { LT_TICKETS = rows; render(); }).catch(function () { }); }
function viewLTMine() {
  if (!LT_TICKETS.length) return '<div class="card"><div class="empty">You haven\'t reported anything yet.</div></div>';
  return LT_TICKETS.map(function (t) {
    var photo = t.photo_path ? ('<img src="/uploads/' + esc(t.photo_path) + '" style="max-width:140px;max-height:140px;border-radius:10px;margin-top:10px;object-fit:cover">') : '';
    var actions = '';
    if (t.status === 'RESOLVED') actions = '<button class="btn g sm" onclick="ltConfirmFixed(' + t.id + ')">Confirm — it\'s fixed</button>';
    else if (t.status === 'CLOSED') actions = '<button class="btn o sm" onclick="ltReopenSame(' + t.id + ')">Reopen — broke again</button>';
    return '<div class="card" style="margin-bottom:12px">' +
      '<div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px">' +
      '<div><b>' + esc(t.ticket_no) + '</b><div class="muted">' + esc(t.category_label || '') + '</div></div>' +
      '<div style="text-align:right"><span class="pill p-mut">' + esc((t.status || '').replace(/_/g, ' ')) + '</span> ' + tatPill(t) + '</div></div>' +
      '<div style="margin-top:8px">' + esc(t.problem || '') + '</div>' +
      (t.resolution ? ('<div class="muted" style="margin-top:8px"><b>Resolution:</b> ' + esc(t.resolution) + '</div>') : '') +
      photo + (actions ? ('<div style="margin-top:12px">' + actions + '</div>') : '') + '</div>';
  }).join('');
}
function ltConfirmFixed(id) {
  api('POST', '/ticket/action', { id: id, action: 'confirm', confirmed_by: ME.name }).then(function () { toast('Marked as fixed — thank you'); loadLTMine(); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Could not confirm'); });
}
function ltReopenSame(id) {
  var reason = prompt('What\'s still wrong? (required):'); if (reason === null) return; if (!reason.trim()) return toast('A reason is required to reopen');
  api('POST', '/ticket/action', { id: id, action: 'reopen', note: reason.trim() }).then(function () { toast('Reopened'); loadLTMine(); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Could not reopen'); });
}

/* ---------- admin portal ----------
   goAdmin only auto-fetches on the FIRST visit to a sub-tab: fetch-then-render
   is async, and if it re-rendered on every visit it could land while the admin
   is mid-fill on a form on a slow connection, silently wiping their input
   (a real double-render race, not hypothetical - caught by hand-testing this
   exact flow). Revisits show cached data instantly; "Refresh" re-fetches
   explicitly. Actions (create/update) still refresh immediately afterward -
   that's a deliberate, user-initiated reload of a form that just submitted,
   not a background one racing live typing. */
function goAdmin(t) { ADMIN_TAB = t; render(); if (!ADMIN_LOADED[t]) loadAdminSection(t); }
function loadAdminSection(t) {
  if (t === 'teams') api('GET', '/admin/teams').then(function (d) { ADMIN_TEAMS = d; ADMIN_LOADED.teams = true; if (ADMIN_TAB === 'teams') render(); });
  else if (t === 'categories') api('GET', '/admin/teams').then(function (d) {
    ADMIN_TEAMS = d;
    api('GET', '/admin/categories').then(function (d2) { ADMIN_CATEGORIES = d2; ADMIN_LOADED.categories = true; if (ADMIN_TAB === 'categories') render(); });
  });
  else if (t === 'sla') api('GET', '/admin/sla').then(function (d) {
    ADMIN_SLA = d;
    api('GET', '/admin/dispatch').then(function (dp) { ADMIN_DISPATCH = dp; ADMIN_LOADED.sla = true; if (ADMIN_TAB === 'sla') render(); });
  });
  else if (t === 'users') api('GET', '/admin/roles').then(function (r) {
    ADMIN_ROLES = r;
    var qs = ADMIN_USERS_Q ? '?q=' + encodeURIComponent(ADMIN_USERS_Q) : '';
    api('GET', '/users' + qs).then(function (d) {
      ADMIN_USERS = d;
      api('GET', '/admin/districts').then(function (dist) {
        ADMIN_DISTRICTS = dist;
        api('GET', '/admin/mandals').then(function (m) {
          ADMIN_MANDALS = m;
          api('GET', '/admin/vehicles').then(function (v) { ADMIN_VEHICLES = v; ADMIN_LOADED.users = true; if (ADMIN_TAB === 'users') render(); });
        });
      });
    });
  });
  else if (t === 'geo') api('GET', '/admin/districts').then(function (d) {
    ADMIN_DISTRICTS = d;
    api('GET', '/admin/zones').then(function (z) {
      ADMIN_ZONES = z;
      api('GET', '/admin/mandals').then(function (m) { ADMIN_MANDALS = m; ADMIN_LOADED.geo = true; if (ADMIN_TAB === 'geo') render(); });
    });
  });
  else if (t === 'vehicles') api('GET', '/admin/vehicles').then(function (d) {
    ADMIN_VEHICLES = d;
    api('GET', '/admin/mandals').then(function (m) { ADMIN_MANDALS = m; ADMIN_LOADED.vehicles = true; if (ADMIN_TAB === 'vehicles') render(); });
  });
  else if (t === 'reasons') api('GET', '/admin/categories').then(function (c) {
    ADMIN_CATEGORIES = c;
    api('GET', '/admin/reasons').then(function (d) { ADMIN_REASONS = d; ADMIN_LOADED.reasons = true; if (ADMIN_TAB === 'reasons') render(); });
  });
  else if (t === 'machines') api('GET', '/admin/machines').then(function (d) { ADMIN_MACHINES = d; ADMIN_LOADED.machines = true; if (ADMIN_TAB === 'machines') render(); });
  else if (t === 'audit') api('GET', '/admin/audit').then(function (d) { ADMIN_AUDIT = d; ADMIN_LOADED.audit = true; if (ADMIN_TAB === 'audit') render(); });
}
function viewAdmin() {
  var labels = {
    teams: 'Teams & Escalation Hierarchy',
    categories: 'Categories & Department Owners',
    geo: 'Districts, Mandals & Zones',
    vehicles: 'MMU Vehicle Fleet Registry',
    reasons: 'Lab Technician Reason Codes',
    machines: 'Diagnostic Machines & Equipment',
    sla: 'SLA Priorities & TAT Benchmarks',
    users: 'System Users & Role Assignments',
    audit: 'System Administrator Audit Log'
  };
  var bar = '<div class="card" style="margin-bottom:14px;display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap">' +
    '<div><div style="font-size:16px;font-weight:800;color:var(--ink)">⚙️ ' + esc(labels[ADMIN_TAB] || 'Admin Portal') + '</div>' +
    '<div style="font-size:12.5px;color:var(--ink2);margin-top:2px">Manage global master data, mappings and access permissions</div></div>' +
    '<button class="btn o sm" onclick="loadAdminSection(ADMIN_TAB)">&#8635; Refresh Data</button></div>';
  var body = '';
  if (!ADMIN_LOADED[ADMIN_TAB]) body = '<div class="card"><div class="empty">Loading…</div></div>';
  else if (ADMIN_TAB === 'teams') body = viewAdminTeams();
  else if (ADMIN_TAB === 'categories') body = viewAdminCategories();
  else if (ADMIN_TAB === 'geo') body = viewAdminGeo();
  else if (ADMIN_TAB === 'vehicles') body = viewAdminVehicles();
  else if (ADMIN_TAB === 'reasons') body = viewAdminReasons();
  else if (ADMIN_TAB === 'machines') body = viewAdminMachines();
  else if (ADMIN_TAB === 'sla') body = viewAdminSla();
  else if (ADMIN_TAB === 'users') body = viewAdminUsers();
  else if (ADMIN_TAB === 'audit') body = viewAdminAudit();
  return bar + body;
}

function viewAdminTeams() {
  var rows = ADMIN_TEAMS.map(function (t) {
    return '<tr><td><b>' + esc(t.code) + '</b></td><td>' + esc(t.name) + '</td>' +
      '<td>' + (t.is_active ? '<span class="pill p-ok">Active</span>' : '<span class="pill p-mut">Inactive</span>') + '</td>' +
      '<td style="display:flex;gap:6px"><button class="btn o sm" onclick="adminRenameTeam(\'' + t.code + '\')">Rename</button>' +
      '<button class="btn ' + (t.is_active ? 'r' : 'g') + ' sm" onclick="adminToggleTeam(\'' + t.code + '\',' + (!t.is_active) + ')">' + (t.is_active ? 'Deactivate' : 'Activate') + '</button></td></tr>';
  }).join('');
  return '<div class="card" style="margin-bottom:14px"><h4 style="margin-bottom:10px;font-size:14px">Teams</h4>' +
    '<div style="overflow-x:auto"><table><thead><tr><th>Code</th><th>Name</th><th>Status</th><th></th></tr></thead><tbody>' + rows + '</tbody></table></div></div>' +
    '<div class="card"><h4 style="margin-bottom:10px;font-size:14px">Add team</h4><div class="grid3">' +
    '<div class="fld"><label>Code</label><input id="at_code" placeholder="PHARMACY"></div>' +
    '<div class="fld"><label>Name</label><input id="at_name" placeholder="Pharmacy Team"></div>' +
    '<div class="fld" style="display:flex;align-items:flex-end"><button class="btn" onclick="adminCreateTeam()">Add team</button></div>' +
    '</div></div>';
}
function adminCreateTeam() {
  var code = gv('at_code'), name = gv('at_name');
  if (!code || !name) return toast('Code and name are required');
  api('POST', '/admin/teams', { code: code, name: name }).then(function () { toast('Team added'); loadAdminSection('teams'); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}
function adminRenameTeam(code) {
  var t = ADMIN_TEAMS.find(function (x) { return x.code === code; });
  editModal('Rename team ' + code,
    '<div class="fld"><label for="em_name">Name</label><input id="em_name" value="' + esc(t ? t.name : '') + '"></div>',
    function () {
      var name = gv('em_name'); if (!name) { toast('Name is required'); return; }
      api('PUT', '/admin/teams/' + code, { name: name }).then(function () { closeModal2(); toast('Renamed'); loadAdminSection('teams'); })
        .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
    });
}
function adminToggleTeam(code, active) {
  api('PUT', '/admin/teams/' + code, { is_active: active }).then(function () { toast(active ? 'Activated' : 'Deactivated'); loadAdminSection('teams'); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}

function viewAdminCategories() {
  var teamOpts = function (sel) { return ADMIN_TEAMS.filter(function (t) { return t.is_active; }).map(function (t) { return '<option value="' + t.code + '"' + (t.code === sel ? ' selected' : '') + '>' + esc(t.name) + '</option>'; }).join(''); };
  var rows = ADMIN_CATEGORIES.map(function (c) {
    return '<tr><td><b>' + esc(c.code) + '</b></td><td>' + esc(c.label) + '</td>' +
      '<td><select id="ac_team_' + c.code + '">' + teamOpts(c.team_code) + '</select> <button class="btn o sm" onclick="adminMoveCategory(\'' + c.code + '\')">Apply</button></td>' +
      '<td>' + esc(c.default_owner || '') + '</td>' +
      '<td><button class="btn ' + (c.route_by_zone ? 'g' : 'o') + ' sm" onclick="adminToggleRouteByZone(\'' + c.code + '\',' + (!c.route_by_zone) + ')">' + (c.route_by_zone ? 'Zone-routed' : 'By category') + '</button></td>' +
      '<td><button class="btn ' + (c.visible_to_lt ? 'g' : 'o') + ' sm" onclick="adminToggleVisibleToLt(\'' + c.code + '\',' + (!c.visible_to_lt) + ')">' + (c.visible_to_lt ? 'Visible to LT' : 'Hidden from LT') + '</button></td>' +
      '<td>' + (c.is_active ? '<span class="pill p-ok">Active</span>' : '<span class="pill p-mut">Inactive</span>') + '</td>' +
      '<td style="display:flex;gap:6px"><button class="btn o sm" onclick="adminEditCategory(\'' + c.code + '\')">Edit</button>' +
      '<button class="btn ' + (c.is_active ? 'r' : 'g') + ' sm" onclick="adminToggleCategory(\'' + c.code + '\',' + (!c.is_active) + ')">' + (c.is_active ? 'Deactivate' : 'Activate') + '</button></td></tr>';
  }).join('');
  return '<div class="card" style="margin-bottom:14px"><h4 style="margin-bottom:10px;font-size:14px">Categories</h4>' +
    '<div class="muted" style="margin-bottom:10px">"Zone-routed" categories send tickets to the Mandal\'s Zone team (if configured) instead of the category\'s own team - use for issues needing physical dispatch (Machine, Fleet, Field). Leave centrally-handled categories (Application, Network, ...) on "By category". "Visible to LT" controls whether it appears in the LT self-service portal\'s issue-type dropdown.</div>' +
    '<div style="overflow-x:auto"><table><thead><tr><th>Code</th><th>Label</th><th>Team</th><th>Owner</th><th>Routing</th><th>LT portal</th><th>Status</th><th></th></tr></thead><tbody>' + rows + '</tbody></table></div></div>' +
    '<div class="card"><h4 style="margin-bottom:10px;font-size:14px">Add category</h4><div class="grid3">' +
    '<div class="fld"><label>Code</label><input id="ac_code" placeholder="MEDSTOCK"></div>' +
    '<div class="fld"><label>Label</label><input id="ac_label" placeholder="Medicine stock issue"></div>' +
    '<div class="fld"><label>Team</label><select id="ac_new_team">' + teamOpts() + '</select></div>' +
    '<div class="fld"><label>Default owner</label><input id="ac_owner" placeholder="Pharmacist"></div>' +
    '<div class="fld" style="display:flex;align-items:flex-end"><button class="btn" onclick="adminCreateCategory()">Add category</button></div>' +
    '</div></div>';
}
function adminCreateCategory() {
  var code = gv('ac_code'), label = gv('ac_label'), team = document.getElementById('ac_new_team').value, owner = gv('ac_owner');
  if (!code || !label) return toast('Code and label are required');
  api('POST', '/admin/categories', { code: code, label: label, team_code: team, default_owner: owner }).then(function () { toast('Category added'); loadAdminSection('categories'); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}
function adminMoveCategory(code) {
  var team = document.getElementById('ac_team_' + code).value;
  api('PUT', '/admin/categories/' + code, { team_code: team }).then(function () { toast('Re-routed'); loadAdminSection('categories'); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}
function adminEditCategory(code) {
  var c = ADMIN_CATEGORIES.find(function (x) { return x.code === code; });
  editModal('Edit category ' + code,
    '<div class="fld"><label for="em_label">Label</label><input id="em_label" value="' + esc(c.label) + '"></div>' +
    '<div class="fld"><label for="em_owner">Default owner</label><input id="em_owner" value="' + esc(c.default_owner || '') + '"></div>',
    function () {
      var label = gv('em_label'); if (!label) { toast('Label is required'); return; }
      api('PUT', '/admin/categories/' + code, { label: label, default_owner: gv('em_owner') })
        .then(function () { closeModal2(); toast('Updated'); loadAdminSection('categories'); })
        .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
    });
}
function adminToggleCategory(code, active) {
  api('PUT', '/admin/categories/' + code, { is_active: active }).then(function () { toast(active ? 'Activated' : 'Deactivated'); loadAdminSection('categories'); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}
function adminToggleRouteByZone(code, routeByZone) {
  api('PUT', '/admin/categories/' + code, { route_by_zone: routeByZone }).then(function () { toast(routeByZone ? 'Now zone-routed' : 'Now routed by category'); loadAdminSection('categories'); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}
function adminToggleVisibleToLt(code, visible) {
  api('PUT', '/admin/categories/' + code, { visible_to_lt: visible }).then(function () { toast(visible ? 'Now visible to LT' : 'Now hidden from LT'); loadAdminSection('categories'); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}

function viewAdminGeo() {
  var districtRows = ADMIN_DISTRICTS.map(function (d) {
    return '<tr><td><b>' + esc(d.name) + '</b></td>' +
      '<td>' + (d.is_active ? '<span class="pill p-ok">Active</span>' : '<span class="pill p-mut">Inactive</span>') + '</td>' +
      '<td style="display:flex;gap:6px"><button class="btn o sm" onclick="adminRenameDistrict(' + d.id + ')">Rename</button>' +
      '<button class="btn ' + (d.is_active ? 'r' : 'g') + ' sm" onclick="adminToggleDistrict(' + d.id + ',' + (!d.is_active) + ')">' + (d.is_active ? 'Deactivate' : 'Activate') + '</button></td></tr>';
  }).join('');
  var zoneRows = ADMIN_ZONES.map(function (z) {
    return '<tr><td><b>' + esc(z.name) + '</b></td><td>' + esc((META.teams || {})[z.team_code] || z.team_code) + '</td>' +
      '<td>' + (z.is_active ? '<span class="pill p-ok">Active</span>' : '<span class="pill p-mut">Inactive</span>') + '</td>' +
      '<td style="display:flex;gap:6px"><button class="btn o sm" onclick="adminEditZone(' + z.id + ')">Edit</button>' +
      '<button class="btn ' + (z.is_active ? 'r' : 'g') + ' sm" onclick="adminToggleZone(' + z.id + ',' + (!z.is_active) + ')">' + (z.is_active ? 'Deactivate' : 'Activate') + '</button></td></tr>';
  }).join('');
  var districtOpts = ADMIN_DISTRICTS.filter(function (d) { return d.is_active; }).map(function (d) { return '<option value="' + d.id + '">' + esc(d.name) + '</option>'; }).join('');
  var zoneOpts = '<option value="">No zone (category-default routing)</option>' + ADMIN_ZONES.filter(function (z) { return z.is_active; }).map(function (z) { return '<option value="' + z.id + '">' + esc(z.name) + '</option>'; }).join('');
  var mandalRows = ADMIN_MANDALS.map(function (m) {
    var d = ADMIN_DISTRICTS.find(function (x) { return x.id === m.district_id; });
    var z = ADMIN_ZONES.find(function (x) { return x.id === m.zone_id; });
    return '<tr><td><b>' + esc(m.name) + '</b></td><td>' + esc(d ? d.name : m.district_id) + '</td><td>' + esc(z ? z.name : '—') + '</td>' +
      '<td>' + (m.is_active ? '<span class="pill p-ok">Active</span>' : '<span class="pill p-mut">Inactive</span>') + '</td>' +
      '<td style="display:flex;gap:6px"><button class="btn o sm" onclick="adminEditMandal(' + m.id + ')">Edit</button>' +
      '<button class="btn ' + (m.is_active ? 'r' : 'g') + ' sm" onclick="adminToggleMandal(' + m.id + ',' + (!m.is_active) + ')">' + (m.is_active ? 'Deactivate' : 'Activate') + '</button></td></tr>';
  }).join('');
  return '<div class="card" style="margin-bottom:14px"><h4 style="margin-bottom:10px;font-size:14px">Districts</h4>' +
    '<table><thead><tr><th>Name</th><th>Status</th><th></th></tr></thead><tbody>' + districtRows + '</tbody></table></div>' +
    '<div class="card" style="margin-bottom:14px"><div class="grid3">' +
    '<div class="fld"><label>New district name</label><input id="geo_district_name" placeholder="Hyderabad"></div>' +
    '<div class="fld" style="display:flex;align-items:flex-end"><button class="btn" onclick="adminCreateDistrict()">Add district</button></div></div></div>' +

    '<div class="card" style="margin-bottom:14px"><h4 style="margin-bottom:4px;font-size:15px">Zones</h4>' +
    '<div class="muted" style="margin-bottom:10px">A Zone maps a group of Mandals to one responsible Team - only used for categories flagged "zone-routed" on the Categories tab.</div>' +
    '<table><thead><tr><th>Name</th><th>Team</th><th>Status</th><th></th></tr></thead><tbody>' + zoneRows + '</tbody></table></div>' +
    '<div class="card" style="margin-bottom:14px"><div class="grid3">' +
    '<div class="fld"><label>New zone name</label><input id="geo_zone_name" placeholder="South Zone"></div>' +
    '<div class="fld"><label>Team</label><select id="geo_zone_team">' + Object.keys(META.teams).map(function (k) { return '<option value="' + k + '">' + esc(META.teams[k]) + '</option>'; }).join('') + '</select></div>' +
    '<div class="fld" style="display:flex;align-items:flex-end"><button class="btn" onclick="adminCreateZone()">Add zone</button></div></div></div>' +

    '<div class="card" style="margin-bottom:14px"><h4 style="margin-bottom:10px;font-size:14px">Mandals</h4>' +
    '<div style="overflow-x:auto"><table><thead><tr><th>Name</th><th>District</th><th>Zone</th><th>Status</th><th></th></tr></thead><tbody>' + mandalRows + '</tbody></table></div></div>' +
    '<div class="card"><h4 style="margin-bottom:10px;font-size:14px">Add mandal</h4><div class="grid3">' +
    '<div class="fld"><label>Name</label><input id="geo_mandal_name" placeholder="Shamshabad"></div>' +
    '<div class="fld"><label>District</label><select id="geo_mandal_district">' + districtOpts + '</select></div>' +
    '<div class="fld"><label>Zone (optional)</label><select id="geo_mandal_zone">' + zoneOpts + '</select></div>' +
    '<div class="fld" style="display:flex;align-items:flex-end"><button class="btn" onclick="adminCreateMandal()">Add mandal</button></div>' +
    '</div></div>';
}
function adminCreateDistrict() {
  var name = gv('geo_district_name'); if (!name) return toast('District name is required');
  api('POST', '/admin/districts', { name: name }).then(function () { toast('District added'); loadAdminSection('geo'); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}
function adminRenameDistrict(id) {
  var d = ADMIN_DISTRICTS.find(function (x) { return x.id === id; });
  editModal('Rename district',
    '<div class="fld"><label for="em_name">Name</label><input id="em_name" value="' + esc(d ? d.name : '') + '"></div>',
    function () {
      var name = gv('em_name'); if (!name) { toast('Name is required'); return; }
      api('PUT', '/admin/districts/' + id, { name: name }).then(function () { closeModal2(); toast('Renamed'); loadAdminSection('geo'); })
        .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
    });
}
function adminToggleDistrict(id, active) {
  api('PUT', '/admin/districts/' + id, { is_active: active }).then(function () { toast(active ? 'Activated' : 'Deactivated'); loadAdminSection('geo'); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}
function adminCreateZone() {
  var name = gv('geo_zone_name'), team = document.getElementById('geo_zone_team').value;
  if (!name) return toast('Zone name is required');
  api('POST', '/admin/zones', { name: name, team_code: team }).then(function () { toast('Zone added'); loadAdminSection('geo'); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}
function adminToggleZone(id, active) {
  api('PUT', '/admin/zones/' + id, { is_active: active }).then(function () { toast(active ? 'Activated' : 'Deactivated'); loadAdminSection('geo'); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}
function adminEditZone(id) {
  var z = ADMIN_ZONES.find(function (x) { return x.id === id; }); if (!z) return;
  var teamOpts = Object.keys(META.teams).map(function (k) { return '<option value="' + k + '"' + (k === z.team_code ? ' selected' : '') + '>' + esc(META.teams[k]) + '</option>'; }).join('');
  editModal('Edit zone',
    '<div class="fld"><label for="em_name">Name</label><input id="em_name" value="' + esc(z.name) + '"></div>' +
    '<div class="fld"><label for="em_team">Team</label><select id="em_team">' + teamOpts + '</select></div>',
    function () {
      var name = gv('em_name'); if (!name) { toast('Zone name is required'); return; }
      api('PUT', '/admin/zones/' + id, { name: name, team_code: document.getElementById('em_team').value })
        .then(function () { closeModal2(); toast('Zone updated'); loadAdminSection('geo'); })
        .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
    });
}
function adminCreateMandal() {
  var name = gv('geo_mandal_name'), did = document.getElementById('geo_mandal_district').value, zid = document.getElementById('geo_mandal_zone').value;
  if (!name || !did) return toast('Mandal name and district are required');
  api('POST', '/admin/mandals', { name: name, district_id: +did, zone_id: zid ? +zid : null }).then(function () { toast('Mandal added'); loadAdminSection('geo'); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}
function adminToggleMandal(id, active) {
  api('PUT', '/admin/mandals/' + id, { is_active: active }).then(function () { toast(active ? 'Activated' : 'Deactivated'); loadAdminSection('geo'); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}
function adminEditMandal(id) {
  var m = ADMIN_MANDALS.find(function (x) { return x.id === id; }); if (!m) return;
  var distOpts = ADMIN_DISTRICTS.filter(function (d) { return d.is_active; }).map(function (d) { return '<option value="' + d.id + '"' + (d.id === m.district_id ? ' selected' : '') + '>' + esc(d.name) + '</option>'; }).join('');
  var zoneOpts = '<option value="">No zone</option>' + ADMIN_ZONES.filter(function (z) { return z.is_active; }).map(function (z) { return '<option value="' + z.id + '"' + (z.id === m.zone_id ? ' selected' : '') + '>' + esc(z.name) + '</option>'; }).join('');
  editModal('Edit mandal',
    '<div class="fld"><label for="em_name">Name</label><input id="em_name" value="' + esc(m.name) + '"></div>' +
    '<div class="fld"><label for="em_district">District</label><select id="em_district">' + distOpts + '</select></div>' +
    '<div class="fld"><label for="em_zone">Zone (optional)</label><select id="em_zone">' + zoneOpts + '</select></div>',
    function () {
      var name = gv('em_name'), did = document.getElementById('em_district').value;
      if (!name || !did) { toast('Mandal name and district are required'); return; }
      var zid = document.getElementById('em_zone').value;
      // Clear-sentinel convention (see crud_geo.update_mandal): 0 clears
      // zone_id, omitted/None leaves it untouched - always send a real number.
      api('PUT', '/admin/mandals/' + id, { name: name, district_id: +did, zone_id: zid ? +zid : 0 })
        .then(function () { closeModal2(); toast('Mandal updated'); loadAdminSection('geo'); })
        .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
    });
}

function viewAdminVehicles() {
  var rows = ADMIN_VEHICLES.map(function (v) {
    var mandal = ADMIN_MANDALS.find(function (x) { return x.id === v.last_mandal_id; });
    return '<tr><td><b>' + esc(v.registration_no) + '</b></td>' +
      '<td>' + esc(mandal ? mandal.name : '—') + '</td>' +
      '<td>' + (v.is_active ? '<span class="pill p-ok">Active</span>' : '<span class="pill p-mut">Inactive</span>') + '</td>' +
      '<td style="display:flex;gap:6px"><button class="btn o sm" onclick="adminEditVehicle(' + v.id + ')">Edit</button>' +
      '<button class="btn ' + (v.is_active ? 'r' : 'g') + ' sm" onclick="adminToggleVehicle(' + v.id + ',' + (!v.is_active) + ')">' + (v.is_active ? 'Deactivate' : 'Activate') + '</button></td></tr>';
  }).join('');
  return '<div class="card" style="margin-bottom:14px"><h4 style="margin-bottom:4px;font-size:15px">Vehicles</h4>' +
    '<div class="muted" style="margin-bottom:10px">A registry entry only tracks the registration number - MMU vehicles move between Mandals, so location is captured fresh on each ticket and never stored here. "Last known Mandal" is an optional administrative note, not the routing source.</div>' +
    '<div style="overflow-x:auto"><table><thead><tr><th>Registration no.</th><th>Last known Mandal</th><th>Status</th><th></th></tr></thead><tbody>' + rows + '</tbody></table></div></div>' +
    '<div class="card"><h4 style="margin-bottom:10px;font-size:14px">Add vehicle</h4><div class="grid3">' +
    '<div class="fld"><label>Registration number</label><input id="veh_reg" placeholder="AP39UL4276"></div>' +
    '<div class="fld" style="display:flex;align-items:flex-end"><button class="btn" onclick="adminCreateVehicle()">Add vehicle</button></div>' +
    '</div></div>';
}
function adminCreateVehicle() {
  var reg = gv('veh_reg'); if (!reg) return toast('Registration number is required');
  api('POST', '/admin/vehicles', { registration_no: reg }).then(function () { toast('Vehicle added'); loadAdminSection('vehicles'); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}
function adminToggleVehicle(id, active) {
  api('PUT', '/admin/vehicles/' + id, { is_active: active }).then(function () { toast(active ? 'Activated' : 'Deactivated'); loadAdminSection('vehicles'); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}
function adminEditVehicle(id) {
  var v = ADMIN_VEHICLES.find(function (x) { return x.id === id; }); if (!v) return;
  var mandOpts = '<option value="">No mandal</option>' + ADMIN_MANDALS.filter(function (m) { return m.is_active; }).map(function (m) { return '<option value="' + m.id + '"' + (m.id === v.last_mandal_id ? ' selected' : '') + '>' + esc(m.name) + '</option>'; }).join('');
  editModal('Edit vehicle — ' + v.registration_no,
    '<div class="fld"><label for="em_mandal">Last known Mandal</label><select id="em_mandal">' + mandOpts + '</select></div>',
    function () {
      var mid = document.getElementById('em_mandal').value;
      api('PUT', '/admin/vehicles/' + id, { last_mandal_id: mid ? +mid : 0 })
        .then(function () { closeModal2(); toast('Vehicle updated'); loadAdminSection('vehicles'); })
        .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
    });
}

function viewAdminReasons() {
  var ltCats = ADMIN_CATEGORIES.filter(function (c) { return c.visible_to_lt; });
  var catOpts = ltCats.map(function (c) { return '<option value="' + c.code + '">' + esc(c.label) + '</option>'; }).join('');
  var catLabel = function (code) { var c = ADMIN_CATEGORIES.find(function (x) { return x.code === code; }); return c ? c.label : code; };
  var rows = ADMIN_REASONS.map(function (r) {
    return '<tr><td><b>' + esc(r.code) + '</b></td><td>' + esc(r.label) + '</td><td>' + esc(catLabel(r.category_code)) + '</td>' +
      '<td>' + (r.is_active ? '<span class="pill p-ok">Active</span>' : '<span class="pill p-mut">Inactive</span>') + '</td>' +
      '<td style="display:flex;gap:6px"><button class="btn o sm" onclick="adminRenameReason(\'' + r.code + '\')">Rename</button>' +
      '<button class="btn ' + (r.is_active ? 'r' : 'g') + ' sm" onclick="adminToggleReason(\'' + r.code + '\',' + (!r.is_active) + ')">' + (r.is_active ? 'Deactivate' : 'Activate') + '</button></td></tr>';
  }).join('');
  return '<div class="card" style="margin-bottom:14px"><h4 style="margin-bottom:10px;font-size:14px">LT Reasons</h4>' +
    '<div class="muted" style="margin-bottom:10px">The tagged reasons an LT picks from when reporting an issue on a category flagged "Visible to LT" (see Categories tab) - keep labels short and plain-language, since field staff pick from these directly.</div>' +
    '<div style="overflow-x:auto"><table><thead><tr><th>Code</th><th>Label</th><th>Issue type</th><th>Status</th><th></th></tr></thead><tbody>' + rows + '</tbody></table></div></div>' +
    '<div class="card"><h4 style="margin-bottom:10px;font-size:14px">Add reason</h4>' +
    (ltCats.length ? ('<div class="grid3">' +
      '<div class="fld"><label>Code</label><input id="ar_code" placeholder="NO_POWER"></div>' +
      '<div class="fld"><label>Label (shown to the LT)</label><input id="ar_label" placeholder="No power / won\'t switch on"></div>' +
      '<div class="fld"><label>Issue type</label><select id="ar_category">' + catOpts + '</select></div>' +
      '<div class="fld" style="display:flex;align-items:flex-end"><button class="btn" onclick="adminCreateReason()">Add reason</button></div>' +
      '</div>') : '<div class="muted">No categories are flagged "Visible to LT" yet - flag one on the Categories tab first.</div>') +
    '</div>';
}
function adminAddReason() {
  var b = { category: document.getElementById('ar_cat').value, reason: document.getElementById('ar_text').value, requires_resolution: document.getElementById('ar_req_res').checked };
  api('POST', '/admin/reasons', b).then(function () { toast('Reason added'); loadAdminSection('reasons'); }).catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}
function adminCreateReason() {
  var code = gv('ar_code'), label = gv('ar_label'), cat = document.getElementById('ar_category').value;
  if (!code || !label) return toast('Code and label are required');
  api('POST', '/admin/reasons', { code: code, category_code: cat, label: label }).then(function () { toast('Reason added'); loadAdminSection('reasons'); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}
function adminRenameReason(code) {
  var r = ADMIN_REASONS.find(function (x) { return x.code === code; });
  editModal('Rename reason',
    '<div class="fld"><label for="em_label">Label</label><input id="em_label" value="' + esc(r ? r.label : '') + '"></div>',
    function () {
      var label = gv('em_label'); if (!label) { toast('Label is required'); return; }
      api('PUT', '/admin/reasons/' + code, { label: label }).then(function () { closeModal2(); toast('Renamed'); loadAdminSection('reasons'); })
        .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
    });
}
function adminToggleReason(code, active) {
  api('PUT', '/admin/reasons/' + code, { is_active: active }).then(function () { toast(active ? 'Activated' : 'Deactivated'); loadAdminSection('reasons'); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}

function viewAdminMachines() {
  var rows = ADMIN_MACHINES.map(function (m) {
    return '<tr><td><b>' + esc(m.name) + '</b></td>' +
      '<td>' + (m.is_active ? '<span class="pill p-ok">Active</span>' : '<span class="pill p-mut">Inactive</span>') + '</td>' +
      '<td><button class="btn ' + (m.is_active ? 'r' : 'g') + ' sm" onclick="adminToggleMachine(' + m.id + ',' + (!m.is_active) + ')">' + (m.is_active ? 'Deactivate' : 'Activate') + '</button></td></tr>';
  }).join('');
  return '<div class="card" style="margin-bottom:14px"><h4 style="margin-bottom:4px;font-size:15px">Machines</h4>' +
    '<div class="muted" style="margin-bottom:10px">Populates the LT self-service portal\'s machine picker.</div>' +
    '<div style="overflow-x:auto"><table><thead><tr><th>Name</th><th>Status</th><th></th></tr></thead><tbody>' + rows + '</tbody></table></div></div>' +
    '<div class="card"><h4 style="margin-bottom:10px;font-size:14px">Add machine</h4><div class="grid3">' +
    '<div class="fld"><label>Machine name</label><input id="am_name" placeholder="Analyzer XL-200"></div>' +
    '<div class="fld" style="display:flex;align-items:flex-end"><button class="btn" onclick="adminAddMachine()">Add machine</button></div>' +
    '</div></div>';
}
function adminAddMachine() {
  var name = gv('am_name'); if (!name) return toast('Machine name is required');
  api('POST', '/admin/machines', { name: name }).then(function () { toast('Machine added'); loadAdminSection('machines'); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}
function adminToggleMachine(id, active) {
  api('PUT', '/admin/machines/' + id, { is_active: active }).then(function () { toast(active ? 'Activated' : 'Deactivated'); loadAdminSection('machines'); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}

function viewAdminSla() {
  if (!ADMIN_SLA) return '<div class="card"><div class="empty">Loading…</div></div>';
  var tat = ADMIN_SLA.tat || {}, sla = ADMIN_SLA.sla || {};
  var dispatchOn = ADMIN_DISPATCH && ADMIN_DISPATCH.local_team_lead_enabled;
  return '<div class="card" style="margin-bottom:14px"><h4 style="margin-bottom:4px;font-size:15px">Local Team Lead routing <span class="pill p-mut">Future feature</span></h4>' +
    '<div class="muted" style="margin-bottom:12px">Off by default: every team\'s Team Executive (statewide) handles every district. Turn this on once you\'ve set up Local Team Leads (Users tab - give a Team Executive a District) to route new tickets and the 50% SLA warning to that district\'s lead instead - any district without a lead configured keeps falling back to the statewide Team Executive.</div>' +
    '<button class="btn ' + (dispatchOn ? 'g' : 'o') + ' sm" onclick="adminToggleDispatch(' + (!dispatchOn) + ')">' + (dispatchOn ? 'Enabled — turn off' : 'Disabled — turn on') + '</button>' +
    '</div>' +
    '<div class="card" style="margin-bottom:14px"><h4 style="margin-bottom:4px;font-size:15px">TAT per priority (minutes)</h4>' +
    '<div class="muted" style="margin-bottom:12px">Approved SLA/TAT values — editable once the official SLA is signed off.</div><div class="grid3">' +
    Object.keys(tat).map(function (k) { return '<div class="fld"><label>' + k + '</label><input id="sla_tat_' + k + '" value="' + esc(tat[k]) + '"></div>'; }).join('') +
    '</div></div>' +
    '<div class="card"><h4 style="margin-bottom:4px;font-size:15px">SLA tiers</h4>' +
    '<div class="muted" style="margin-bottom:12px">A ticket goes AT RISK / CRITICAL once time-left drops to or below max(floor minutes, TAT &times; fraction).</div>' +
    '<div class="grid3">' +
    '<div class="fld"><label>At-risk floor (min)</label><input id="sla_arm" value="' + esc(sla.at_risk_minutes) + '"></div>' +
    '<div class="fld"><label>At-risk fraction (0-1)</label><input id="sla_arf" value="' + esc(sla.at_risk_fraction) + '"></div>' +
    '<div class="fld"><label>Critical floor (min)</label><input id="sla_cm" value="' + esc(sla.critical_minutes) + '"></div>' +
    '<div class="fld"><label>Critical fraction (0-1)</label><input id="sla_cf" value="' + esc(sla.critical_fraction) + '"></div>' +
    '<div class="fld"><label>Resolved follow-up (hours)</label><input id="sla_rfh" value="' + esc(sla.resolved_followup_hours) + '"></div>' +
    '<div class="fld"><label>Reopen window (hours)</label><input id="sla_rwh" value="' + esc(sla.reopen_window_hours) + '"></div>' +
    '<div class="fld" style="display:flex;align-items:flex-end"><button class="btn" onclick="adminSaveSla()">Save</button></div>' +
    '</div></div>' +
    '<div class="card"><h4 style="margin-bottom:4px;font-size:15px">VIP escalation keywords</h4>' +
    '<div class="muted" style="margin-bottom:12px">A new ticket auto-escalates to P1 if the problem text contains any of these (case-insensitive).</div>' +
    '<div class="fld"><label>Keywords (comma-separated)</label><input id="sla_vipkw" value="' + esc((ADMIN_SLA.vip_keywords || []).join(', ')) + '"></div>' +
    '<button class="btn o sm" onclick="adminSaveVipKeywords()">Save keywords</button></div>';
}
function adminToggleDispatch(enabled) {
  api('PUT', '/admin/dispatch', { local_team_lead_enabled: enabled }).then(function () { toast(enabled ? 'Local Team Lead routing enabled' : 'Local Team Lead routing disabled'); loadAdminSection('sla'); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}
function adminSaveSla() {
  var tat = {}; Object.keys(ADMIN_SLA.tat || {}).forEach(function (k) { tat[k] = gv('sla_tat_' + k); });
  var sla = { at_risk_minutes: gv('sla_arm'), at_risk_fraction: gv('sla_arf'), critical_minutes: gv('sla_cm'), critical_fraction: gv('sla_cf'), resolved_followup_hours: gv('sla_rfh'), reopen_window_hours: gv('sla_rwh') };
  api('PUT', '/admin/sla', { tat: tat, sla: sla }).then(function () { toast('Saved'); loadAdminSection('sla'); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}
function adminSaveVipKeywords() {
  var keywords = gv('sla_vipkw').split(',').map(function (s) { return s.trim(); }).filter(Boolean);
  api('PUT', '/admin/sla', { vip_keywords: keywords }).then(function () { toast('Saved'); loadAdminSection('sla'); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}

function searchAdminUsers() {
  var el = document.getElementById('au_search');
  if (el) {
    ADMIN_USERS_Q = el.value;
    ADMIN_LOADED.users = false;
    loadAdminSection('users');
  }
}

function viewAdminUsers() {
  var roleOpts = function (sel) { return ADMIN_ROLES.map(function (r) { return '<option value="' + r + '"' + (r === sel ? ' selected' : '') + '>' + esc(roleLabel(r)) + '</option>'; }).join(''); };
  var mgrName = function (id) { var u = ADMIN_USERS.find(function (x) { return x.id === id; }); return u ? u.name : ''; };
  var distName = function (id) { var d = ADMIN_DISTRICTS.find(function (x) { return x.id === id; }); return d ? d.name : ''; };
  var mandName = function (id) { var m = ADMIN_MANDALS.find(function (x) { return x.id === id; }); return m ? m.name : ''; };
  var vehName = function (id) { var v = ADMIN_VEHICLES.find(function (x) { return x.id === id; }); return v ? v.registration_no : ''; };
  var isOrgWide = function (role) { return role === 'CC_MANAGER' || role === 'CALL_TAKER'; };
  var rows = ADMIN_USERS.map(function (u) {
    var loc;
    if (u.role === 'LT') loc = [distName(u.district_id), mandName(u.mandal_id), vehName(u.vehicle_id)].filter(Boolean).join(' / ') || '—';
    else if (!isOrgWide(u.role)) loc = distName(u.district_id) || '—';
    else loc = '—';
    var dispatchLabel = u.is_team_manager ? (u.district_id ? ('Local Team Lead · ' + esc(distName(u.district_id) || '?')) : 'Team Executive') : '';
    return '<tr><td><b>' + esc(u.username) + '</b></td><td>' + esc(u.name) + '</td>' +
      '<td><select id="au_role_' + u.id + '">' + roleOpts(u.role) + '</select> <button class="btn o sm" onclick="adminChangeRole(' + u.id + ')">Apply</button></td>' +
      '<td>' + esc(u.hr_emp_code || '—') + '</td>' +
      '<td>' + esc(u.reporting_manager_id ? mgrName(u.reporting_manager_id) : '—') + '</td>' +
      '<td><button class="btn ' + (u.is_team_manager ? 'g' : 'o') + ' sm" onclick="adminToggleTeamManager(' + u.id + ',' + (!u.is_team_manager) + ')">' + (u.is_team_manager ? 'Remove' : 'Make executive') + '</button>' +
      (dispatchLabel ? (' <span class="pill p-mut">' + dispatchLabel + '</span>') : '') + '</td>' +
      '<td>' + esc(loc) + (!isOrgWide(u.role) ? (' <button class="btn o sm" onclick="adminEditUserLocation(' + u.id + ')">Edit</button>') : '') + '</td>' +
      '<td>' + (u.active ? '<span class="pill p-ok">Active</span>' : '<span class="pill p-mut">Inactive</span>') + '</td>' +
      '<td style="display:flex;gap:6px"><button class="btn o sm" onclick="adminResetPassword(' + u.id + ')">Reset password</button>' +
      '<button class="btn ' + (u.active ? 'r' : 'g') + ' sm" onclick="adminToggleUser(' + u.id + ',' + (!u.active) + ')">' + (u.active ? 'Deactivate' : 'Activate') + '</button></td></tr>';
  }).join('');
  var mgrOpts = '<option value="">No reporting manager</option>' + ADMIN_USERS.filter(function (u) { return u.active; }).map(function (u) { return '<option value="' + u.id + '">' + esc(u.name) + ' (' + esc(u.username) + ')</option>'; }).join('');
  var distOpts = '<option value="">No district</option>' + ADMIN_DISTRICTS.filter(function (d) { return d.is_active; }).map(function (d) { return '<option value="' + d.id + '">' + esc(d.name) + '</option>'; }).join('');
  var mandOpts = '<option value="">No mandal</option>' + ADMIN_MANDALS.filter(function (m) { return m.is_active; }).map(function (m) { return '<option value="' + m.id + '">' + esc(m.name) + '</option>'; }).join('');
  var vehOpts = '<option value="">No vehicle</option>' + ADMIN_VEHICLES.filter(function (v) { return v.is_active; }).map(function (v) { return '<option value="' + v.id + '">' + esc(v.registration_no) + '</option>'; }).join('');
    return '<div class="card" style="margin-bottom:14px">' +
      '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">' +
        '<h4 style="font-size:14px;margin:0">Users</h4>' +
        '<div style="display:flex;gap:6px">' +
          '<input type="text" id="au_search" value="' + esc(ADMIN_USERS_Q) + '" placeholder="Search users..." onkeydown="if(event.key===\'Enter\') searchAdminUsers()">' +
          '<button class="btn sm" onclick="searchAdminUsers()">Search</button>' +
        '</div>' +
      '</div>' +
      '<div style="overflow-x:auto"><table><thead><tr><th>Username</th><th>Name</th><th>Role</th><th>HR code</th><th>Reports to</th><th>Dispatch</th><th>Location</th><th>Status</th><th></th></tr></thead><tbody>' + rows + '</tbody></table></div></div>' +
      '<div class="card"><h4 style="margin-bottom:10px;font-size:14px">Add user</h4><div class="grid3">' +
    '<div class="fld"><label>Username</label><input id="au_uname" placeholder="tech6"></div>' +
    '<div class="fld"><label>Name</label><input id="au_name"></div>' +
    '<div class="fld"><label>Role</label><select id="au_new_role">' + roleOpts() + '</select></div>' +
    '<div class="fld"><label>Phone</label><input id="au_phone"></div>' +
    '<div class="fld"><label>Temporary password</label><input id="au_pw" placeholder="min 8 characters"></div>' +
    '<div class="fld"><label>HR employee code</label><input id="au_hr_code" placeholder="EMP1234"></div>' +
    '<div class="fld"><label>Reporting manager</label><select id="au_report_to">' + mgrOpts + '</select></div>' +
    '<div class="fld" style="display:flex;align-items:center;gap:8px"><input type="checkbox" id="au_is_manager" style="width:auto"> <label style="margin:0;text-transform:none;font-size:13px;font-weight:600;color:var(--ink2)">Team Executive for this role</label></div>' +
    '</div>' +
    '<div class="muted" style="margin:4px 0 10px">Location profile — for an LT this auto-fills their self-service portal (never re-asked); for a Team Executive, setting a District turns them into that district\'s Local Team Lead once the Global Team Executive enables Local Team Lead routing (SLA &amp; TAT tab) - leave it blank to keep them statewide.</div>' +
    '<div class="grid3">' +
    '<div class="fld"><label>District</label><select id="au_district">' + distOpts + '</select></div>' +
    '<div class="fld"><label>Mandal (LT only)</label><select id="au_mandal">' + mandOpts + '</select></div>' +
    '<div class="fld"><label>Vehicle (LT only)</label><select id="au_vehicle">' + vehOpts + '</select></div>' +
    '<div class="fld" style="display:flex;align-items:flex-end"><button class="btn" onclick="adminCreateUser()">Add user</button></div>' +
    '</div></div>';
}
function adminCreateUser() {
  var username = gv('au_uname'), name = gv('au_name'), role = document.getElementById('au_new_role').value, phone = gv('au_phone'), pw = gv('au_pw'),
    hrCode = gv('au_hr_code'), reportTo = document.getElementById('au_report_to').value, isManager = document.getElementById('au_is_manager').checked,
    districtId = document.getElementById('au_district').value, mandalId = document.getElementById('au_mandal').value, vehicleId = document.getElementById('au_vehicle').value;
  if (!username || !name || !pw) return toast('Username, name and password are required');
  api('POST', '/admin/users', {
    username: username, name: name, role: role, phone: phone, password: pw,
    hr_emp_code: hrCode, reporting_manager_id: reportTo ? +reportTo : null, is_team_manager: isManager,
    district_id: districtId ? +districtId : null, mandal_id: mandalId ? +mandalId : null, vehicle_id: vehicleId ? +vehicleId : null
  })
    .then(function () { toast('User created'); loadAdminSection('users'); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}
function adminEditUserLocation(id) {
  var u = ADMIN_USERS.find(function (x) { return x.id === id; }); if (!u) return;
  var isLt = u.role === 'LT';
  var distOpts = '<option value="">No district</option>' + ADMIN_DISTRICTS.filter(function (d) { return d.is_active; })
    .map(function (d) { return '<option value="' + d.id + '"' + (d.id === u.district_id ? ' selected' : '') + '>' + esc(d.name) + '</option>'; }).join('');
  var fields = '<div class="fld"><label for="em_district">District</label><select id="em_district">' + distOpts + '</select></div>';
  if (isLt) {
    var mandOpts = '<option value="">No mandal</option>' + ADMIN_MANDALS.filter(function (m) { return m.is_active; })
      .map(function (m) { return '<option value="' + m.id + '"' + (m.id === u.mandal_id ? ' selected' : '') + '>' + esc(m.name) + '</option>'; }).join('');
    var vehOpts = '<option value="">No vehicle</option>' + ADMIN_VEHICLES.filter(function (v) { return v.is_active; })
      .map(function (v) { return '<option value="' + v.id + '"' + (v.id === u.vehicle_id ? ' selected' : '') + '>' + esc(v.registration_no) + '</option>'; }).join('');
    fields += '<div class="fld"><label for="em_mandal">Mandal</label><select id="em_mandal">' + mandOpts + '</select></div>' +
      '<div class="fld"><label for="em_vehicle">Vehicle</label><select id="em_vehicle">' + vehOpts + '</select></div>';
  }
  editModal('Edit location — ' + u.name, fields, function () {
    // Clear-sentinel convention (app/crud/crud_user.py's update_user): 0
    // clears the field to NULL, None/omitted leaves it untouched - always
    // send a real number, never null, or a cleared field silently no-ops.
    var patch = { district_id: gv('em_district') ? +gv('em_district') : 0 };
    if (isLt) {
      patch.mandal_id = gv('em_mandal') ? +gv('em_mandal') : 0;
      patch.vehicle_id = gv('em_vehicle') ? +gv('em_vehicle') : 0;
    }
    api('PUT', '/admin/users/' + id, patch)
      .then(function () { closeModal2(); toast('Location updated'); loadAdminSection('users'); })
      .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
  });
}
function adminChangeRole(id) {
  var role = document.getElementById('au_role_' + id).value;
  api('PUT', '/admin/users/' + id, { role: role }).then(function () { toast('Role updated'); loadAdminSection('users'); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}
function adminToggleUser(id, active) {
  api('PUT', '/admin/users/' + id, { active: active }).then(function () { toast(active ? 'Activated' : 'Deactivated'); loadAdminSection('users'); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}
function adminToggleTeamManager(id, isManager) {
  api('PUT', '/admin/users/' + id, { is_team_manager: isManager }).then(function () { toast(isManager ? 'Now a Team Executive' : 'Team Executive removed'); loadAdminSection('users'); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}
function adminResetPassword(id) {
  editModal('Reset password',
    '<div class="fld"><label for="em_pw">New temporary password (min 8 characters)</label><input id="em_pw" type="password"></div>',
    function () {
      var pw = gv('em_pw');
      if (pw.length < 8) { toast('Password must be at least 8 characters'); return; }
      api('PUT', '/admin/users/' + id, { password: pw }).then(function () { closeModal2(); toast('Password reset'); })
        .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
    });
}

function viewAdminAudit() {
  if (!ADMIN_AUDIT.length) return '<div class="card"><div class="empty">No admin actions recorded yet.</div></div>';
  var rows = ADMIN_AUDIT.map(function (e) {
    return '<tr><td>' + esc(e.at) + '</td><td>' + esc(e.actor) + '<div class="muted">' + esc(e.actor_role) + '</div></td>' +
      '<td>' + esc(e.action) + '</td><td>' + esc(e.entity_type) + ' · ' + esc(e.entity_id) + '</td><td>' + esc(e.detail || '') + '</td></tr>';
  }).join('');
  return '<div class="card"><h4 style="margin-bottom:10px;font-size:14px">Recent admin activity</h4>' +
    '<div style="overflow-x:auto"><table><thead><tr><th>When</th><th>Who</th><th>Action</th><th>Entity</th><th>Detail</th></tr></thead><tbody>' + rows + '</tbody></table></div></div>';
}

if (TOK) { boot(); }