/* Register Call pre-fill: vehicle geo lookup (Segment Number, Secretariat,
   Village) and a caller employee search (Designation, Emp ID). Both call
   the same external system/auth as Admin > Hierarchy Source, via two more
   URLs configured there (vehicle_lookup_url / employee_lookup_url). Neither
   ever blocks the form - unconfigured or unreachable just means the fields
   stay editable for manual entry. */

var LOOKUP_EMP_DEBOUNCE = null, LOOKUP_EMP_RESULTS = [];

function initLookupUI() {
  var geoHost = document.getElementById('lookup_geo_fields');
  if (geoHost) {
    geoHost.innerHTML =
      '<div class="grid3" style="margin-top:10px">' +
        '<div class="fld"><label>Segment Number</label><input id="f_segment" placeholder="Auto-filled from vehicle, or enter manually"></div>' +
        '<div class="fld"><label>Secretariat</label><input id="f_secretariat" placeholder="Auto-filled from vehicle, or enter manually"></div>' +
        '<div class="fld"><label>Village</label><input id="f_village" placeholder="Auto-filled from vehicle, or enter manually"></div>' +
      '</div>' +
      '<div class="muted" id="f_veh_lookup_status" style="font-size:12px;margin-top:2px"></div>';
  }
  var callerHost = document.getElementById('lookup_caller_fields');
  if (callerHost) {
    callerHost.innerHTML =
      '<div class="grid3" style="margin-top:10px">' +
        '<div class="fld"><label>Search Employee (optional)</label><div style="position:relative">' +
          '<input id="f_emp_search" placeholder="Type name or emp ID" oninput="empSearchInput()" onfocus="showEmpDropdown()" onblur="hideEmpDropdown()" autocomplete="off" style="width:100%">' +
          '<div id="emp_dropdown" class="hide" style="position:absolute;top:100%;left:0;right:0;max-height:200px;overflow-y:auto;background:var(--card);border:1px solid var(--line);border-radius:8px;z-index:100;box-shadow:0 10px 25px rgba(0,0,0,0.05);padding:4px"></div>' +
        '</div></div>' +
        '<div class="fld"><label>Designation</label><input id="f_designation" placeholder="Auto-filled when an employee is selected"></div>' +
        '<div class="fld"><label>Employee ID</label><input id="f_empid" placeholder="Auto-filled when an employee is selected"></div>' +
      '</div>';
  }
}

function onVehicleSelectedForLookup(regNo) {
  var status = document.getElementById('f_veh_lookup_status');
  if (!regNo) return;
  if (status) status.textContent = 'Looking up vehicle location…';
  api('GET', '/tickets/lookup/vehicle?registration_no=' + encodeURIComponent(regNo)).then(function (r) {
    if (!status) return;
    if (!r.configured) { status.textContent = ''; return; }
    if (!r.found) { status.textContent = 'No location on file for this vehicle — enter Segment/Secretariat/Village manually.'; return; }
    var d = r.data || {};
    if (d.segment_number) document.getElementById('f_segment').value = d.segment_number;
    if (d.secretariat) document.getElementById('f_secretariat').value = d.secretariat;
    if (d.village) document.getElementById('f_village').value = d.village;
    status.textContent = 'Location auto-filled from vehicle lookup.';
  }).catch(function () { if (status) status.textContent = ''; });
}

function empSearchInput() {
  clearTimeout(LOOKUP_EMP_DEBOUNCE);
  var q = gv('f_emp_search');
  var dd = document.getElementById('emp_dropdown');
  if (!dd) return;
  dd.classList.remove('hide');
  if (q.length < 2) { dd.innerHTML = '<div style="padding:8px;color:var(--mut)">Type at least 2 chars...</div>'; return; }
  dd.innerHTML = '<div style="padding:8px;color:var(--mut)">Searching...</div>';
  LOOKUP_EMP_DEBOUNCE = setTimeout(function () {
    api('GET', '/tickets/lookup/employees?q=' + encodeURIComponent(q)).then(function (r) {
      if (!r.configured) { dd.innerHTML = '<div style="padding:8px;color:var(--mut)">Employee lookup not configured — enter details manually</div>'; return; }
      LOOKUP_EMP_RESULTS = r.results || [];
      if (!LOOKUP_EMP_RESULTS.length) { dd.innerHTML = '<div style="padding:8px;color:var(--mut)">No matches found</div>'; return; }
      dd.innerHTML = LOOKUP_EMP_RESULTS.map(function (e, i) {
        return '<div class="dropdown-item" onmousedown="selectEmp(' + i + ')" style="padding:8px;cursor:pointer;">' +
          esc(e.name || e.emp_id || '') + (e.designation ? (' <span class="muted">(' + esc(e.designation) + ')</span>') : '') + '</div>';
      }).join('');
    }).catch(function () { dd.innerHTML = '<div style="padding:8px;color:var(--mut)">Error loading employees</div>'; });
  }, 300);
}
function showEmpDropdown() { empSearchInput(); }
function hideEmpDropdown() { setTimeout(function () { var dd = document.getElementById('emp_dropdown'); if (dd) dd.classList.add('hide'); }, 200); }
function selectEmp(i) {
  var e = LOOKUP_EMP_RESULTS[i];
  if (!e) return;
  document.getElementById('f_emp_search').value = e.name || '';
  document.getElementById('f_designation').value = e.designation || '';
  document.getElementById('f_empid').value = e.emp_id || '';
  var cname = document.getElementById('f_cname');
  if (cname && !cname.value) cname.value = e.name || '';
  document.getElementById('emp_dropdown').classList.add('hide');
}

function lookupExtraFields() {
  var g = function (i) { var e = document.getElementById(i); return e ? e.value.trim() : ''; };
  return {
    segment_number: g('f_segment') || undefined,
    secretariat: g('f_secretariat') || undefined,
    village: g('f_village') || undefined,
    caller_designation: g('f_designation') || undefined,
    caller_emp_id: g('f_empid') || undefined
  };
}
