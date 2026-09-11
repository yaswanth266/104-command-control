var API = '/cccapi', TOK = sessionStorage.getItem('ccc_tok') || localStorage.getItem('ccc_tok') || '', ME = null, META = null, TAB = 'queue', ROWS = [], ROWTOTAL = 0, DASH = null, LAST_DASH_STR = '',
  FILT = { status: '', scope: '', team: '', priority: '', category: '', mmu_vehicle: '', district: '', district_id: '', mandal_id: '', date_preset: '', date_from: '', date_to: '', time_from: '', time_to: '', shift: '', q: '', page: 1, page_size: 50, sort_by: 'created_at', sort_desc: true },
  DASH_FILT = { district: '', team: '', mmu_vehicle: '', date_preset: '', date_from: '', date_to: '' },
  NOTIFS = [], NOTIF_OPEN = false, POLL_TIMER = null, CLOCK_TIMER = null,
  ADMIN_TAB = 'teams', ADMIN_TEAMS = [], ADMIN_CATEGORIES = [], ADMIN_SLA = null, ADMIN_DISPATCH = null, ADMIN_USERS = [], ADMIN_USERS_Q = '', ADMIN_ROLES = [], ADMIN_AUDIT = [], ADMIN_LOADED = {},
  ADMIN_DISTRICTS = [], ADMIN_ZONES = [], ADMIN_MANDALS = [], ADMIN_VEHICLES = [], ADMIN_REASONS = [], ADMIN_MACHINES = [],
  LT_CATEGORIES = [], LT_REASONS = [], LT_SELECTED_REASONS = [], LT_MACHINE_RESULTS = [], LT_TICKETS = [],
  AUDIO_CTX = null, SOUND_ENABLED = localStorage.getItem('ccc_sound_enabled') !== '0',
  AUTO_REFRESH_ENABLED = true, AUTO_REFRESH_SECS = 20, REFRESH_COUNTDOWN = 20, LAST_MAX_TICKET_ID = 0, CURRENT_MODAL_TICKET_ID = null;

function getAudioContext() {
  if (!AUDIO_CTX) {
    var AudioContext = window.AudioContext || window.webkitAudioContext;
    if (AudioContext) AUDIO_CTX = new AudioContext();
  }
  if (AUDIO_CTX && AUDIO_CTX.state === 'suspended') {
    AUDIO_CTX.resume();
  }
  return AUDIO_CTX;
}

function playAlertSound(type) {
  if (!SOUND_ENABLED) return;
  try {
    var ctx = getAudioContext();
    if (!ctx) return;
    var now = ctx.currentTime;
    
    if (type === 'p1' || type === 'critical') {
      // Emergency P1 Two-Tone Warning: D5 (587Hz) -> A5 (880Hz) -> D6 (1174Hz)
      var notes = [587.33, 880.00, 1174.66];
      notes.forEach(function (freq, idx) {
        var osc = ctx.createOscillator();
        var gain = ctx.createGain();
        osc.type = 'triangle';
        osc.frequency.setValueAtTime(freq, now + idx * 0.12);
        gain.gain.setValueAtTime(0.35, now + idx * 0.12);
        gain.gain.exponentialRampToValueAtTime(0.001, now + idx * 0.12 + 0.35);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(now + idx * 0.12);
        osc.stop(now + idx * 0.12 + 0.35);
      });
    } else {
      // Melodic Standard Notification Chime: C5 (523Hz) -> E5 (659Hz) -> G5 (784Hz)
      var notes = [523.25, 659.25, 783.99];
      notes.forEach(function (freq, idx) {
        var osc = ctx.createOscillator();
        var gain = ctx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(freq, now + idx * 0.1);
        gain.gain.setValueAtTime(0.25, now + idx * 0.1);
        gain.gain.exponentialRampToValueAtTime(0.001, now + idx * 0.1 + 0.4);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(now + idx * 0.1);
        osc.stop(now + idx * 0.1 + 0.4);
      });
    }
  } catch (e) {
    console.warn('Audio alert error:', e);
  }
}

function toggleSoundAlerts() {
  SOUND_ENABLED = !SOUND_ENABLED;
  localStorage.setItem('ccc_sound_enabled', SOUND_ENABLED ? '1' : '0');
  if (SOUND_ENABLED) {
    playAlertSound('new');
    toast('Audio alerts turned ON');
  } else {
    toast('Audio alerts MUTED');
  }
  var btn = document.getElementById('sound_toggle_btn');
  if (btn) {
    btn.className = 'sound-toggle-btn ' + (SOUND_ENABLED ? 'on' : 'off');
    if (SOUND_ENABLED) {
      btn.innerHTML = '<svg class="sound-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:4px"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"></path></svg><span id="sound_label">Audio ON</span>';
    } else {
      btn.innerHTML = '<svg class="sound-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:4px"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><line x1="23" y1="9" x2="17" y2="15"></line><line x1="17" y1="9" x2="23" y2="15"></line></svg><span id="sound_label">Audio Muted</span>';
    }
  }
}

function toggleAutoRefresh() {
  AUTO_REFRESH_ENABLED = !AUTO_REFRESH_ENABLED;
  REFRESH_COUNTDOWN = AUTO_REFRESH_SECS;
  toast(AUTO_REFRESH_ENABLED ? 'Live Queue Auto-Refresh Active' : 'Auto-Refresh Paused');
  var btn = document.getElementById('auto_refresh_btn');
  if (btn) {
    btn.className = 'auto-refresh-btn ' + (AUTO_REFRESH_ENABLED ? 'active' : 'paused');
    btn.innerHTML = '<span class="pulse-dot"></span><span id="auto_refresh_label">' + (AUTO_REFRESH_ENABLED ? 'Live' : 'Paused') + '</span>';
  }
}

function testAudioAlert() {
  playAlertSound('p1');
  toast('Tested P1 Emergency Audio Chime');
}

function esc(s) { return (s == null ? '' : String(s)).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
function api(m, p, b) {
  var h = { 'Content-Type': 'application/json' }; if (TOK) h.Authorization = 'Bearer ' + TOK;
  return fetch(API + p, { method: m, headers: h, body: b ? JSON.stringify(b) : undefined }).then(function (r) {
    if (r.status === 401) { logout(); throw 'auth'; }
    return r.json().then(function (d) { if (!r.ok) throw (d.detail || ('HTTP ' + r.status)); return d; });
  });
}
function toast(m) { var t = document.createElement('div'); t.className = 'toast'; t.textContent = m; document.body.appendChild(t); setTimeout(function () { t.style.transition = 'all 0.3s ease'; t.style.opacity = '0'; t.style.transform = 'translateX(-50%) translateY(20px)'; setTimeout(function () { t.remove(); }, 300); }, 3000); }
function doLogin() {
  var u = document.getElementById('u').value.trim(), p = document.getElementById('p').value;
  document.getElementById('lerr').textContent = '';
  api('POST', '/auth', { username: u, password: p }).then(function (d) {
    TOK = d.token;
    ME = d.user;
    sessionStorage.setItem('ccc_tok', TOK);
    sessionStorage.setItem('ccc_me', JSON.stringify(d.user));
    localStorage.setItem('ccc_tok', TOK);
    localStorage.setItem('ccc_me', JSON.stringify(d.user));
    saveState();
    boot();
  }).catch(function (e) {
    document.getElementById('lerr').textContent = (e === 'auth' ? '' : (e || 'Login failed'));
  });
}
function togglePasswordVisibility(inputId, btnId) {
  var inp = document.getElementById(inputId);
  var btn = document.getElementById(btnId);
  if (!inp || !btn) return;
  var isPw = inp.type === 'password';
  inp.type = isPw ? 'text' : 'password';
  var eyeOpen = btn.querySelector('.eye-open');
  var eyeClosed = btn.querySelector('.eye-closed');
  if (eyeOpen && eyeClosed) {
    if (isPw) {
      eyeOpen.classList.add('hide');
      eyeClosed.classList.remove('hide');
    } else {
      eyeOpen.classList.remove('hide');
      eyeClosed.classList.add('hide');
    }
  }
}

function toggleForgotView(showForgot) {
  var loginSec = document.getElementById('login_section');
  var forgotSec = document.getElementById('forgot_section');
  var lerr = document.getElementById('lerr');
  var fmsg = document.getElementById('forgot_msg');
  if (lerr) lerr.textContent = '';
  if (fmsg) { fmsg.textContent = ''; fmsg.style.color = ''; }
  if (showForgot) {
    if (loginSec) loginSec.classList.add('hide');
    if (forgotSec) forgotSec.classList.remove('hide');
    var fu = document.getElementById('forgot_u');
    if (fu) setTimeout(function () { fu.focus(); }, 50);
  } else {
    if (loginSec) loginSec.classList.remove('hide');
    if (forgotSec) forgotSec.classList.add('hide');
    var u = document.getElementById('u');
    if (u) setTimeout(function () { u.focus(); }, 50);
  }
}

function doForgotPassword() {
  var u = (document.getElementById('forgot_u').value || '').trim();
  var phone = (document.getElementById('forgot_phone').value || '').trim();
  var np = (document.getElementById('forgot_p').value || '').trim();
  var cp = (document.getElementById('forgot_cp').value || '').trim();
  var msg = document.getElementById('forgot_msg');
  if (msg) { msg.textContent = ''; msg.style.color = 'var(--crit)'; }

  if (!u) {
    if (msg) msg.textContent = 'Please enter your username';
    return;
  }
  if (!phone) {
    if (msg) msg.textContent = 'Please enter your registered mobile number';
    return;
  }
  if (!np) {
    if (msg) msg.textContent = 'Please enter a new password';
    return;
  }
  if (np.length < 8) {
    if (msg) msg.textContent = 'Password must be at least 8 characters';
    return;
  }
  if (np !== cp) {
    if (msg) msg.textContent = 'New passwords do not match';
    return;
  }

  if (msg) { msg.style.color = 'var(--pur)'; msg.textContent = 'Verifying and resetting password...'; }
  api('POST', '/auth/forgot-password', { username: u, phone: phone, new_password: np })
    .then(function (d) {
      if (msg) {
        msg.style.color = '#059669';
        msg.textContent = d.message || 'Password reset successfully! Returning to sign in...';
      }
      setTimeout(function () {
        toggleForgotView(false);
        var uInp = document.getElementById('u');
        var pInp = document.getElementById('p');
        if (uInp) uInp.value = u;
        if (pInp) { pInp.value = ''; pInp.focus(); }
        toast('Password reset successfully! Please sign in.');
      }, 1400);
    })
    .catch(function (e) {
      if (msg) {
        msg.style.color = 'var(--crit)';
        msg.textContent = typeof e === 'string' ? e : (e.detail || 'Password reset failed');
      }
    });
}

function logout() {
  TOK = '';
  ME = null;
  TAB = 'queue';
  sessionStorage.clear();
  localStorage.removeItem('ccc_tok');
  localStorage.removeItem('ccc_me');
  localStorage.removeItem('ccc_tab');
  localStorage.removeItem('ccc_admin_tab');
  localStorage.removeItem('ccc_filt');
  try { if (window.history && window.history.replaceState) window.history.replaceState(null, null, ' '); else window.location.hash = ''; } catch (e) {}
  if (POLL_TIMER) clearInterval(POLL_TIMER);
  if (CLOCK_TIMER) clearInterval(CLOCK_TIMER);
  var _u = document.getElementById('u'), _p = document.getElementById('p'), _e = document.getElementById('lerr');
  if (_u) _u.value = '';
  if (_p) _p.value = '';
  if (_e) _e.textContent = '';
  toggleForgotView(false);
  document.getElementById('app').classList.add('hide');
  document.getElementById('login').classList.remove('hide');
}
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

function openProfile() {
  closeSidebar();
  document.getElementById('modal').innerHTML = '<div class="ovl" onclick="if(event.target===this)closeModal()"><div class="sheet" style="max-width:520px">' +
    '<div class="sh"><div style="font-size:18px;font-weight:800">My Profile</div><button class="x" onclick="closeModal()">&times;</button></div>' +
    '<div class="sb" id="profile_body">Loading...</div>' +
    '</div></div>';
  api('GET', '/users/me').then(function (p) {
    renderProfileModal(p);
  }).catch(function (e) {
    var b = document.getElementById('profile_body');
    if (b) b.innerHTML = '<div class="err">' + esc(typeof e === 'string' ? e : (e.detail || 'Could not load profile')) + '</div>';
  });
}

function renderProfileModal(p) {
  var b = document.getElementById('profile_body');
  if (!b) return;

  var rows = [
    ['Full Name', esc(p.name)],
    ['Username', '@' + esc(p.username)],
    ['Role', esc(roleLabel(p.role)) + (p.is_team_manager ? ' <span style="display:inline-block;margin-left:6px;padding:1px 7px;border-radius:10px;font-size:10.5px;font-weight:800;background:#F5F0FF;color:var(--pur)">TEAM MANAGER</span>' : '')],
    ['Phone', esc(p.phone || '-')]
  ];
  if (p.hr_emp_code) rows.push(['HR Employee Code', esc(p.hr_emp_code)]);
  if (p.team) rows.push(['Team', esc(p.team.name)]);
  if (p.reporting_manager) rows.push(['Reports To', esc(p.reporting_manager.name) + ' (@' + esc(p.reporting_manager.username) + ')']);
  if (p.district) rows.push(['District', esc(p.district.name)]);
  if (p.mandal) rows.push(['Mandal', esc(p.mandal.name)]);
  if (p.vehicle) rows.push(['Assigned Vehicle', esc(p.vehicle.registration_no)]);

  var infoHtml = rows.map(function (r) {
    return '<div style="display:flex;justify-content:space-between;gap:12px;padding:7px 0;border-bottom:1px solid var(--line)">' +
      '<span style="opacity:.75">' + r[0] + '</span><span style="font-weight:600;text-align:right">' + r[1] + '</span></div>';
  }).join('');

  var routingNote = '';
  if (p.role === 'LT') {
    routingNote = '<div class="s" style="margin-top:10px">Your District, Mandal and Vehicle above are auto-attached to every ticket you raise from the field, and decide which team it is routed to. If any of these are missing or wrong, ask your CC Manager to update them.</div>';
  } else if (p.team) {
    routingNote = '<div class="s" style="margin-top:10px">Tickets classified under your team (' + esc(p.team.name) + ') land in your team queue' + (p.reporting_manager ? ', with escalations visible to ' + esc(p.reporting_manager.name) : '') + '.</div>';
  }

  b.innerHTML =
    '<div style="font-weight:700;font-size:13.5px;margin-bottom:4px;color:var(--ink)">Account Details</div>' +
    infoHtml + routingNote +
    '<div style="font-weight:700;font-size:13.5px;margin:18px 0 8px;color:var(--ink);border-top:1px solid var(--line);padding-top:14px">Change Password</div>' +
    '<div class="fld"><label>Current Password</label><input id="pw_current" type="password" placeholder="Enter current password"></div>' +
    '<div class="fld"><label>New Password (min 8 chars)</label><input id="pw_new" type="password" placeholder="Enter new password"></div>' +
    '<div class="fld"><label>Confirm New Password</label><input id="pw_confirm" type="password" placeholder="Re-enter new password" onkeydown="if(event.key==\'Enter\')saveProfilePassword()"></div>' +
    '<div class="err" id="profile_pw_msg"></div>' +
    '<div style="display:flex;justify-content:flex-end;gap:10px;margin-top:12px">' +
      '<button class="btn" onclick="saveProfilePassword()">Update Password</button>' +
    '</div>';
}

function saveProfilePassword() {
  var cur = gv('pw_current'), np = gv('pw_new'), cp = gv('pw_confirm');
  var msg = document.getElementById('profile_pw_msg');
  if (msg) { msg.style.color = 'var(--crit)'; msg.textContent = ''; }

  if (!cur) { if (msg) msg.textContent = 'Enter your current password'; return; }
  if (!np) { if (msg) msg.textContent = 'Enter a new password'; return; }
  if (np.length < 8) { if (msg) msg.textContent = 'New password must be at least 8 characters'; return; }
  if (np !== cp) { if (msg) msg.textContent = 'New passwords do not match'; return; }
  if (np === cur) { if (msg) msg.textContent = 'New password must be different from the current password'; return; }

  api('POST', '/users/me/password', { current_password: cur, new_password: np }).then(function (d) {
    toast(d.message || 'Password updated successfully');
    closeModal();
  }).catch(function (e) {
    if (msg) msg.textContent = typeof e === 'string' ? e : (e.detail || 'Could not update password');
  });
}
function saveState() {
  try {
    sessionStorage.setItem('ccc_tab', TAB);
    sessionStorage.setItem('ccc_admin_tab', ADMIN_TAB);
    sessionStorage.setItem('ccc_filt', JSON.stringify(FILT));
    sessionStorage.setItem('ccc_dash_filt', JSON.stringify(DASH_FILT));
    localStorage.setItem('ccc_tab', TAB);
    localStorage.setItem('ccc_admin_tab', ADMIN_TAB);
    localStorage.setItem('ccc_filt', JSON.stringify(FILT));
    localStorage.setItem('ccc_dash_filt', JSON.stringify(DASH_FILT));

    if (CURRENT_MODAL_TICKET_ID) {
      sessionStorage.setItem('ccc_modal_ticket', CURRENT_MODAL_TICKET_ID);
      localStorage.setItem('ccc_modal_ticket', CURRENT_MODAL_TICKET_ID);
    } else {
      sessionStorage.removeItem('ccc_modal_ticket');
      localStorage.removeItem('ccc_modal_ticket');
    }

    // Mirror to URL hash
    var hash = '#' + TAB;
    if (TAB === 'admin') {
      hash += '/' + (ADMIN_TAB || 'teams');
    } else if (TAB === 'queue') {
      var params = [];
      if (FILT.status !== undefined && FILT.status !== null) params.push('status=' + encodeURIComponent(FILT.status));
      if (FILT.scope) params.push('scope=' + encodeURIComponent(FILT.scope));
      if (FILT.team) params.push('team=' + encodeURIComponent(FILT.team));
      if (FILT.district_id) params.push('district_id=' + encodeURIComponent(FILT.district_id));
      if (FILT.q) params.push('q=' + encodeURIComponent(FILT.q));
      if (FILT.date_preset) params.push('date_preset=' + encodeURIComponent(FILT.date_preset));
      if (FILT.date_from) params.push('date_from=' + encodeURIComponent(FILT.date_from));
      if (FILT.date_to) params.push('date_to=' + encodeURIComponent(FILT.date_to));
      if (FILT.sort_by) params.push('sort_by=' + encodeURIComponent(FILT.sort_by));
      if (FILT.sort_desc !== undefined) params.push('sort_desc=' + (FILT.sort_desc ? '1' : '0'));
      if (FILT.page > 1) params.push('page=' + FILT.page);
      if (CURRENT_MODAL_TICKET_ID) params.push('ticket=' + CURRENT_MODAL_TICKET_ID);
      if (params.length) hash += '?' + params.join('&');
    } else if (TAB === 'dash') {
      var dparams = [];
      if (DASH_FILT.district) dparams.push('district=' + encodeURIComponent(DASH_FILT.district));
      if (DASH_FILT.team) dparams.push('team=' + encodeURIComponent(DASH_FILT.team));
      if (DASH_FILT.mmu_vehicle) dparams.push('mmu_vehicle=' + encodeURIComponent(DASH_FILT.mmu_vehicle));
      if (DASH_FILT.date_preset) dparams.push('date_preset=' + encodeURIComponent(DASH_FILT.date_preset));
      if (DASH_FILT.date_from) dparams.push('date_from=' + encodeURIComponent(DASH_FILT.date_from));
      if (DASH_FILT.date_to) dparams.push('date_to=' + encodeURIComponent(DASH_FILT.date_to));
      if (dparams.length) hash += '?' + dparams.join('&');
    }

    if (window.history && window.history.replaceState) {
      window.history.replaceState(null, null, hash);
    } else {
      window.location.hash = hash;
    }
  } catch (e) {}
}

function restoreState() {
  try {
    // 1. First, always restore from storage as baseline
    var savedTab = sessionStorage.getItem('ccc_tab') || localStorage.getItem('ccc_tab');
    if (savedTab) TAB = savedTab;
    else if (ME && ME.role === 'LT') TAB = 'report';
    else TAB = 'queue';

    var savedAdminTab = sessionStorage.getItem('ccc_admin_tab') || localStorage.getItem('ccc_admin_tab');
    if (savedAdminTab) ADMIN_TAB = savedAdminTab;

    var savedFilt = sessionStorage.getItem('ccc_filt') || localStorage.getItem('ccc_filt');
    if (savedFilt) {
      try {
        var f = JSON.parse(savedFilt);
        for (var k in f) {
          if (f.hasOwnProperty(k)) FILT[k] = f[k];
        }
      } catch (e) {}
    }

    var savedDashFilt = sessionStorage.getItem('ccc_dash_filt') || localStorage.getItem('ccc_dash_filt');
    if (savedDashFilt) {
      try {
        var df = JSON.parse(savedDashFilt);
        for (var dk in df) {
          if (df.hasOwnProperty(dk)) DASH_FILT[dk] = df[dk];
        }
      } catch (e) {}
    }

    var savedTicket = sessionStorage.getItem('ccc_modal_ticket') || localStorage.getItem('ccc_modal_ticket');
    if (savedTicket) CURRENT_MODAL_TICKET_ID = parseInt(savedTicket) || null;

    // 2. Override with URL hash if present
    var rawHash = (window.location.hash || '').replace(/^#/, '');
    if (rawHash) {
      var parts = rawHash.split('?');
      var path = parts[0];
      var qs = parts[1] || '';

      if (path.indexOf('admin/') === 0) {
        TAB = 'admin';
        ADMIN_TAB = path.split('/')[1] || ADMIN_TAB || 'teams';
      } else if (path === 'admin') {
        TAB = 'admin';
        if (!ADMIN_TAB) ADMIN_TAB = 'teams';
      } else if (path) {
        TAB = path;
      }

      if (qs) {
        var sp = new URLSearchParams(qs);
        if (TAB === 'dash') {
          if (sp.has('district')) DASH_FILT.district = sp.get('district');
          if (sp.has('team')) DASH_FILT.team = sp.get('team');
          if (sp.has('mmu_vehicle')) DASH_FILT.mmu_vehicle = sp.get('mmu_vehicle');
          if (sp.has('date_preset')) DASH_FILT.date_preset = sp.get('date_preset');
          if (sp.has('date_from')) DASH_FILT.date_from = sp.get('date_from');
          if (sp.has('date_to')) DASH_FILT.date_to = sp.get('date_to');
        } else {
          if (sp.has('status')) FILT.status = sp.get('status');
          if (sp.has('scope')) FILT.scope = sp.get('scope');
          if (sp.has('team')) FILT.team = sp.get('team');
          if (sp.has('district_id')) FILT.district_id = sp.get('district_id');
          if (sp.has('q')) FILT.q = sp.get('q');
          if (sp.has('date_preset')) FILT.date_preset = sp.get('date_preset');
          if (sp.has('date_from')) FILT.date_from = sp.get('date_from');
          if (sp.has('date_to')) FILT.date_to = sp.get('date_to');
          if (sp.has('sort_by')) FILT.sort_by = sp.get('sort_by');
          if (sp.has('sort_desc')) FILT.sort_desc = sp.get('sort_desc') === '1' || sp.get('sort_desc') === 'true';
          if (sp.has('page')) FILT.page = parseInt(sp.get('page')) || 1;
          if (sp.has('ticket')) CURRENT_MODAL_TICKET_ID = parseInt(sp.get('ticket')) || null;
        }
      }
      // Sanitize stale ghost filters
      FILT.mmu_vehicle = '';
      FILT.mandal_id = '';
      FILT.shift = '';
      FILT.time_from = '';
      FILT.time_to = '';
      if (ME && ME.role !== 'CC_MANAGER' && ME.role !== 'ADMIN' && ME.role !== 'CALL_TAKER') {
        FILT.district_id = '';
        FILT.district = '';
        FILT.team = '';
      }
    }
  } catch (e) {}
}

function boot() {
  document.getElementById('login').classList.add('hide');
  document.getElementById('app').classList.remove('hide');
  try {
    ME = ME || JSON.parse(sessionStorage.getItem('ccc_me')) || JSON.parse(localStorage.getItem('ccc_me'));
  } catch (e) { ME = null; }
  if (!ME || !TOK) { logout(); return; }
  document.getElementById('who').innerHTML = '<b>' + esc(ME.name) + '</b>' + esc(roleLabel(ME.role));
  restoreState();
  api('GET', '/meta').then(function (m) {
    META = m;
    render();
    if (TAB === 'queue') load(true);
    else if (TAB === 'dash') load(true);
    else if (TAB === 'mine') load(true);
    else if (TAB === 'admin') loadAdminSection(ADMIN_TAB);
    if (CURRENT_MODAL_TICKET_ID) openT(CURRENT_MODAL_TICKET_ID);
    loadNotifs();
    startPolling();
  }).catch(function (e) {
    if (e === 'auth') logout();
  });
}
function startPolling() {
  if (POLL_TIMER) clearInterval(POLL_TIMER);
  if (CLOCK_TIMER) clearInterval(CLOCK_TIMER);
  
  REFRESH_COUNTDOWN = AUTO_REFRESH_SECS;
  CLOCK_TIMER = setInterval(function () {
    if (!AUTO_REFRESH_ENABLED || !TOK) return;
    REFRESH_COUNTDOWN--;
    if (REFRESH_COUNTDOWN <= 0) {
      REFRESH_COUNTDOWN = AUTO_REFRESH_SECS;
      if (TAB === 'queue') load(false);
      else if (TAB === 'dash') load(false);
      else if (TAB === 'mine') loadLTMine();
      loadNotifs();
    }
  }, 1000);
}
var NAV_EXPANDED = { queue: true, admin: true };

function toggleNavGroup(k) {
  NAV_EXPANDED[k] = !NAV_EXPANDED[k];
  renderNavTree();
}

function toggleSidebar() {
  var sb = document.getElementById('sidebar');
  if (sb) {
    var willShow = !sb.classList.contains('show');
    sb.classList.toggle('show', willShow);
    var bd = document.getElementById('sidebar_backdrop');
    if (bd) bd.classList.toggle('show', willShow);
  }
}

function closeSidebar() {
  var sb = document.getElementById('sidebar');
  if (sb && sb.classList.contains('show')) {
    sb.classList.remove('show');
    var bd = document.getElementById('sidebar_backdrop');
    if (bd) bd.classList.remove('show');
  }
}

function setQueueStatus(st) {
  closeSidebar();
  TAB = 'queue';
  FILT.status = st;
  FILT.scope = '';
  FILT.page = 1;
  NAV_EXPANDED.queue = true;
  saveState();
  render();
  load(true);
}

function setQueueScope(sc) {
  closeSidebar();
  TAB = 'queue';
  FILT.status = 'open';
  FILT.scope = sc;
  FILT.page = 1;
  NAV_EXPANDED.queue = true;
  saveState();
  render();
  load(true);
}

var NAV_ICONS = {
  queue: '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path><polyline points="22,6 12,13 2,6"></polyline></svg>',
  register: '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"></path></svg>',
  report: '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>',
  tickets: '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="7" width="20" height="14" rx="2" ry="2"></rect><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"></path></svg>',
  monitor: '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"></line><line x1="12" y1="20" x2="12" y2="4"></line><line x1="6" y1="20" x2="6" y2="14"></line></svg>',
  matrix: '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="6" y1="3" x2="6" y2="15"></line><circle cx="18" cy="6" r="3"></circle><circle cx="6" cy="18" r="3"></circle><path d="M18 9a9 9 0 0 1-9 9"></path></svg>',
  admin: '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>',
  profile: '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>',
  teams: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>',
  categories: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"></path><line x1="7" y1="7" x2="7.01" y2="7"></line></svg>',
  geo: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"></polygon><line x1="8" y1="2" x2="8" y2="18"></line><line x1="16" y1="6" x2="16" y2="22"></line></svg>',
  vehicles: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="1" y="3" width="15" height="13"></rect><polygon points="16 8 20 8 23 11 23 16 16 16 16 8"></polygon><circle cx="5.5" cy="18.5" r="2.5"></circle><circle cx="18.5" cy="18.5" r="2.5"></circle></svg>',
  reasons: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>',
  machines: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="16" height="16" rx="2" ry="2"></rect><rect x="9" y="9" width="6" height="6"></rect><line x1="9" y1="1" x2="9" y2="4"></line><line x1="15" y1="1" x2="15" y2="4"></line><line x1="9" y1="20" x2="9" y2="23"></line><line x1="15" y1="20" x2="15" y2="23"></line><line x1="20" y1="9" x2="23" y2="9"></line><line x1="20" y1="14" x2="23" y2="14"></line><line x1="1" y1="9" x2="4" y2="9"></line><line x1="1" y1="14" x2="4" y2="14"></line></svg>',
  sla: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>',
  users: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="8.5" cy="7" r="4"></circle><polyline points="17 11 19 13 23 9"></polyline></svg>',
  audit: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line></svg>'
};

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
      { label: 'All Tickets', dot: 'all', active: isStatus(''), onclick: "setQueueStatus('')" },
      { label: 'Open', dot: 'open', active: isStatus('open'), onclick: "setQueueStatus('open')" },
      { label: 'Closed', dot: 'closed', active: isStatus('CLOSED'), onclick: "setQueueStatus('CLOSED')" },
      { label: 'TAT Breached', dot: 'breached', active: isScope('breach'), onclick: "setQueueScope('breach')" },
      { label: 'At Risk', dot: 'risk', active: isScope('risk'), onclick: "setQueueScope('risk')" },
      { label: 'Critical', dot: 'critical', active: isScope('critical'), onclick: "setQueueScope('critical')" },
      { label: 'Escalated', dot: 'escalated', active: isScope('escalated'), onclick: "setQueueScope('escalated')" },
      { label: 'Unassigned', dot: 'unassigned', active: isScope('unassigned'), onclick: "setQueueScope('unassigned')" }
    ];

    html += '<div class="nav-group">' +
      '<div class="nav-parent ' + (NAV_EXPANDED.queue ? 'open ' : '') + (isQueue ? 'active-branch' : '') + '" onclick="toggleNavGroup(\'queue\')">' +
        '<div class="nav-parent-left"><span class="nav-parent-icon">' + NAV_ICONS.queue + '</span><span class="nav-parent-title">Ticket Queue</span></div>' +
        '<span class="nav-chevron">&#9654;</span>' +
      '</div>' +
      '<div class="nav-children' + (NAV_EXPANDED.queue ? '' : ' hide') + '">' +
        qSubFilters.map(function(item) {
          return '<div class="nav-subitem' + (item.active ? ' on' : '') + '" onclick="' + item.onclick + '">' +
            '<span class="nav-subitem-icon"><span class="nav-status-indicator nav-dot-' + item.dot + '"></span></span><span>' + esc(item.label) + '</span>' +
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
        '<div class="nav-parent-left"><span class="nav-parent-icon">' + NAV_ICONS.register + '</span><span class="nav-parent-title">Register Call</span></div>' +
      '</div>' +
    '</div>';
  }

  // 3. Lab Tech Options (if LT)
  if (ME.role === 'LT') {
    html += '<div class="nav-group">' +
      '<div class="nav-parent ' + (TAB === 'report' ? 'active-branch' : '') + '" onclick="go(\'report\')">' +
        '<div class="nav-parent-left"><span class="nav-parent-icon">' + NAV_ICONS.report + '</span><span class="nav-parent-title">Report an Issue</span></div>' +
      '</div>' +
    '</div>';
    html += '<div class="nav-group">' +
      '<div class="nav-parent ' + (TAB === 'mine' ? 'active-branch' : '') + '" onclick="go(\'mine\')">' +
        '<div class="nav-parent-left"><span class="nav-parent-icon">' + NAV_ICONS.tickets + '</span><span class="nav-parent-title">My Tickets</span></div>' +
      '</div>' +
    '</div>';
  }

  // 4. Daily Monitoring (Parent item)
  if (ME.role === 'CC_MANAGER' || ME.is_team_manager) {
    var isDash = (TAB === 'dash');
    html += '<div class="nav-group">' +
      '<div class="nav-parent ' + (isDash ? 'active-branch' : '') + '" onclick="go(\'dash\')">' +
        '<div class="nav-parent-left"><span class="nav-parent-icon">' + NAV_ICONS.monitor + '</span><span class="nav-parent-title">' + (ME.role === 'CC_MANAGER' ? 'Daily Monitoring' : 'Team Monitoring') + '</span></div>' +
      '</div>' +
    '</div>';
  }

  // 5. Routing Matrix (Parent item)
  if (ME.role !== 'LT') {
    var isMatrix = (TAB === 'matrix');
    html += '<div class="nav-group">' +
      '<div class="nav-parent ' + (isMatrix ? 'active-branch' : '') + '" onclick="go(\'matrix\')">' +
        '<div class="nav-parent-left"><span class="nav-parent-icon">' + NAV_ICONS.matrix + '</span><span class="nav-parent-title">Routing Matrix</span></div>' +
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
      { id: 'tickettypes', label: 'Ticket Types', icon: '🏗️' },
      { id: 'reasons', label: 'Sub-Categories', icon: '🗂️' },
      { id: 'priorities', label: 'Priorities & Matrix', icon: '🎯' },
      { id: 'slapolicies', label: 'SLA Policies', icon: '📐' },
      { id: 'calendars', label: 'Business Calendars', icon: '📅' },
      { id: 'routingrules', label: 'Routing Rules', icon: '🧭' },
      { id: 'hierarchysource', label: 'Hierarchy Source', icon: '🪜' },
      { id: 'assignmentexceptions', label: 'Assignment Exceptions', icon: '🚧' },
      { id: 'machines', label: 'Machines', icon: '🔬' },
      { id: 'sla', label: 'SLA & TAT', icon: '⏱️' },
      { id: 'users', label: 'Users', icon: '👥' },
      { id: 'audit', label: 'Audit Log', icon: '📜' }
    ];
    html += '<div class="nav-group">' +
      '<div class="nav-parent ' + (NAV_EXPANDED.admin ? 'open ' : '') + (isAdmin ? 'active-branch' : '') + '" onclick="toggleNavGroup(\'admin\')">' +
        '<div class="nav-parent-left"><span class="nav-parent-icon">' + NAV_ICONS.admin + '</span><span class="nav-parent-title">Admin Portal</span></div>' +
        '<span class="nav-chevron">&#9654;</span>' +
      '</div>' +
      '<div class="nav-children' + (NAV_EXPANDED.admin ? '' : ' hide') + '">' +
        aItems.map(function(item) {
          var on = (TAB === 'admin' && ADMIN_TAB === item.id) ? ' on' : '';
          return '<div class="nav-subitem' + on + '" onclick="goAdminItem(\'' + item.id + '\')">' +
            '<span class="nav-subitem-icon">' + (NAV_ICONS[item.id] || '') + '</span><span>' + esc(item.label) + '</span>' +
          '</div>';
        }).join('') +
      '</div>' +
    '</div>';
  }

  // 7. My Profile (all roles)
  html += '<div class="nav-group">' +
    '<div class="nav-parent" onclick="openProfile()">' +
      '<div class="nav-parent-left"><span class="nav-parent-icon">' + NAV_ICONS.profile + '</span><span class="nav-parent-title">My Profile</span></div>' +
    '</div>' +
  '</div>';

  el.innerHTML = html;
}

function goAdminItem(subTab) {
  closeSidebar();
  TAB = 'admin';
  ADMIN_TAB = subTab;
  NAV_EXPANDED.admin = true;
  saveState();
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
function go(t) {
  closeSidebar();
  TAB = t;
  if (t === 'dash') DASH = null;
  if (t === 'admin' && !ADMIN_TAB) ADMIN_TAB = 'teams';
  saveState();
  render();
  if (t === 'queue' || t === 'dash' || t === 'mine') load(true);
  if (t === 'admin') loadAdminSection(ADMIN_TAB);
}
function queueQS() {
  var params = [];
  var keys = ['status', 'scope', 'team', 'priority', 'category', 'mmu_vehicle', 'district', 'district_id', 'mandal_id', 'date_from', 'date_to', 'time_from', 'time_to', 'shift', 'page', 'page_size', 'sort_by', 'sort_desc'];
  keys.forEach(function (k) {
    var v = FILT[k];
    if (v !== undefined && v !== null && String(v).trim() !== '') {
      params.push(k + '=' + encodeURIComponent(v));
    }
  });
  if (FILT.q) params.push('q_=' + encodeURIComponent(FILT.q));
  return params.join('&');
}

function dashQS() {
  var p = [];
  if (DASH_FILT.district) p.push('district=' + encodeURIComponent(DASH_FILT.district));
  if (DASH_FILT.team) p.push('team=' + encodeURIComponent(DASH_FILT.team));
  if (DASH_FILT.mmu_vehicle) p.push('mmu_vehicle=' + encodeURIComponent(DASH_FILT.mmu_vehicle.trim()));
  if (DASH_FILT.date_from) p.push('date_from=' + encodeURIComponent(DASH_FILT.date_from));
  if (DASH_FILT.date_to) p.push('date_to=' + encodeURIComponent(DASH_FILT.date_to));
  return p.length ? ('?' + p.join('&')) : '';
}

function load(forced) {
  if (ME.role === 'LT') { if (TAB === 'mine') loadLTMine(); return; }
  if (TAB === 'queue') {
    api('GET', '/tickets?' + queueQS()).then(function (d) {
      ROWS = d.rows || []; ROWTOTAL = d.total || 0;

      // Sound alert and new ticket detection
      if (ROWS.length > 0) {
        var maxId = 0;
        var incomingP1 = false;
        var incomingNew = 0;

        ROWS.forEach(function (t) {
          if (t.id > maxId) maxId = t.id;
          if (LAST_MAX_TICKET_ID > 0 && t.id > LAST_MAX_TICKET_ID) {
            incomingNew++;
          }
        });

        if (incomingNew > 0) {
          playAlertSound('p1');
          var topT = ROWS[0] || {};
          var msg = incomingNew === 1 ?
            ('New Breakdown Alert: Ticket ' + esc(topT.ticket_no) + (topT.mmu_vehicle ? (' · MMU ' + esc(topT.mmu_vehicle)) : '')) :
            (incomingNew + ' new breakdown tickets received!');
          toast(msg);
        }

        if (maxId > LAST_MAX_TICKET_ID) {
          LAST_MAX_TICKET_ID = maxId;
        }
      }

      if (forced) {
        render();
      } else {
        updateQueueTableOnly();
      }
    });
  }
  if (TAB === 'dash') {
    api('GET', '/dashboard' + dashQS()).then(function (d) {
      var dStr = JSON.stringify(d);
      if (forced || dStr !== LAST_DASH_STR) {
        LAST_DASH_STR = dStr;
        DASH = d;
        render();
      }
    });
  }
}
function setFilt(k, v) {
  TAB = 'queue';
  FILT[k] = v;
  FILT.page = 1;
  saveState();
  render();
  load(true);
}
function viewVehicleTickets(veh) {
  TAB = 'queue';
  FILT.status = '';
  FILT.scope = '';
  FILT.mmu_vehicle = veh;
  FILT.district = '';
  FILT.q = '';
  FILT.priority = '';
  FILT.category = '';
  FILT.date_from = '';
  FILT.date_to = '';
  FILT.page_size = 100;
  FILT.page = 1;
  saveState();
  render();
  load(true);
}
function gotoPage(p) { if (p < 1) return; FILT.page = p; saveState(); load(true); }

function parseDT(s) { if (!s) return null; var p = s.split(/[- :]/); return new Date(+p[0], +p[1] - 1, +p[2], +p[3] || 0, +p[4] || 0, 0); }
function formatDT(s) {
  if (!s) return '—';
  var str = String(s).trim().replace('T', ' ');
  if (str.indexOf('AM') !== -1 || str.indexOf('PM') !== -1) return esc(str);
  var p = str.split(/[- :]/);
  if (p.length < 5) return esc(str.slice(0, 16));
  var y = p[0], m = p[1], d = p[2], hh = parseInt(p[3], 10), mm = p[4];
  if (isNaN(hh)) return esc(str.slice(0, 16));
  var ampm = hh >= 12 ? 'PM' : 'AM';
  var h12 = hh % 12;
  if (h12 === 0) h12 = 12;
  var hStr = (h12 < 10 ? '0' : '') + h12;
  return esc(y + '-' + m + '-' + d + ' ' + hStr + ':' + mm + ' ' + ampm);
}
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
  updateQueueTableOnly();
}
function tatPill(t) {
  var s = t.tat_state; var k = s === 'BREACHED' ? 'p-crit' : (s === 'CRITICAL' ? 'p-critical' : (s === 'AT RISK' ? 'p-warn' : (s === 'MET' || s === 'ON TRACK' ? 'p-ok' : 'p-mut')));
  var extra = (t.mins_left != null && t.status !== 'CLOSED') ? (' · ' + (t.mins_left < 0 ? ('+' + Math.abs(t.mins_left)) : t.mins_left) + 'm') : '';
  return '<span class="pill ' + k + '">' + esc(s) + extra + '</span>';
}
function priorityPill(code) {
  if (!code) return '';
  var label = (META.priorities && META.priorities[code] && META.priorities[code].label) || code;
  return '<span class="pill p-' + esc(code) + '" title="' + esc(code) + '">' + esc(label) + '</span>';
}
function statusPill(status) {
  var s = (status || '').toUpperCase();
  var label = esc(s.replace(/_/g, ' '));
  var cls = 'p-mut';
  if (s === 'NEW') cls = 'p-info';
  else if (s === 'ASSIGNED') cls = 'p-assigned';
  else if (s === 'IN_PROGRESS' || s === 'ACKNOWLEDGED') cls = 'p-warn';
  else if (s === 'PENDING') cls = 'p-pending';
  else if (s === 'RESOLVED') cls = 'p-ok';
  else if (s === 'CLOSURE_CONFIRMATION') cls = 'p-closure';
  else if (s === 'CLOSED') cls = 'p-mut';
  return '<span class="pill ' + cls + '">' + label + '</span>';
}
function gv(i) { var e = document.getElementById(i); return e ? e.value.trim() : ''; }

function onTimePresetChange(preset) {
  var customWrap = document.getElementById('qf_custom_dates');
  if (preset === 'custom') {
    FILT.date_preset = 'custom';
    if (customWrap) customWrap.style.display = 'flex';
    return;
  }
  if (customWrap) customWrap.style.display = 'none';
  applyFilters();
}

function setDatePreset(preset) {
  FILT.date_preset = preset;
  applyFilters();
}

function applyFilters() {
  FILT.q = gv('qf_q');

  var stEl = document.getElementById('qf_status');
  if (stEl) FILT.status = stEl.value;

  var priEl = document.getElementById('qf_priority');
  if (priEl) FILT.priority = priEl.value;

  var deptEl = document.getElementById('qf_dept');
  FILT.team = deptEl ? deptEl.value : '';

  var distEl = document.getElementById('qf_dist');
  FILT.district_id = distEl ? distEl.value : '';
  FILT.district = '';
  if (FILT.district_id && META && META.districts) {
    var dObj = META.districts.find(function (d) { return String(d.id) === String(FILT.district_id); });
    if (dObj) FILT.district = dObj.name;
  }

  // Clear obsolete filters to prevent ghost filtering
  FILT.category = '';
  FILT.mmu_vehicle = '';
  FILT.mandal_id = '';
  FILT.time_from = '';
  FILT.time_to = '';
  FILT.shift = '';

  var timeSel = gv('qf_time');
  FILT.date_preset = timeSel;
  var now = new Date();
  var pad = function (n) { return (n < 10 ? '0' : '') + n; };
  var fmtDate = function (d) { return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()); };

  if (timeSel === 'today') {
    var today = fmtDate(now);
    FILT.date_from = today;
    FILT.date_to = today;
  } else if (timeSel === 'yesterday') {
    var y = new Date();
    y.setDate(y.getDate() - 1);
    var yDate = fmtDate(y);
    FILT.date_from = yDate;
    FILT.date_to = yDate;
  } else if (timeSel === '24h') {
    var yesterday = new Date(now.getTime() - 24 * 3600 * 1000);
    FILT.date_from = fmtDate(yesterday);
    FILT.date_to = fmtDate(now);
  } else if (timeSel === '7d') {
    var last7 = new Date(now.getTime() - 7 * 24 * 3600 * 1000);
    FILT.date_from = fmtDate(last7);
    FILT.date_to = fmtDate(now);
  } else if (timeSel === '30d') {
    var last30 = new Date(now.getTime() - 30 * 24 * 3600 * 1000);
    FILT.date_from = fmtDate(last30);
    FILT.date_to = fmtDate(now);
  } else if (timeSel === 'custom') {
    FILT.date_from = gv('qf_from');
    FILT.date_to = gv('qf_to');
  } else {
    FILT.date_from = '';
    FILT.date_to = '';
  }

  var sortVal = gv('qf_sort');
  if (sortVal) {
    var parts = sortVal.split('_');
    FILT.sort_desc = parts.pop() === 'desc';
    FILT.sort_by = parts.join('_');
  }
  FILT.page = 1;
  saveState();
  load(true);
}

function clearFilters() {
  FILT.status = '';
  FILT.scope = '';
  FILT.team = '';
  FILT.priority = '';
  FILT.category = '';
  FILT.district = '';
  FILT.district_id = '';
  FILT.mandal_id = '';
  FILT.mmu_vehicle = '';
  FILT.q = '';
  FILT.date_preset = '';
  FILT.date_from = '';
  FILT.date_to = '';
  FILT.time_from = '';
  FILT.time_to = '';
  FILT.shift = '';
  FILT.sort_by = 'created_at';
  FILT.sort_desc = true;
  FILT.page = 1;
  try {
    sessionStorage.removeItem('ccc_filt');
    localStorage.removeItem('ccc_filt');
  } catch (e) {}
  saveState();
  render();
  load(true);
}

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
function renderQueueRow(t) {
  var raisedTime = formatDT(t.created_at);
  var dueTime = formatDT(t.due_at);
  var chronicBadge = t.is_chronic_fault ?
    (' <span class="pill-chronic" title="' + t.chronic_breakdown_count + ' breakdowns in 30 days">' + t.chronic_breakdown_count + 'x in 30d</span>') : '';
  var vipBadge = t.vip ? ' <span class="pill p-crit" style="font-size:10px;padding:1px 6px">VIP</span>' : '';
  var escBadge = t.escalated ? ' <span class="pill p-crit" style="font-size:10px;padding:2px 6px;margin-left:4px">ESC</span>' : '';

  return '<tr class="row" onclick="openT(' + t.id + ')">' +
    '<td style="white-space:nowrap">' +
      '<div style="font-weight:700;font-size:13px;color:var(--ink);display:flex;align-items:center;gap:6px;flex-wrap:wrap">' +
        '<span>' + esc(t.ticket_no) + '</span>' + priorityPill(t.priority) + vipBadge +
      '</div>' +
      '<div class="muted" style="font-size:11.5px;margin-top:2px">' + esc(t.source) + '</div>' +
    '</td>' +
    '<td>' +
      '<div style="font-weight:600;font-size:13px;color:var(--ink);display:flex;align-items:center;gap:6px;flex-wrap:wrap">' +
        '<span>' + esc(t.mmu_vehicle || '—') + '</span>' + chronicBadge +
      '</div>' +
      '<div class="muted" style="font-size:11.5px;margin-top:2px">' + esc(t.district || '') + (t.mandal ? (' · ' + esc(t.mandal)) : '') + '</div>' +
    '</td>' +
    '<td>' +
      '<div style="font-size:13px;font-weight:600;color:var(--ink)">' + esc(t.category_label || '') + '</div>' +
    '</td>' +
    '<td>' +
      '<div style="font-size:13px;font-weight:500;color:var(--ink2)">' + esc(t.team_label || '') + '</div>' +
    '</td>' +
    '<td style="white-space:nowrap">' +
      statusPill(t.status) + escBadge +
    '</td>' +
    '<td style="white-space:nowrap">' +
      '<div style="font-weight:600;font-size:12.5px;color:var(--ink);letter-spacing:-0.01em">' + raisedTime + '</div>' +
      '<div class="muted" style="font-size:11px;margin-top:2px;display:flex;align-items:center;gap:4px">' +
        '<span style="display:inline-block;width:5px;height:5px;border-radius:50%;background:#94a3b8"></span>' +
        '<span>Raised</span>' +
      '</div>' +
    '</td>' +
    '<td style="white-space:nowrap">' +
      '<div>' + tatPill(t) + '</div>' +
      '<div class="muted" style="font-size:11px;margin-top:3px">' +
        '<span style="opacity:0.75;font-weight:500">Due:</span> ' + dueTime +
      '</div>' +
    '</td>' +
    '<td style="max-width:320px">' +
      '<div style="font-size:13px;color:var(--ink);line-height:1.45;word-break:break-word">' +
        esc((t.problem || '').slice(0, 110)) + ((t.problem || '').length > 110 ? '…' : '') +
      '</div>' +
    '</td>' +
  '</tr>';
}

function updateQueueTableOnly() {
  var tb = document.querySelector('#queue_table_wrap tbody');
  if (!tb) {
    if (TAB === 'queue') render();
    return;
  }
  var newHTML = '';
  if (!ROWS.length) {
    var hasActiveFilters = FILT.q || FILT.team || FILT.district_id || FILT.date_from || FILT.date_to || FILT.date_preset;
    var emptyMsg = hasActiveFilters ?
      '<div style="padding:36px 20px;text-align:center">' +
        '<div style="display:flex;justify-content:center;margin-bottom:8px"><svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg></div>' +
        '<div style="font-size:15px;font-weight:700;color:var(--ink);margin-bottom:4px">No tickets found matching the selected filters</div>' +
        '<div style="font-size:13px;color:var(--ink2);margin-bottom:14px">Try selecting "All Time" or resetting filters to view all active tickets.</div>' +
        '<button class="btn sm" onclick="clearFilters()" style="padding:6px 18px">Clear All Filters</button>' +
      '</div>' :
      '<div class="empty" style="padding:30px">No tickets currently in this view.</div>';
    newHTML = '<tr><td colspan="8">' + emptyMsg + '</td></tr>';
  } else {
    newHTML = ROWS.map(renderQueueRow).join('');
  }
  if (tb.innerHTML !== newHTML) {
    tb.innerHTML = newHTML;
  }
  var qb = document.getElementById('queue_total_badge');
  if (qb) qb.textContent = ROWTOTAL + ' ticket' + (ROWTOTAL === 1 ? '' : 's');
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
  var filterTitle = 'All Tickets · Time & Ticket # Basis';
  if (FILT.mmu_vehicle) filterTitle = 'Breakdown Records · MMU ' + FILT.mmu_vehicle;
  else if (FILT.scope === 'breach') filterTitle = 'TAT Breached Tickets';
  else if (FILT.scope === 'risk') filterTitle = 'At Risk Tickets';
  else if (FILT.scope === 'critical') filterTitle = 'Critical Priority Tickets';
  else if (FILT.scope === 'escalated') filterTitle = 'Escalated Tickets';
  else if (FILT.scope === 'unassigned') filterTitle = 'Unassigned Tickets';
  else if (FILT.status === 'open') filterTitle = 'Open Tickets';
  else if (FILT.status === 'CLOSED') filterTitle = 'Closed Tickets';

  var vehicleNotice = '';
  if (FILT.mmu_vehicle) {
    vehicleNotice = '<div style="background:#FAF5FF;border:1px solid #D8B4FE;border-radius:8px;padding:8px 14px;margin-bottom:12px;display:flex;align-items:center;justify-content:space-between;font-size:13px">' +
      '<span>Filtered by MMU Vehicle: <b>' + esc(FILT.mmu_vehicle) + '</b></span>' +
      '<button class="btn sm o" onclick="FILT.mmu_vehicle=\'\';saveState();load(true);render();">Clear Filter</button>' +
    '</div>';
  }

  var isCCManagerOrAdmin = ME && (ME.role === 'CC_MANAGER' || ME.role === 'ADMIN' || ME.role === 'CALL_TAKER');

  var statusSelectHtml = [
    { id: '', label: 'All Statuses' },
    { id: 'open', label: 'Open / Active' },
    { id: 'CLOSED', label: 'Closed' }
  ].map(function (s) {
    return '<option value="' + s.id + '"' + ((FILT.status || '') === s.id ? ' selected' : '') + '>' + esc(s.label) + '</option>';
  }).join('');

  var prioritySelectHtml = '<option value="">All Priorities</option>' +
    Object.keys(META.priorities || {}).sort(function (a, b) {
      return (META.priorities[a].display_order || 0) - (META.priorities[b].display_order || 0);
    }).map(function (code) {
      return '<option value="' + code + '"' + ((FILT.priority || '') === code ? ' selected' : '') + '>' + esc(META.priorities[code].label) + ' (' + code + ')</option>';
    }).join('');

  var distOptions = '<option value="">All Locations (Statewide)</option>';
  if (META && META.districts) {
    distOptions += META.districts.map(function (d) {
      return '<option value="' + d.id + '"' + (String(FILT.district_id) === String(d.id) ? ' selected' : '') + '>' + esc(d.name) + '</option>';
    }).join('');
  }

  var deptOptions = '<option value="">All Departments</option>' +
    [
      { id: 'SERVICE', label: 'Service Team (Machines)' },
      { id: 'CDA', label: 'CDA Specialists (Diagnostics)' },
      { id: 'FLEET', label: 'Fleet Operations (MMU Vehicles)' },
      { id: 'APPLICATION', label: 'Application Support (Software)' },
      { id: 'NETWORK', label: 'Network & LIS (Connectivity)' },
      { id: 'QUALITY', label: 'Quality Team (Lab QC)' },
      { id: 'TECHNICAL', label: 'Technical Team (Hardware)' }
    ].map(function (d) {
      return '<option value="' + d.id + '"' + (FILT.team === d.id ? ' selected' : '') + '>' + esc(d.label) + '</option>';
    }).join('');

  var timePresets = [
    { id: '', label: 'All Time' },
    { id: 'today', label: 'Today' },
    { id: 'yesterday', label: 'Yesterday' },
    { id: '24h', label: 'Last 24 Hours' },
    { id: '7d', label: 'Last 7 Days' },
    { id: '30d', label: 'This Month' },
    { id: 'custom', label: 'Custom Date Range...' }
  ];
  var timeSelectHtml = timePresets.map(function (p) {
    return '<option value="' + p.id + '"' + (FILT.date_preset === p.id ? ' selected' : '') + '>' + esc(p.label) + '</option>';
  }).join('');

  var curSortKey = (FILT.sort_by || 'created_at') + '_' + (FILT.sort_desc ? 'desc' : 'asc');
  var sortSelectHtml = [
    { id: 'created_at_desc', label: 'Time Basis (Newest First)' },
    { id: 'created_at_asc', label: 'Time Basis (Oldest First)' },
    { id: 'ticket_no_desc', label: 'Ticket # (High to Low)' },
    { id: 'ticket_no_asc', label: 'Ticket # (Low to High)' },
    { id: 'due_at_asc', label: 'SLA Urgent First' },
    { id: 'due_at_desc', label: 'SLA Least Urgent' }
  ].map(function (s) {
    return '<option value="' + s.id + '"' + (curSortKey === s.id ? ' selected' : '') + '>' + esc(s.label) + '</option>';
  }).join('');

  var bar = vehicleNotice + '<div class="card" style="margin-bottom:14px;padding:16px 20px;border-radius:12px;background:#fff;border:1px solid #E5E7EB;box-shadow:0 1px 3px rgba(0,0,0,0.04)">' +
    '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;padding-bottom:10px;border-bottom:1px solid #F3F4F6">' +
      '<div style="font-size:15px;font-weight:700;color:var(--ink);display:flex;align-items:center;gap:6px">' + esc(filterTitle) + '</div>' +
      '<div id="queue_total_badge" style="font-size:12px;font-weight:700;background:#EDE9FE;color:#6D28D9;padding:4px 12px;border-radius:20px">' +
        ROWTOTAL + ' ticket' + (ROWTOTAL === 1 ? '' : 's') +
      '</div>' +
    '</div>' +
    '<div class="qf-grid">' +
      '<div class="qf-fld" style="flex:1.2;min-width:170px"><label class="qf-label">Search</label><input id="qf_q" class="qf-input" value="' + esc(FILT.q) + '" placeholder="Ticket #, vehicle, problem..." onkeydown="if(event.key===\'Enter\')applyFilters()"></div>' +
      '<div class="qf-fld" style="flex:0.9;min-width:130px"><label class="qf-label">Status</label><select id="qf_status" class="qf-select" onchange="applyFilters()">' + statusSelectHtml + '</select></div>' +
      '<div class="qf-fld" style="flex:0.9;min-width:150px"><label class="qf-label">Priority</label><select id="qf_priority" class="qf-select" onchange="applyFilters()">' + prioritySelectHtml + '</select></div>' +
      (isCCManagerOrAdmin ? ('<div class="qf-fld" style="flex:1.1;min-width:150px"><label class="qf-label">Location</label><select id="qf_dist" class="qf-select" onchange="applyFilters()">' + distOptions + '</select></div>') : '') +
      (isCCManagerOrAdmin ? ('<div class="qf-fld" style="flex:1.1;min-width:150px"><label class="qf-label">Department</label><select id="qf_dept" class="qf-select" onchange="applyFilters()">' + deptOptions + '</select></div>') : '') +
      '<div class="qf-fld" style="flex:1;min-width:130px"><label class="qf-label">Date Filter</label><select id="qf_time" class="qf-select" onchange="onTimePresetChange(this.value)">' + timeSelectHtml + '</select></div>' +
      '<div class="qf-fld" style="flex:1.1;min-width:150px"><label class="qf-label">Sort Order</label><select id="qf_sort" class="qf-select" onchange="applyFilters()">' + sortSelectHtml + '</select></div>' +
      '<div class="qf-fld" style="flex:0 0 auto"><label class="qf-label" style="visibility:hidden">Actions</label>' +
        '<div style="display:flex;gap:8px;align-items:center">' +
          '<button class="qf-btn qf-btn-primary" onclick="applyFilters()">Filter</button>' +
          '<button class="qf-btn qf-btn-outline" onclick="clearFilters()" title="Reset All Filters">Reset</button>' +
          '<button class="qf-btn qf-btn-export" onclick="exportQueue()" title="Export Tickets to Excel">Export</button>' +
        '</div>' +
      '</div>' +
    '</div>' +
    '<div id="qf_custom_dates" style="display:' + (FILT.date_preset === 'custom' || (FILT.date_from && !FILT.date_preset) ? 'flex' : 'none') + ';gap:12px;margin-top:12px;align-items:flex-end;flex-wrap:wrap;padding-top:12px;border-top:1px dashed #E5E7EB">' +
      '<div class="qf-fld" style="flex:1;min-width:150px"><label class="qf-label">Date From</label><input id="qf_from" class="qf-input" type="date" value="' + esc(FILT.date_from) + '"></div>' +
      '<div class="qf-fld" style="flex:1;min-width:150px"><label class="qf-label">Date To</label><input id="qf_to" class="qf-input" type="date" value="' + esc(FILT.date_to) + '"></div>' +
      '<button class="qf-btn qf-btn-primary" onclick="applyFilters()" style="height:38px">Apply Range</button>' +
    '</div>' +
  '</div>';

  var rows = '';
  if (!ROWS.length) {
    var hasActiveFilters = FILT.q || FILT.team || FILT.district_id || FILT.date_from || FILT.date_to || FILT.date_preset;
    var emptyMsg = hasActiveFilters ?
      '<div style="padding:40px 20px;text-align:center">' +
        '<div style="display:flex;justify-content:center;margin-bottom:8px"><svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg></div>' +
        '<div style="font-size:15px;font-weight:700;color:var(--ink);margin-bottom:4px">No tickets found matching the selected filters</div>' +
        '<div style="font-size:13px;color:var(--ink2);margin-bottom:14px">Try selecting "All Time" or resetting filters to view all active tickets.</div>' +
        '<button class="btn sm" onclick="clearFilters()" style="padding:6px 18px">Clear All Filters</button>' +
      '</div>' :
      '<div class="empty" style="padding:30px">No tickets currently in this view.</div>';
    rows = '<tr><td colspan="8">' + emptyMsg + '</td></tr>';
  } else {
    rows = ROWS.map(renderQueueRow).join('');
  }
  var pages = Math.max(1, Math.ceil(ROWTOTAL / FILT.page_size));
  var pager = '<div class="pager"><span>' + ROWTOTAL + ' ticket' + (ROWTOTAL === 1 ? '' : 's') + ' &middot; page ' + FILT.page + ' of ' + pages + '</span>' +
    '<button class="btn o sm" ' + (FILT.page <= 1 ? 'disabled' : '') + ' onclick="gotoPage(' + (FILT.page - 1) + ')">&larr; Prev</button>' +
    '<button class="btn o sm" ' + (FILT.page >= pages ? 'disabled' : '') + ' onclick="gotoPage(' + (FILT.page + 1) + ')">Next &rarr;</button></div>';

  function thSort(col, label, widthStyle) {
    var active = FILT.sort_by === col;
    var icon = active ? (FILT.sort_desc ? '&#8595;' : '&#8593;') : '&#8597;';
    var activeClass = active ? ' th-sorted' : '';
    return '<th class="th-sort' + activeClass + '" onclick="sortQueue(\'' + col + '\')"' + (widthStyle ? (' style="' + widthStyle + '"') : '') + '>' +
      '<div style="display:flex;align-items:center;justify-content:space-between;gap:6px">' +
      '<span>' + label + '</span>' +
      '<span class="sort-ico' + (active ? ' active' : '') + '">' + icon + '</span>' +
      '</div></th>';
  }

  var th_t = thSort('ticket_no', 'Ticket', 'width:145px;min-width:140px');
  var th_loc = thSort('district', 'MMU / Location', 'min-width:160px');
  var th_cat = '<th style="min-width:150px">Category</th>';
  var th_team = '<th style="min-width:150px">Team</th>';
  var th_s = thSort('status', 'Status', 'width:130px;min-width:125px');
  var th_c = thSort('created_at', 'Raised At', 'width:165px;min-width:160px');
  var th_d = thSort('due_at', 'TAT Due (SLA)', 'width:180px;min-width:175px');
  var th_prob = '<th style="min-width:240px">Problem Statement</th>';

  return bar + '<div class="card" id="queue_table_wrap"><div style="overflow-x:auto"><table class="queue-table"><thead><tr>' + th_t + th_loc + th_cat + th_team + th_s + th_c + th_d + th_prob + '</tr></thead><tbody>' + rows + '</tbody></table></div></div>' + pager;
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
        '<div class="form-accordion-title"><span class="form-accordion-num">4</span><span>Problem Statement &amp; SLA Routing</span><span class="form-accordion-summary">— Emergency Category &amp; Routing</span></div>' +
        '<span class="form-accordion-chevron">&#9654;</span>' +
      '</div>' +
      '<div class="form-accordion-body' + (FORM_ACCORDION_OPEN.issue ? '' : ' hide') + '">' +
        '<div class="fld"><label>Nature of the problem *</label><textarea id="f_prob" rows="3" placeholder="What exactly is happening?"></textarea></div>' +
        '<div class="grid2">' +
        '<div class="fld"><label>Issue category *</label><select id="f_cat" onchange="previewRoute()">' + cats + '</select></div>' +
        '<div class="fld"><label>Ticket Type</label><select id="f_tt">' + Object.keys(META.ticket_types || {}).map(function (k) { return '<option value="' + k + '">' + esc(META.ticket_types[k].label) + '</option>'; }).join('') + '</select></div>' +
        '</div>' +
        '<div class="fld"><label>Sub-Category (optional)</label><select id="f_subcat"><option value="">— None —</option></select></div>' +
        '<div class="grid3">' +
        '<div class="fld"><label>Impact (optional)</label><select id="f_impact" onchange="updatePrioritySuggestion()"><option value="">— Not specified —</option>' + (META.impact_levels || []).map(function (lvl) { return '<option value="' + lvl + '">' + esc(lvl) + '</option>'; }).join('') + '</select></div>' +
        '<div class="fld"><label>Urgency (optional)</label><select id="f_urgency" onchange="updatePrioritySuggestion()"><option value="">— Not specified —</option>' + (META.urgency_levels || []).map(function (lvl) { return '<option value="' + lvl + '">' + esc(lvl) + '</option>'; }).join('') + '</select></div>' +
        '<div class="fld"><label>Priority *</label><select id="f_pri">' + Object.keys(META.priorities || {}).sort(function (a, b) { return (META.priorities[a].display_order || 0) - (META.priorities[b].display_order || 0); }).map(function (code) { return '<option value="' + code + '"' + (code === 'P2' ? ' selected' : '') + '>' + esc(META.priorities[code].label) + ' (' + code + ')</option>'; }).join('') + '</select></div>' +
        '</div>' +
        '<div class="muted" id="f_pri_suggestion" style="margin-top:-6px;margin-bottom:10px"></div>' +
        '<div class="route" id="rpre" style="margin-top:10px"></div>' +
        '<div class="fld" style="margin-top:14px"><label style="display:flex;justify-content:space-between;align-items:center"><span>Attach Images / Evidence (optional)</span><span class="muted" style="font-size:12px;font-weight:normal">Multiple files supported (images, PDFs)</span></label>' +
        '<input type="file" id="f_photos" accept="image/*,.pdf,.doc,.docx" multiple onchange="previewNewTicketPhotos()" style="width:100%"><div id="f_photos_prev" class="photo-gallery"></div></div>' +
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
  updateSubcategoryOptions();
}
function updatePrioritySuggestion() {
  var box = document.getElementById('f_pri_suggestion');
  if (!box) return;
  var impact = document.getElementById('f_impact').value, urgency = document.getElementById('f_urgency').value;
  if (!impact || !urgency) { box.innerHTML = ''; return; }
  var suggested = (META.priority_matrix && META.priority_matrix[impact] || {})[urgency];
  if (!suggested) { box.innerHTML = ''; return; }
  var label = (META.priorities && META.priorities[suggested] && META.priorities[suggested].label) || suggested;
  box.innerHTML = 'Suggested priority: <b>' + esc(label) + ' (' + esc(suggested) + ')</b> — you can still change Priority above.';
  var priSel = document.getElementById('f_pri');
  if (priSel) priSel.value = suggested;
}
function updateSubcategoryOptions() {
  var sel = document.getElementById('f_subcat');
  if (!sel) return;
  var cat = document.getElementById('f_cat').value;
  var subs = Object.keys(META.subcategories || {}).filter(function (code) { return META.subcategories[code].category_code === cat; });
  sel.innerHTML = '<option value="">— None —</option>' + subs.map(function (code) {
    return '<option value="' + code + '">' + esc(META.subcategories[code].label) + '</option>';
  }).join('');
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
window._NEW_TICKET_FILES = [];

function previewNewTicketPhotos() {
  var inp = document.getElementById('f_photos');
  if (!inp || !inp.files) return;
  Array.from(inp.files).forEach(function (f) {
    if (!window._NEW_TICKET_FILES.some(function (x) { return x.name === f.name && x.size === f.size; })) {
      window._NEW_TICKET_FILES.push(f);
    }
  });
  renderNewTicketPhotosPreview();
  inp.value = '';
}

function removeNewTicketPhoto(idx) {
  window._NEW_TICKET_FILES.splice(idx, 1);
  renderNewTicketPhotosPreview();
}

function renderNewTicketPhotosPreview() {
  var prev = document.getElementById('f_photos_prev');
  if (!prev) return;
  if (!window._NEW_TICKET_FILES.length) {
    prev.innerHTML = '';
    return;
  }
  prev.innerHTML = window._NEW_TICKET_FILES.map(function (f, idx) {
    var isImg = f.type.indexOf('image') === 0;
    var iconOrImg = isImg ?
      ('<img src="' + URL.createObjectURL(f) + '" alt="Preview">') :
      ('<div style="width:98px;height:98px;display:flex;align-items:center;justify-content:center;background:#f3f4f6;border-radius:8px"><svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#6b7280" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg></div>');
    return '<div class="photo-thumb-card">' +
      iconOrImg +
      '<span class="photo-size" title="' + esc(f.name) + '">' + esc(f.name) + ' (' + Math.round(f.size / 1024) + ' KB)</span>' +
      '<button type="button" class="photo-remove-btn" onclick="removeNewTicketPhoto(' + idx + ')" title="Remove">&times;</button>' +
    '</div>';
  }).join('');
}

function createT() {
  var g = function (i) { var e = document.getElementById(i); return e ? e.value.trim() : ''; };
  if (!g('f_prob')) return toast('Nature of the problem is required');
  var districtId = g('f_district_id'), mandalId = g('f_mandal_id'), vehicleId = g('f_vehicle_id'), machineId = g('f_machine_id');
  var districtName = districtId ? ((NEW_DISTRICTS.find(function (d) { return String(d.id) === districtId; }) || {}).name || '') : '';
  var filesToUpload = (window._NEW_TICKET_FILES || []).slice();

  api('POST', '/ticket', {
    mmu_vehicle: g('f_veh'), vehicle_id: vehicleId ? +vehicleId : null, district: districtName,
    district_id: districtId ? +districtId : null, mandal_id: mandalId ? +mandalId : null, machine_id: machineId ? +machineId : null,
    location: g('f_loc'), caller_name: g('f_cname'),
    caller_phone: g('f_cph'), equipment: g('f_eq'), problem: g('f_prob'), error_code: g('f_err'), impact: g('f_imp'),
    category: g('f_cat'), priority: g('f_pri'), impact_code: g('f_impact') || undefined, urgency_code: g('f_urgency') || undefined,
    ticket_type: g('f_tt') || undefined, subcategory_code: g('f_subcat') || undefined
  })
    .then(function (d) {
      window._NEW_TICKET_FILES = [];
      if (filesToUpload.length > 0) {
        toast('Ticket ' + d.ticket_no + ' created! Uploading ' + filesToUpload.length + ' image(s)…');
        var uploads = filesToUpload.map(function (file) {
          var fd = new FormData();
          fd.append('file', file);
          fd.append('note', 'Initial ticket creation image');
          return apiForm('/tickets/' + d.id + '/attachments', fd);
        });
        Promise.all(uploads).then(function () {
          toast('Ticket ' + d.ticket_no + ' created with ' + filesToUpload.length + ' attachment(s)');
          TAB = 'queue'; render(); load(true);
        }).catch(function () {
          toast('Ticket created, but some attachments could not be uploaded');
          TAB = 'queue'; render(); load(true);
        });
      } else {
        toast('Ticket ' + d.ticket_no + ' created → ' + d.team + (d.vip ? ' (VIP Dispatch)' : ''));
        TAB = 'queue'; render(); load();
      }
    })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}

/* ---------- ticket detail ---------- */
var MODAL_TICK = null;
function markTicketNotifsRead(ticketId) {
  if (!ticketId || !NOTIFS || !NOTIFS.length) return;
  var unread = NOTIFS.filter(function (n) { return n.ticket_id === ticketId && !n.read_at; });
  if (unread.length > 0) {
    unread.forEach(function (n) {
      n.read_at = 'now';
      api('POST', '/notifications/' + n.id + '/read', {}).catch(function () {});
    });
    renderBell();
    if (NOTIF_OPEN) renderNotifPanel();
  }
}
function openT(id) {
  CURRENT_MODAL_TICKET_ID = id;
  saveState();
  markTicketNotifsRead(id);
  api('GET', '/ticket/' + id).then(function (d) {
    renderT(d.ticket, d.events);
    loadAttachments(id);
    loadAssignments(id, d.ticket.current_level);
  });
}
function closeT() {
  CURRENT_MODAL_TICKET_ID = null;
  saveState();
  document.getElementById('modal').innerHTML = '';
  if (MODAL_TICK) { clearInterval(MODAL_TICK); MODAL_TICK = null; }
}
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
    if (t.status === 'RESOLVED') {
      A.push('<button class="btn g" onclick="act(' + t.id + ',\'confirm\')">Confirm with MMU</button>');
      A.push('<button class="btn r" onclick="act(' + t.id + ',\'not_resolved\')">Not resolved — return to team</button>');
    }
    if (t.status === 'CLOSURE_CONFIRMATION') A.push('<button class="btn" onclick="act(' + t.id + ',\'close\')">Close ticket</button>');
    if (t.status !== 'CLOSED' && ME.role !== 'CC_MANAGER') A.push('<button class="btn r" onclick="act(' + t.id + ',\'escalate\')">Escalate to Global Team Executive</button>');
  }
  if ((ME.role === 'CC_MANAGER' || ME.role === 'CALL_TAKER') && t.status === 'CLOSED') {
    var closedDt = parseDT(t.closed_at), windowH = (META.sla && META.sla.reopen_window_hours) || 24;
    var withinWindow = closedDt ? ((Date.now() - closedDt.getTime()) / 3600000 <= windowH) : true;
    if (withinWindow) A.push('<button class="btn o" onclick="reopenT(' + t.id + ')">Reopen</button>');
    else A.push('<span class="muted">Reopen window (' + windowH + 'h) has passed - register a new ticket</span>');
  }
  var reroute = (ME.role === 'CC_MANAGER' || ME.role === 'CALL_TAKER') ?
    ('<div class="fld" style="margin-top:12px"><label>Re-route to team</label><select id="a_team">' +
      Object.keys(META.teams).map(function (k) { return '<option value="' + k + '"' + (k === t.team ? ' selected' : '') + '>' + esc(META.teams[k]) + '</option>'; }).join('') +
      '</select><button class="btn o sm" style="margin-top:7px" onclick="act(' + t.id + ',\'reassign\')">Apply re-route</button></div>') : '';
  var canAssign = (ME.role === 'CC_MANAGER' || (ME.role === t.team && ME.is_team_manager)) && t.status !== 'CLOSED';
  var assignBlock = canAssign ? ('<div class="fld" style="margin-top:12px"><label>Assign to engineer (current: ' +
    esc(t.current_assignee_username || t.assignee || 'unassigned') + ')</label>' +
    '<select id="a_assignee"><option value="">Loading roster…</option></select>' +
    '<button class="btn o sm" style="margin-top:7px" onclick="act(' + t.id + ',\'assign\')">Assign</button></div>') : '';
  if (canAssign) setTimeout(function () { loadAssignRoster(t.team, t.current_assignee_username || t.assignee); }, 0);
  var form = (mine && t.status !== 'CLOSED') ? ('<div class="grid2" style="margin-top:6px">' +
    '<div class="fld"><label>Diagnosis</label><textarea id="a_diag" rows="2">' + esc(t.diagnosis || '') + '</textarea></div>' +
    '<div class="fld"><label>Action taken</label><textarea id="a_act" rows="2">' + esc(t.action_taken || '') + '</textarea></div>' +
    '<div class="fld"><label>Root cause</label><input id="a_rc" value="' + esc(t.root_cause || '') + '"></div>' +
    '<div class="fld"><label>Parts / replacement</label><input id="a_parts" value="' + esc(t.parts || '') + '"></div>' +
    '<div class="fld"><label>Resolution (required to resolve)</label><textarea id="a_res" rows="2">' + esc(t.resolution || '') + '</textarea></div>' +
    '<div class="fld"><label>Pending reason (required to hold)</label><input id="a_pend" value="' + esc(t.pending_reason || '') + '"></div>' +
    '<div class="fld"><label>Confirmed by (MMU / field)</label><input id="a_conf" value="' + esc(t.confirmed_by || '') + '" placeholder="Name at the MMU who confirmed"></div>' +
    '<div class="fld"><label>Re-route remark</label><input id="a_note" placeholder="Remark for re-routing to another team"></div>' +
    (ME.role !== 'CC_MANAGER' ? '<div class="fld"><label>Escalation reason (required to escalate)</label><input id="a_esc_reason" placeholder="Why this needs the Global Team Executive\'s attention"></div>' : '') +
    '</div>') : '';
  
  document.getElementById('modal').innerHTML = '<div class="ovl" onclick="if(event.target===this)closeT()"><div class="sheet">' +
    '<div class="sh"><div><div style="font-size:19px;font-weight:800">' + esc(t.ticket_no) + ' &middot; ' + esc(t.category_label) + (t.vip ? ' <span class="pill p-crit">VIP</span>' : '') + '</div>' +
    '<div style="font-size:12.5px;opacity:.9;margin-top:3px">' + esc(t.mmu_vehicle || '—') + ' &middot; ' + esc(t.district || '') + ' &middot; ' + esc(t.team_label) + ' &middot; <span class="pill p-crit" style="font-size:10.5px;padding:2px 7px">EMERGENCY SERVICE</span></div></div>' +
    '<button class="x" onclick="closeT()">&times;</button></div><div class="sb">' +
    '<div style="display:flex;gap:9px;flex-wrap:wrap;margin-bottom:14px">' + priorityPill(t.priority) + '<span class="pill p-mut">' + esc((t.status || '').replace(/_/g, ' ')) + '</span>' + tatPill(t).replace('<span ', '<span id="modalTat" ') +
    (t.escalated ? '<span class="pill p-crit">ESCALATED' + (t.escalation_count > 1 ? ' &times;' + esc(t.escalation_count) : '') + '</span>' : '') + '<span class="pill p-mut">TAT ' + esc(t.tat_mins) + ' min</span>' +
    (t.paused_minutes ? '<span class="pill p-mut">Paused ' + esc(t.paused_minutes) + 'm so far</span>' : '') + '</div>' +
    '<div class="grid2"><div>' + row('Ticket Type', (META.ticket_types && META.ticket_types[t.ticket_type] && META.ticket_types[t.ticket_type].label) || t.ticket_type) + row('Sub-Category', t.subcategory_label_snapshot) + row('Problem', t.problem) + row('Equipment', t.equipment) + row('Error code', t.error_code) + row('Impact', t.impact) + row('Impact Level', t.impact_code) + row('Urgency Level', t.urgency_code) +
    row('Caller', (t.caller_name || '') + (t.caller_phone ? (' · ' + t.caller_phone) : '')) + row('Location', t.location) + '</div>' +
    '<div>' + row('Raised At', formatDT(t.created_at)) +
    row('Response Due (SLA)', t.response_due_at ? (formatDT(t.response_due_at) + (t.response_breached ? ' — BREACHED' : '')) : '') +
    row('Resolution Due (SLA)', formatDT(t.due_at)) + row('SLA Policy', t.sla_policy_code) +
    row('Acknowledged', formatDT(t.acknowledged_at)) + row('Resolved', formatDT(t.resolved_at)) +
    row('Assigned to', t.assignee) + row('Confirmed by', t.confirmed_by) + row('Closed', formatDT(t.closed_at)) + row('Owner', t.owner) +
    row('Escalation reason', t.escalation_note) + '</div></div>' +
    form + reroute + assignBlock +
    '<div style="display:flex;gap:9px;flex-wrap:wrap;margin-top:14px">' + A.join('') + '</div>' +
    '<h4 style="margin:18px 0 8px;font-size:14px">Hierarchy (L1–L4) &amp; Assignment History</h4>' +
    '<div id="modal_assignments"><div class="muted">Loading…</div></div>' +
    '<h4 style="margin:18px 0 8px;font-size:14px">Attachments / Evidence</h4>' +
    '<div id="modal_attachments"><div class="muted">Loading attachments...</div></div>' +
    '<h4 style="margin:18px 0 8px;font-size:14px">Audit trail</h4><div class="tl">' +
    (evs || []).map(function (e) { return '<div class="e"><b>' + esc(e.action) + '</b> — ' + esc(e.detail || '') + '<div class="muted">' + esc(e.at) + ' · ' + esc(e.actor) + ' (' + esc(e.actor_role) + ')</div></div>'; }).join('') +
    '</div></div></div></div>';
  if (MODAL_TICK) clearInterval(MODAL_TICK);
  if (t.status !== 'CLOSED') MODAL_TICK = setInterval(function () { updateModalCountdown(t); }, 30000);
}
function act(id, a) {
  var g = function (i) { var e = document.getElementById(i); return e ? e.value.trim() : undefined; };
  var note = g('a_note');
  if (a === 'escalate') {
    var reason = g('a_esc_reason');
    if (!reason) { toast('Enter a reason before escalating'); return; }
    note = reason;
  }
  if (a === 'not_resolved') {
    var reason = prompt('What is still not working / reason for rejection? (required):');
    if (reason === null) return;
    if (!reason.trim()) { toast('A reason is required to mark as not resolved'); return; }
    note = reason.trim();
  }
  var b = {
    id: id, action: a, diagnosis: g('a_diag'), action_taken: g('a_act'), root_cause: g('a_rc'), parts: g('a_parts'),
    resolution: g('a_res'), pending_reason: g('a_pend'), confirmed_by: g('a_conf'), note: note,
    team: g('a_team'), priority: g('a_pri'), assignee: g('a_assignee')
  };
  api('POST', '/ticket/action', b).then(function () { toast('Done: ' + a); closeT(); load(); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Action failed'); });
}

function loadAssignRoster(team, current) {
  var sel = document.getElementById('a_assignee');
  if (!sel) return;
  var qs = ME.role === 'CC_MANAGER' ? ('?team=' + encodeURIComponent(team)) : '';
  api('GET', '/users/team-roster' + qs).then(function (rows) {
    sel.innerHTML = '<option value="">— Choose —</option>' + rows.map(function (u) {
      return '<option value="' + esc(u.username) + '"' + (u.username === current ? ' selected' : '') + '>' + esc(u.name) + '</option>';
    }).join('');
  }).catch(function () { sel.innerHTML = '<option value="">Could not load roster</option>'; });
}

function loadAssignments(id, currentLevel) {
  var box = document.getElementById('modal_assignments');
  if (!box) return;
  api('GET', '/ticket/' + id + '/assignments').then(function (rows) {
    var active = rows.filter(function (r) { return r.status === 'ACTIVE'; });
    var history = rows.filter(function (r) { return r.status !== 'ACTIVE'; }).slice().reverse();
    var chainHtml = ['L1', 'L2', 'L3', 'L4'].map(function (lvl) {
      var row = active.find(function (r) { return r.level === lvl; });
      var label = row ? (row.user_name || row.team_name || row.team_code || '—') : '—';
      var isCurrent = lvl === currentLevel;
      return '<span class="pill ' + (isCurrent ? 'p-crit' : 'p-mut') + '" style="margin-right:6px" title="' + esc(row ? row.source : '') + '">' + lvl + ': ' + esc(label) + '</span>';
    }).join('');
    var historyHtml = history.length ? ('<div class="tl">' + history.map(function (r) {
      return '<div class="e"><b>' + esc(r.level) + '</b> — ' + esc(r.user_name || r.team_name || r.team_code || '—') +
        ' <span class="muted">(' + esc(r.source) + ')</span>' +
        '<div class="muted">' + esc(r.assigned_at) + (r.released_at ? (' → released ' + esc(r.released_at)) : '') + '</div></div>';
    }).join('') + '</div>') : '<div class="muted">No prior reassignments.</div>';
    box.innerHTML = '<div style="margin-bottom:10px">' + chainHtml + '</div>' + historyHtml;
  }).catch(function () { box.innerHTML = '<div class="muted">Could not load assignment history.</div>'; });
}

function loadAttachments(id) {
  var box = document.getElementById('modal_attachments');
  if (!box) return;
  api('GET', '/ticket/' + id + '/attachments').then(function(rows) {
    var list = rows.length ? rows.map(function(a) {
      return '<div style="display:flex;align-items:center;justify-content:space-between;padding:8px 0;border-bottom:1px solid #f3f4f6">' +
        '<div><a href="/cccapi/uploads/' + esc(a.filename) + '" target="_blank" style="color:var(--pur);font-weight:600;text-decoration:none">' + esc(a.original_name) + '</a>' +
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

function loadNotifs() {
  api('GET', '/notifications').then(function (d) {
    var oldUnread = (NOTIFS || []).filter(function (x) { return !x.read_at; }).length;
    NOTIFS = d.rows || [];
    var newUnread = (NOTIFS || []).filter(function (x) { return !x.read_at; }).length;
    if (newUnread > oldUnread && oldUnread !== 0) {
      playAlertSound('new');
    }
    renderBell();
    if (NOTIF_OPEN) renderNotifPanel();
  }).catch(function () { });
}
function renderBell() {
  var unreadCount = (NOTIFS || []).filter(function (x) { return !x.read_at; }).length;
  var b = document.getElementById('nbadge');
  if (!b) return;
  if (unreadCount > 0) {
    b.textContent = unreadCount > 99 ? '99+' : unreadCount;
    b.classList.remove('hide');
    b.style.display = 'inline-block';
  } else {
    b.textContent = '';
    b.classList.add('hide');
    b.style.display = 'none';
  }
}
function closeNotifs() {
  if (NOTIF_OPEN) {
    NOTIF_OPEN = false;
    var np = document.getElementById('npanel');
    if (np) np.innerHTML = '';
  }
}
function markAllNotifsRead() {
  if (!NOTIFS || !NOTIFS.length) return;
  var unread = NOTIFS.filter(function (n) { return !n.read_at; });
  if (unread.length > 0) {
    unread.forEach(function (n) { n.read_at = 'now'; });
    renderBell();
    api('POST', '/notifications/read-all', {}).catch(function () {});
  }
}
function toggleNotifs() {
  NOTIF_OPEN = !NOTIF_OPEN;
  if (NOTIF_OPEN) {
    renderNotifPanel();
    // Viewing notifications clears unread status so icon numbers are removed
    markAllNotifsRead();
  } else {
    var np = document.getElementById('npanel');
    if (np) np.innerHTML = '';
  }
}
function renderNotifPanel() {
  var unreadCount = (NOTIFS || []).filter(function (n) { return !n.read_at; }).length;
  var markAllBtn = unreadCount > 0 ?
    '<button class="btn sm o" style="font-size:11px;padding:2px 8px;border-radius:6px;margin:0" onclick="markAllNotifsRead();renderNotifPanel()">Mark all read</button>' : '';
  var body = !NOTIFS.length ? '<div class="empty" style="padding:24px">No notifications</div>' :
    NOTIFS.map(function (n) {
      return '<div class="ni' + (n.read_at ? '' : ' unread') + '" onclick="openNotif(' + n.id + ',' + (n.ticket_id || 'null') + ')">' +
        '<div class="t">' + esc((n.type || '').replace(/_/g, ' ')) + '</div><div>' + esc(n.message) + '</div><div class="muted">' + esc(n.created_at) + '</div></div>';
    }).join('');
  document.getElementById('npanel').innerHTML = '<div class="npanel"><div class="nh" style="display:flex;align-items:center;justify-content:space-between"><span>Notifications</span>' + markAllBtn + '</div>' + body + '</div>';
}
function openNotif(id, ticketId) {
  var n = NOTIFS.find(function (x) { return x.id === id; });
  if (n && !n.read_at) {
    n.read_at = 'now';
    api('POST', '/notifications/' + id + '/read', {}).catch(function () {});
    renderBell();
  }
  closeNotifs();
  if (ticketId) { TAB = 'queue'; render(); openT(ticketId); }
}

/* ---------- dashboard ---------- */
function attnGoto(status, scope, priority) {
  TAB = 'queue';
  FILT.status = status || '';
  FILT.scope = scope || '';
  FILT.priority = priority || '';
  FILT.mmu_vehicle = DASH_FILT.mmu_vehicle || '';
  FILT.district = DASH_FILT.district || '';
  if (FILT.district && META && META.districts) {
    var dObj = META.districts.find(function (d) { return d.name === FILT.district; });
    if (dObj) FILT.district_id = dObj.id;
  } else {
    FILT.district_id = '';
  }
  FILT.team = DASH_FILT.team || '';
  FILT.date_preset = DASH_FILT.date_preset || '';
  FILT.date_from = DASH_FILT.date_from || '';
  FILT.date_to = DASH_FILT.date_to || '';
  FILT.q = '';
  FILT.category = '';
  FILT.page = 1;
  saveState();
  render();
  load(true);
}

function exportDash() {
  var qs = dashQS();
  var url = '/reports/summary.xlsx' + (qs ? qs : '?period=daily');
  downloadExcel(url, 'Dashboard_Summary.xlsx');
}

function formatISODate(d) {
  if (!d) return '';
  var pad = function (n) { return (n < 10 ? '0' : '') + n; };
  return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate());
}

function openCalendarPicker(id) {
  var el = document.getElementById(id);
  if (el) {
    el.focus();
    try {
      if (typeof el.showPicker === 'function') el.showPicker();
    } catch (e) {}
  }
}

function onDashTimePresetChange(preset) {
  var customWrap = document.getElementById('dash_custom_dates');
  if (preset === 'custom') {
    DASH_FILT.date_preset = 'custom';
    if (customWrap) customWrap.style.display = 'flex';
    if (customWrap) {
      customWrap.style.display = 'flex';
      var fEl = document.getElementById('dash_from');
      var tEl = document.getElementById('dash_to');
      var now = new Date();
      if (fEl && !fEl.value) {
        var d30 = new Date(now.getTime() - 30 * 24 * 3600 * 1000);
        fEl.value = DASH_FILT.date_from || formatISODate(d30);
      }
      if (tEl && !tEl.value) {
        tEl.value = DASH_FILT.date_to || formatISODate(now);
      }
      setTimeout(function () { openCalendarPicker('dash_from'); }, 60);
    }
    return;
  }
  if (customWrap) customWrap.style.display = 'none';
  DASH_FILT.date_preset = preset;
  applyDashFilters();
}

function applyDashFilters() {
  var distEl = document.getElementById('dash_dist');
  DASH_FILT.district = distEl ? distEl.value : '';

  var teamEl = document.getElementById('dash_team');
  DASH_FILT.team = teamEl ? teamEl.value : '';

  var vehEl = document.getElementById('dash_veh');
  DASH_FILT.mmu_vehicle = vehEl ? vehEl.value.trim() : '';

  var timeSel = (document.getElementById('dash_time') ? document.getElementById('dash_time').value : '') || DASH_FILT.date_preset || '';
  DASH_FILT.date_preset = timeSel;
  var now = new Date();
  var pad = function (n) { return (n < 10 ? '0' : '') + n; };
  var fmtDate = function (d) { return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()); };

  if (timeSel === 'today') {
    var today = fmtDate(now);
    DASH_FILT.date_from = today;
    DASH_FILT.date_to = today;
  } else if (timeSel === 'yesterday') {
    var y = new Date();
    y.setDate(y.getDate() - 1);
    var yDate = fmtDate(y);
    DASH_FILT.date_from = yDate;
    DASH_FILT.date_to = yDate;
  } else if (timeSel === '24h') {
    var yesterday = new Date(now.getTime() - 24 * 3600 * 1000);
    DASH_FILT.date_from = fmtDate(yesterday);
    DASH_FILT.date_to = fmtDate(now);
  } else if (timeSel === '7d') {
    var last7 = new Date(now.getTime() - 7 * 24 * 3600 * 1000);
    DASH_FILT.date_from = fmtDate(last7);
    DASH_FILT.date_to = fmtDate(now);
  } else if (timeSel === '30d') {
    var last30 = new Date(now.getTime() - 30 * 24 * 3600 * 1000);
    DASH_FILT.date_from = fmtDate(last30);
    DASH_FILT.date_to = fmtDate(now);
  } else if (timeSel === 'custom') {
    DASH_FILT.date_from = gv('dash_from') || '';
    DASH_FILT.date_to = gv('dash_to') || '';
  } else {
    DASH_FILT.date_from = '';
    DASH_FILT.date_to = '';
  }

  saveState();
  load(true);
}

function clearDashFilters() {
  DASH_FILT.district = '';
  DASH_FILT.team = '';
  DASH_FILT.mmu_vehicle = '';
  DASH_FILT.date_preset = '';
  DASH_FILT.date_from = '';
  DASH_FILT.date_to = '';
  try {
    sessionStorage.removeItem('ccc_dash_filt');
    localStorage.removeItem('ccc_dash_filt');
  } catch (e) {}
  saveState();
  load(true);
}

/* ---------- dashboard state & helpers for sections A through H ---------- */
window.DASH_TREND_VIEW = window.DASH_TREND_VIEW || 'week'; // 'week', 'month', 'custom'
window.DASH_AGEING_VIEW = window.DASH_AGEING_VIEW || 'week'; // 'week', 'month', 'custom'
window.DASH_APPROLE_VIEW = window.DASH_APPROLE_VIEW || 'app'; // 'app', 'role'
window.DASH_ACTIVITY_FILTER = window.DASH_ACTIVITY_FILTER || 'all'; // 'all', 'p1_p2', 'breach', 'escalate', 'resolved', 'status'

function setDashTrendView(mode) {
  window.DASH_TREND_VIEW = mode;
  var el = document.getElementById('dash_trend_chart_container');
  if (el && DASH) el.innerHTML = renderDashTrendChartContent(DASH.trend || [], mode);
  var bar = document.getElementById('dash_trend_custom_bar');
  if (bar) bar.style.display = (mode === 'custom') ? 'flex' : 'none';

  var btns = document.querySelectorAll('.dash-trend-btn');
  btns.forEach(function (b) {
    b.classList.toggle('active', b.getAttribute('data-mode') === mode);
  });

  if (mode === 'custom') {
    var now = new Date();
    var fEl = document.getElementById('trend_date_from');
    var tEl = document.getElementById('trend_date_to');
    if (fEl && !fEl.value) {
      var d30 = new Date(now.getTime() - 30 * 24 * 3600 * 1000);
      fEl.value = DASH_FILT.date_from || formatISODate(d30);
    }
    if (tEl && !tEl.value) {
      tEl.value = DASH_FILT.date_to || formatISODate(now);
    }
    var el = document.getElementById('dash_trend_chart_container');
    if (el && DASH) el.innerHTML = renderDashTrendChartContent(DASH.trend || [], mode);
    setTimeout(function () { openCalendarPicker('trend_date_from'); }, 60);
  } else {
    var el = document.getElementById('dash_trend_chart_container');
    if (el && DASH) el.innerHTML = renderDashTrendChartContent(DASH.trend || [], mode);
  }
}

function applyTrendCustomDates() {
  var f = (document.getElementById('trend_date_from') ? document.getElementById('trend_date_from').value : '') || '';
  var t = (document.getElementById('trend_date_to') ? document.getElementById('trend_date_to').value : '') || '';
  if (!f && !t) {
    toast('Please select at least one date from the calendar');
    return;
  }
  DASH_FILT.date_preset = 'custom';
  DASH_FILT.date_from = f;
  DASH_FILT.date_to = t;
  window.DASH_TREND_VIEW = 'custom';

  var df = document.getElementById('dash_from');
  var dt = document.getElementById('dash_to');
  var dtSel = document.getElementById('dash_time');
  if (df) df.value = f;
  if (dt) dt.value = t;
  if (dtSel) dtSel.value = 'custom';
  var customWrap = document.getElementById('dash_custom_dates');
  if (customWrap) customWrap.style.display = 'flex';

  var af = document.getElementById('ageing_date_from');
  var at = document.getElementById('ageing_date_to');
  if (af) af.value = f;
  if (at) at.value = t;

  saveState();
  load(true);
}

function onTrendDateChange() {
  var el = document.getElementById('dash_trend_chart_container');
  if (el && DASH) el.innerHTML = renderDashTrendChartContent(DASH.trend || [], 'custom');
}

function renderDashTrendChartContent(trendRows, mode) {
  var MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  function parseDate(s) {
    if (!s) return null;
    var p = String(s).trim().split('-');
    if (p.length !== 3) return null;
    var y = parseInt(p[0], 10), m = parseInt(p[1], 10) - 1, d = parseInt(p[2], 10);
    if (isNaN(y) || isNaN(m) || isNaN(d)) return null;
    return new Date(y, m, d, 12, 0, 0);
  }
  function toISO(dt) {
    var y = dt.getFullYear();
    var m = String(dt.getMonth() + 1);
    if (m.length < 2) m = '0' + m;
    var d = String(dt.getDate());
    if (d.length < 2) d = '0' + d;
    return y + '-' + m + '-' + d;
  }
  function toHuman(dt) {
    var d = String(dt.getDate());
    if (d.length < 2) d = '0' + d;
    return d + ' ' + MONTH_NAMES[dt.getMonth()];
  }
  function toFullHuman(dt) {
    var d = String(dt.getDate());
    if (d.length < 2) d = '0' + d;
    return d + ' ' + MONTH_NAMES[dt.getMonth()] + ' ' + dt.getFullYear();
  }

  var now = new Date();
  var sDate = null, eDate = null;

  if (mode === 'week') {
    eDate = DASH_FILT.date_to ? parseDate(DASH_FILT.date_to) : new Date(now.getFullYear(), now.getMonth(), now.getDate(), 12);
    if (!eDate) eDate = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 12);
    sDate = new Date(eDate.getTime() - 6 * 24 * 3600 * 1000);
  } else if (mode === 'month') {
    eDate = DASH_FILT.date_to ? parseDate(DASH_FILT.date_to) : new Date(now.getFullYear(), now.getMonth(), now.getDate(), 12);
    if (!eDate) eDate = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 12);
    sDate = new Date(eDate.getTime() - 29 * 24 * 3600 * 1000);
  } else {
    // custom
    var fVal = (document.getElementById('trend_date_from') ? document.getElementById('trend_date_from').value : '') || DASH_FILT.date_from || '';
    var tVal = (document.getElementById('trend_date_to') ? document.getElementById('trend_date_to').value : '') || DASH_FILT.date_to || '';
    if (fVal) sDate = parseDate(fVal);
    if (tVal) eDate = parseDate(tVal);
    if (!sDate && !eDate) {
      if (trendRows && trendRows.length) {
        sDate = parseDate(trendRows[0].d);
        eDate = parseDate(trendRows[trendRows.length - 1].d);
      } else {
        eDate = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 12);
        sDate = new Date(eDate.getTime() - 29 * 24 * 3600 * 1000);
      }
    } else if (!sDate && eDate) {
      sDate = new Date(eDate.getTime() - 29 * 24 * 3600 * 1000);
    } else if (sDate && !eDate) {
      eDate = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 12);
    }
  }

  if (!sDate) sDate = new Date(now.getTime() - 6 * 24 * 3600 * 1000);
  if (!eDate) eDate = new Date(now.getTime());

  if (sDate.getTime() > eDate.getTime()) {
    var tmp = sDate;
    sDate = eDate;
    eDate = tmp;
  }

  // Build row lookup from database rows
  var rowMap = {};
  (trendRows || []).forEach(function (r) {
    if (r && r.d) {
      rowMap[r.d] = {
        created_count: Number(r.created_count || 0),
        resolved_count: Number(r.resolved_count || 0)
      };
    }
  });

  // Generate continuous day series
  var data = [];
  var cur = new Date(sDate.getFullYear(), sDate.getMonth(), sDate.getDate(), 12);
  var targetEnd = new Date(eDate.getFullYear(), eDate.getMonth(), eDate.getDate(), 12);
  var safetyLimit = 0;
  while (cur.getTime() <= targetEnd.getTime() && safetyLimit < 180) {
    var dStr = toISO(cur);
    var entry = rowMap[dStr] || { created_count: 0, resolved_count: 0 };
    data.push({
      d: dStr,
      dt: new Date(cur.getTime()),
      created_count: entry.created_count,
      resolved_count: entry.resolved_count
    });
    cur.setDate(cur.getDate() + 1);
    safetyLimit++;
  }

  if (!data.length) {
    return '<div class="muted" style="padding:40px;text-align:center">No trend activity logged for this time period</div>';
  }

  var maxVal = 5;
  data.forEach(function (r) {
    if (r.created_count > maxVal) maxVal = r.created_count;
    if (r.resolved_count > maxVal) maxVal = r.resolved_count;
  });

  var totalCreated = data.reduce(function (acc, x) { return acc + (x.created_count || 0); }, 0);
  var totalResolved = data.reduce(function (acc, x) { return acc + (x.resolved_count || 0); }, 0);
  var resolutionRate = totalCreated > 0 ? (Math.round((totalResolved / totalCreated) * 1000) / 10) : 100;

  var chartW = 560;
  var chartH = 150;
  var padLeft = 32;
  var padBottom = 26;
  var padTop = 16;
  var padRight = 16;
  var plotW = chartW - padLeft - padRight;
  var plotH = chartH - padTop - padBottom;

  var numPoints = data.length;
  var slotW = plotW / Math.max(1, numPoints);
  var barW = Math.max(2, Math.min(12, slotW * 0.35));

  // Determine tick label interval
  var maxLabels = (numPoints <= 7 ? numPoints : 6);
  var step = Math.max(1, Math.round(numPoints / maxLabels));
  var minGap = Math.max(2, Math.floor(step * 0.7));

  var barsHtml = '';
  data.forEach(function (d, i) {
    var xSlotStart = padLeft + i * slotW;
    var xMid = xSlotStart + slotW / 2;

    var cH = d.created_count > 0 ? Math.max(3, Math.round(((d.created_count) / maxVal) * plotH)) : 0;
    var rH = d.resolved_count > 0 ? Math.max(3, Math.round(((d.resolved_count) / maxVal) * plotH)) : 0;

    var cY = padTop + plotH - cH;
    var rY = padTop + plotH - rH;

    var dateLbl = toHuman(d.dt);
    var fullLbl = toFullHuman(d.dt);

    // Transparent full-slot hit area for hover tooltip on every day
    barsHtml += '<rect x="' + xSlotStart + '" y="' + padTop + '" width="' + slotW + '" height="' + plotH + '" fill="transparent" style="cursor:pointer">' +
      '<title>Date: ' + esc(fullLbl) + '&#10;Tickets Created: ' + d.created_count + '&#10;Tickets Resolved: ' + d.resolved_count + '</title></rect>';

    // Created bar (indigo)
    if (d.created_count > 0) {
      barsHtml += '<rect x="' + (xMid - barW - 0.5) + '" y="' + cY + '" width="' + barW + '" height="' + cH + '" fill="#6366F1" rx="2" style="cursor:pointer">' +
        '<title>Date: ' + esc(fullLbl) + '&#10;Tickets Created: ' + d.created_count + '</title></rect>';
    }
    // Resolved bar (emerald)
    if (d.resolved_count > 0) {
      barsHtml += '<rect x="' + (xMid + 0.5) + '" y="' + rY + '" width="' + barW + '" height="' + rH + '" fill="#10B981" rx="2" style="cursor:pointer">' +
        '<title>Date: ' + esc(fullLbl) + '&#10;Tickets Resolved: ' + d.resolved_count + '</title></rect>';
    }

    // X-axis date labels
    var printLabel = false;
    if (numPoints <= 7) {
      printLabel = true;
    } else if (i === 0 || i === numPoints - 1) {
      printLabel = true;
    } else if (i % step === 0 && i >= minGap && (numPoints - 1 - i) >= minGap) {
      printLabel = true;
    }

    if (printLabel) {
      barsHtml += '<text x="' + xMid + '" y="' + (chartH - 6) + '" font-size="9.5" fill="#6B7280" font-weight="500" text-anchor="middle">' + esc(dateLbl) + '</text>';
    }
  });

  // Grid lines
  var midVal = Math.round(maxVal / 2);
  var gridHtml = '<line x1="' + padLeft + '" y1="' + (padTop + plotH) + '" x2="' + (chartW - padRight) + '" y2="' + (padTop + plotH) + '" stroke="#E5E7EB" stroke-width="1"/>' +
    '<text x="' + (padLeft - 6) + '" y="' + (padTop + plotH + 4) + '" font-size="9" fill="#9CA3AF" text-anchor="end">0</text>' +
    '<line x1="' + padLeft + '" y1="' + (padTop + Math.round(plotH / 2)) + '" x2="' + (chartW - padRight) + '" y2="' + (padTop + Math.round(plotH / 2)) + '" stroke="#F3F4F6" stroke-dasharray="2,2"/>' +
    '<text x="' + (padLeft - 6) + '" y="' + (padTop + Math.round(plotH / 2) + 4) + '" font-size="9" fill="#9CA3AF" text-anchor="end">' + midVal + '</text>' +
    '<line x1="' + padLeft + '" y1="' + padTop + '" x2="' + (chartW - padRight) + '" y2="' + padTop + '" stroke="#F3F4F6" stroke-dasharray="2,2"/>' +
    '<text x="' + (padLeft - 6) + '" y="' + (padTop + 4) + '" font-size="9" fill="#9CA3AF" text-anchor="end">' + maxVal + '</text>';

  var startStr = toHuman(data[0].dt);
  var endStr = toHuman(data[data.length - 1].dt);

  return '<div style="width:100%">' +
    '<div style="display:flex;justify-content:space-between;align-items:center;padding:0 4px 6px;font-size:11.5px;color:var(--ink2)">' +
      '<span>Timeline: <strong style="color:var(--ink)">' + esc(startStr) + '</strong> to <strong style="color:var(--ink)">' + esc(endStr) + '</strong> (' + numPoints + ' days)</span>' +
      '<span>Activity: <strong style="color:var(--ink)">' + (totalCreated + totalResolved) + '</strong> tickets</span>' +
    '</div>' +
    '<svg viewBox="0 0 ' + chartW + ' ' + chartH + '" style="width:100%;height:auto;display:block">' +
      gridHtml + barsHtml +
    '</svg>' +
    '<div style="display:flex;justify-content:space-around;padding-top:12px;margin-top:6px;border-top:1px solid #F3F4F6;flex-wrap:wrap;gap:10px">' +
      '<div><span style="display:inline-block;width:8px;height:8px;border-radius:2px;background:#6366F1;margin-right:6px"></span><span class="muted" style="font-size:12px">Total Created:</span> <b style="font-size:13px;color:var(--ink)">' + totalCreated + '</b></div>' +
      '<div><span style="display:inline-block;width:8px;height:8px;border-radius:2px;background:#10B981;margin-right:6px"></span><span class="muted" style="font-size:12px">Total Resolved:</span> <b style="font-size:13px;color:var(--ink)">' + totalResolved + '</b></div>' +
      '<div><span class="muted" style="font-size:12px">Resolution Rate:</span> <b style="font-size:13px;color:#059669">' + resolutionRate + '%</b></div>' +
    '</div>' +
  '</div>';
}

function renderDashDonutChart(priList) {
  if (!priList || !priList.length) return '<div class="muted" style="padding:20px;text-align:center">No priority data</div>';
  var total = priList.reduce(function (acc, x) { return acc + (x.count || 0); }, 0);
  if (total === 0) total = 1;

  var r = 40;
  var c = 2 * Math.PI * r; // ~251.327
  var currentOffset = 0;

  var pathsHtml = priList.map(function (item) {
    var fraction = (item.count || 0) / total;
    var dash = (fraction * c).toFixed(2);
    var space = (c - dash).toFixed(2);
    var offset = (-currentOffset).toFixed(2);
    currentOffset += (fraction * c);
    return '<circle cx="50" cy="50" r="' + r + '" fill="transparent" ' +
      'stroke="' + item.color + '" stroke-width="14" ' +
      'stroke-dasharray="' + dash + ' ' + space + '" ' +
      'stroke-dashoffset="' + offset + '">' +
      '<title>' + esc(item.label) + ': ' + item.count + ' (' + item.pct + '%)</title>' +
    '</circle>';
  }).join('');

  var legendHtml = priList.map(function (item) {
    return '<div class="dash-donut-item">' +
      '<div class="dash-donut-item-left">' +
        '<span class="dash-donut-dot" style="background:' + item.color + '"></span>' +
        '<span>' + esc(item.label) + '</span>' +
      '</div>' +
      '<div class="dash-donut-item-right">' +
        '<b style="color:var(--ink)">' + item.count + '</b>' +
        '<span style="font-size:12px;color:var(--ink2);width:45px;text-align:right">(' + item.pct + '%)</span>' +
      '</div>' +
    '</div>';
  }).join('');

  return '<div class="dash-donut-layout">' +
    '<div class="dash-donut-svg-wrap">' +
      '<svg viewBox="0 0 100 100" style="transform:rotate(-90deg);width:100%;height:100%">' +
        pathsHtml +
      '</svg>' +
      '<div class="dash-donut-center">' +
        '<div class="dash-donut-center-num">' + (total === 1 && priList[0].count === 0 ? 0 : total) + '</div>' +
        '<div class="dash-donut-center-lbl">Total</div>' +
      '</div>' +
    '</div>' +
    '<div class="dash-donut-legend">' + legendHtml + '</div>' +
  '</div>';
}

function setDashAgeingView(mode) {
  window.DASH_AGEING_VIEW = mode;
  var bar = document.getElementById('dash_ageing_custom_bar');
  if (bar) bar.style.display = (mode === 'custom') ? 'flex' : 'none';

  var btns = document.querySelectorAll('.dash-ageing-btn');
  btns.forEach(function (b) {
    b.classList.toggle('active', b.getAttribute('data-mode') === mode);
  });
  if (mode === 'week') {
    onDashTimePresetChange('7d');
  } else if (mode === 'month') {
    onDashTimePresetChange('30d');
  } else if (mode === 'custom') {
    var now = new Date();
    var fEl = document.getElementById('ageing_date_from');
    var tEl = document.getElementById('ageing_date_to');
    if (fEl && !fEl.value) {
      var d30 = new Date(now.getTime() - 30 * 24 * 3600 * 1000);
      fEl.value = DASH_FILT.date_from || formatISODate(d30);
    }
    if (tEl && !tEl.value) {
      tEl.value = DASH_FILT.date_to || formatISODate(now);
    }
    setTimeout(function () { openCalendarPicker('ageing_date_from'); }, 60);
  }
}

function applyAgeingCustomDates() {
  var f = (document.getElementById('ageing_date_from') ? document.getElementById('ageing_date_from').value : '') || '';
  var t = (document.getElementById('ageing_date_to') ? document.getElementById('ageing_date_to').value : '') || '';
  if (!f && !t) {
    toast('Please select at least one date from the calendar');
    return;
  }
  DASH_FILT.date_preset = 'custom';
  DASH_FILT.date_from = f;
  DASH_FILT.date_to = t;
  window.DASH_AGEING_VIEW = 'custom';

  var df = document.getElementById('dash_from');
  var dt = document.getElementById('dash_to');
  var dtSel = document.getElementById('dash_time');
  if (df) df.value = f;
  if (dt) dt.value = t;
  if (dtSel) dtSel.value = 'custom';
  var customWrap = document.getElementById('dash_custom_dates');
  if (customWrap) customWrap.style.display = 'flex';

  var tf = document.getElementById('trend_date_from');
  var tt = document.getElementById('trend_date_to');
  if (tf) tf.value = f;
  if (tt) tt.value = t;

  saveState();
  load(true);
}

function renderDashAgeing(ageingList) {
  if (!ageingList || !ageingList.length) return '<div class="muted">No ticket ageing data</div>';
  return '<div class="dash-ageing-grid">' +
    ageingList.map(function (item) {
      return '<div class="dash-ageing-row">' +
        '<div class="dash-ageing-bracket">' + esc(item.bracket) + '</div>' +
        '<div class="dash-ageing-bar-bg" title="' + esc(item.desc) + '">' +
          '<div class="dash-ageing-bar-fill" style="width:' + item.pct + '%;background:' + item.color + '"></div>' +
        '</div>' +
        '<div class="dash-ageing-stats">' +
          '<span>' + item.count + '</span> <span style="font-size:12px;color:var(--ink2);font-weight:normal">(' + item.pct + '%)</span>' +
        '</div>' +
      '</div>';
    }).join('') +
  '</div>';
}

function setDashAppRoleView(mode) {
  window.DASH_APPROLE_VIEW = mode;
  var el = document.getElementById('dash_approle_container');
  if (el && DASH) el.innerHTML = renderDashAppRoleContent(DASH, mode);
  var bApp = document.getElementById('dash_app_btn');
  var bRole = document.getElementById('dash_role_btn');
  if (bApp) bApp.classList.toggle('active', mode === 'app');
  if (bRole) bRole.classList.toggle('active', mode === 'role');
}

function renderDashAppRoleContent(d, mode) {
  var list = mode === 'app' ? (d.by_application || []) : (d.by_role || []);
  if (!list.length) return '<div class="muted" style="padding:20px;text-align:center">No records</div>';

  return '<div style="display:flex;flex-direction:column;gap:10px">' +
    list.map(function (item) {
      var color = mode === 'app' ? (item.code === 'CALL' ? '#6366F1' : '#059669') : '#8B5CF6';
      return '<div style="padding:8px 12px;background:#F9FAFB;border:1px solid #F3F4F6;border-radius:8px">' +
        '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">' +
          '<span style="font-size:13px;font-weight:700;color:var(--ink)">' + esc(item.name) + '</span>' +
          '<div><b style="font-size:13.5px;color:var(--ink)">' + item.count + '</b> <span style="font-size:12px;color:var(--ink2)">(' + item.pct + '%)</span></div>' +
        '</div>' +
        '<div style="height:6px;background:#E5E7EB;border-radius:3px;overflow:hidden">' +
          '<div style="width:' + item.pct + '%;height:100%;background:' + color + ';border-radius:3px"></div>' +
        '</div>' +
      '</div>';
    }).join('') +
  '</div>';
}

function renderDashCategory(catList) {
  if (!catList || !catList.length) return '<tr><td colspan="4" style="text-align:center;color:var(--ink2);padding:20px">No category records</td></tr>';

  return catList.map(function (r) {
    var catLabel = (META && META.routing && META.routing[r.category]) ? META.routing[r.category].label : (r.category || 'General');
    var pct = r.pct || 0;
    return '<tr>' +
      '<td><b>' + esc(catLabel) + '</b></td>' +
      '<td><b>' + (r.n || 0) + '</b></td>' +
      '<td>' + (r.open_n > 0 ? ('<span class="pill p-crit" style="font-size:11.5px">' + r.open_n + ' Open</span>') : '<span class="pill p-ok" style="font-size:11.5px">0</span>') + '</td>' +
      '<td>' +
        '<div style="display:flex;align-items:center;gap:8px">' +
          '<div style="flex:1;min-width:60px;height:8px;background:#F3F4F6;border-radius:4px;overflow:hidden">' +
            '<div style="width:' + pct + '%;height:100%;background:var(--pur);border-radius:4px"></div>' +
          '</div>' +
          '<span style="font-size:12px;font-weight:700;color:var(--ink);width:40px;text-align:right">' + pct + '%</span>' +
        '</div>' +
      '</td>' +
    '</tr>';
  }).join('');
}

function renderDashDistrictTable(distRows) {
  if (!distRows || !distRows.length) return '<tr><td colspan="7" style="text-align:center;color:var(--ink2);padding:20px">No district records</td></tr>';

  return distRows.map(function (d) {
    var breachBadge = d.breaches > 0 ?
      ('<span class="pill p-crit" style="font-size:11.5px">' + d.breaches + ' Breached</span>') :
      ('<span class="pill p-ok" style="font-size:11.5px">0 Breaches</span>');

    return '<tr class="dash-district-tr" data-dist="' + esc(d.district).toLowerCase() + '">' +
      '<td><a href="javascript:void(0)" onclick="viewDistrictTickets(\'' + esc(d.district) + '\')" style="font-weight:700;color:var(--pur);text-decoration:none" title="View all tickets in ' + esc(d.district) + '">' + esc(d.district) + '</a></td>' +
      '<td><b>' + d.total + '</b></td>' +
      '<td>' + (d.open > 0 ? ('<span class="pill p-open" style="font-size:11.5px">' + d.open + '</span>') : '0') + '</td>' +
      '<td>' + (d.resolved > 0 ? ('<span class="pill p-ok" style="font-size:11.5px">' + d.resolved + '</span>') : '0') + '</td>' +
      '<td>' + (d.pending > 0 ? ('<span class="pill p-warn" style="font-size:11.5px">' + d.pending + '</span>') : '0') + '</td>' +
      '<td>' + breachBadge + '</td>' +
      '<td>' +
        '<div style="display:flex;gap:6px;align-items:center">' +
          '<button class="btn sm" onclick="viewDistrictTickets(\'' + esc(d.district) + '\')" title="View ' + esc(d.district) + ' tickets in Queue" style="white-space:nowrap;padding:4px 10px;font-size:11.5px">View Tickets</button>' +
          '<button class="btn sm o" onclick="filterDashByDistrict(\'' + esc(d.district) + '\')" title="Filter dashboard view to ' + esc(d.district) + '" style="white-space:nowrap;padding:4px 8px;font-size:11.5px">Filter Dash</button>' +
        '</div>' +
      '</td>' +
    '</tr>';
  }).join('');
}

function filterDashDistrictTable(query) {
  var q = (query || '').toLowerCase().trim();
  var rows = document.querySelectorAll('.dash-district-tr');
  rows.forEach(function (r) {
    var name = r.getAttribute('data-dist') || '';
    r.style.display = (!q || name.indexOf(q) !== -1) ? '' : 'none';
  });
}

function viewDistrictTickets(distName) {
  TAB = 'queue';
  FILT.status = '';
  FILT.scope = '';
  FILT.mmu_vehicle = '';
  FILT.district = (distName === 'Unassigned District') ? 'Unassigned' : distName;
  FILT.district_id = '';
  FILT.q = '';
  FILT.priority = '';
  FILT.category = '';
  FILT.date_from = DASH_FILT.date_from || '';
  FILT.date_to = DASH_FILT.date_to || '';
  FILT.page_size = 50;
  FILT.page = 1;
  saveState();
  render();
  load(true);
}

function filterDashByDistrict(distName) {
  var dVal = (distName === 'Unassigned District') ? '__unassigned__' : distName;
  DASH_FILT.district = dVal;
  var sel = document.getElementById('dash_dist');
  if (sel) {
    var found = false;
    for (var i = 0; i < sel.options.length; i++) {
      if (sel.options[i].value.toLowerCase() === dVal.toLowerCase()) {
        sel.selectedIndex = i;
        found = true;
        break;
      }
    }
    if (!found && dVal) {
      var opt = document.createElement('option');
      opt.value = dVal;
      opt.textContent = distName;
      opt.selected = true;
      sel.appendChild(opt);
    }
  }
  applyDashFilters();
}

function setDashActivityFilter(filterType) {
  window.DASH_ACTIVITY_FILTER = filterType;
  var el = document.getElementById('dash_activity_feed_container');
  if (el && DASH) el.innerHTML = renderDashActivitiesContent(DASH.recent_activities || [], filterType);
  var chips = document.querySelectorAll('.dash-activity-chip');
  chips.forEach(function (c) {
    c.classList.toggle('active', c.getAttribute('data-filter') === filterType);
  });
}

function renderDashActivitiesContent(acts, filterType) {
  if (!acts || !acts.length) return '<div class="muted" style="padding:24px;text-align:center">No recent activities logged</div>';

  var filtered = acts.filter(function (a) {
    if (filterType === 'all') return true;
    var act = (a.action || '').toUpperCase();
    var pri = (a.priority || '').toUpperCase();
    if (filterType === 'p1_p2') return pri === 'P1' || pri === 'P2';
    if (filterType === 'breach') return act.indexOf('BREACH') !== -1;
    if (filterType === 'escalate') return act.indexOf('ESCALAT') !== -1;
    if (filterType === 'resolved') return act.indexOf('RESOLV') !== -1 || act.indexOf('CONFIRM') !== -1;
    if (filterType === 'status') return act.indexOf('STATUS') !== -1 || act === 'ASSIGNED' || act === 'CREATED';
    return true;
  });

  if (!filtered.length) {
    return '<div class="muted" style="padding:24px;text-align:center">No events match filter "' + esc(filterType) + '"</div>';
  }

  return filtered.map(function (a) {
    var act = (a.action || '').toUpperCase();
    var badgeClass = 'badge-info';
    var badgeLabel = a.action || 'EVENT';

    if (act.indexOf('BREACH') !== -1) { badgeClass = 'badge-crit'; badgeLabel = 'SLA BREACH'; }
    else if (act.indexOf('ESCALAT') !== -1) { badgeClass = 'badge-esc'; badgeLabel = 'ESCALATED'; }
    else if (act.indexOf('RESOLV') !== -1 || act.indexOf('CONFIRM') !== -1) { badgeClass = 'badge-ok'; badgeLabel = 'RESOLVED'; }
    else if (act === 'CREATED' || act === 'NEW') { badgeClass = 'badge-new'; badgeLabel = 'NEW TICKET'; }
    else if (act === 'ASSIGNED') { badgeClass = 'badge-warn'; badgeLabel = 'ASSIGNED'; }

    var timeStr = a.at ? (formatDT(a.at) || a.at) : '';

    return '<div class="dash-activity-item">' +
      '<span class="dash-activity-badge ' + badgeClass + '">' + esc(badgeLabel) + '</span>' +
      '<div class="dash-activity-content">' +
        '<div class="dash-activity-title">' +
          '<div>' +
            '<a class="dash-activity-tlink" onclick="openT(' + a.ticket_id + ')" title="Open ticket details">' + esc(a.ticket_no) + '</a> ' +
            (a.priority ? ('<span class="pill ' + (a.priority === 'P1' ? 'p-crit' : 'p-warn') + '" style="font-size:11px;padding:1px 6px;margin-left:4px">' + esc(a.priority) + '</span>') : '') +
            (a.district ? (' <span class="muted" style="font-size:12px">&middot; ' + esc(a.district) + '</span>') : '') +
            (a.mmu_vehicle ? (' <span class="muted" style="font-size:12px">(' + esc(a.mmu_vehicle) + ')</span>') : '') +
          '</div>' +
          '<div class="dash-activity-time">' + esc(timeStr) + '</div>' +
        '</div>' +
        '<div style="color:var(--ink);margin-top:3px">' + esc(a.detail || '') + '</div>' +
        '<div style="font-size:11.5px;color:var(--ink2);margin-top:4px">' +
          'Actor: <b>' + esc(a.actor || 'System') + '</b>' + (a.actor_role ? (' (' + esc(a.actor_role) + ')') : '') +
        '</div>' +
      '</div>' +
    '</div>';
  }).join('');
}

function viewDash() {
  if (!DASH) return '<div class="card"><div class="empty">Loading daily monitoring…</div></div>';
  var t = DASH.today || {}, k = DASH.kpi || {}, kc = DASH.kpi_cards || {};

  var timeOptions = [
    { id: '', label: 'Today (Default)' },
    { id: 'today', label: 'Today' },
    { id: 'yesterday', label: 'Yesterday' },
    { id: '24h', label: 'Last 24 Hours' },
    { id: '7d', label: 'Last 7 Days' },
    { id: '30d', label: 'Last 30 Days' },
    { id: 'custom', label: 'Custom Date Range...' }
  ];

  var timeSelectHtml = timeOptions.map(function (o) {
    return '<option value="' + o.id + '"' + (DASH_FILT.date_preset === o.id ? ' selected' : '') + '>' + esc(o.label) + '</option>';
  }).join('');

  var distSelectHtml = '<option value="">All Districts (Statewide)</option>' +
    ((META && META.districts) || []).map(function (d) {
      return '<option value="' + esc(d.name) + '"' + (DASH_FILT.district === d.name ? ' selected' : '') + '>' + esc(d.name) + '</option>';
    }).join('');

  var teamSelectHtml = '<option value="">All Departments</option>' +
    Object.keys((META && META.teams) || {}).map(function (k) {
      return '<option value="' + esc(k) + '"' + (DASH_FILT.team === k ? ' selected' : '') + '>' + esc(META.teams[k]) + '</option>';
    }).join('');

  var hasActiveFilters = !!(DASH_FILT.district || DASH_FILT.team || DASH_FILT.mmu_vehicle || (DASH_FILT.date_preset && DASH_FILT.date_preset !== 'today') || DASH_FILT.date_from);

  var emptyFilterNoticeHtml = '';
  var hasDateFilter = !!(DASH_FILT.date_from || DASH_FILT.date_to || (DASH_FILT.date_preset && DASH_FILT.date_preset !== 'all' && DASH_FILT.date_preset !== ''));
  var isZeroTotal = (kc.total_tickets === 0 || (kc.total_tickets == null && t.tickets === 0));
  if (hasDateFilter && isZeroTotal) {
    var rangeDesc = (DASH_FILT.date_from && DASH_FILT.date_to) ? (esc(DASH_FILT.date_from) + ' to ' + esc(DASH_FILT.date_to)) : (esc(DASH_FILT.date_preset || 'selected range'));
    emptyFilterNoticeHtml = '<div style="background:#FFFBEB;border:1px solid #FDE68A;color:#92400E;padding:12px 18px;border-radius:10px;margin-bottom:18px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px">' +
      '<div style="display:flex;align-items:center;gap:10px">' +
        '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>' +
        '<span style="font-size:13px"><strong>No tickets found for selected dates: ' + rangeDesc + '</strong> (Department: <strong>' + esc(DASH_FILT.team || 'All Departments') + '</strong>). The logged tickets in the system are between <strong>25 Aug 2026</strong> and <strong>07 Sep 2026</strong>.</span>' +
      '</div>' +
      '<div style="display:flex;gap:8px">' +
        '<button type="button" class="qf-btn qf-btn-primary" style="height:32px;padding:0 14px;font-size:12px" onclick="onDashTimePresetChange(\'30d\')">View Last 30 Days</button>' +
        '<button type="button" class="qf-btn qf-btn-outline" style="height:32px;padding:0 12px;font-size:12px" onclick="clearDashFilters()">Reset All Filters</button>' +
      '</div>' +
    '</div>';
  }

  var attn = function (n, l, c, onclick) {
    return '<button class="c" onclick="' + onclick + '">' +
      '<div class="n" style="color:' + c + '">' + esc(n == null ? 0 : n) + '</div>' +
      '<div class="l">' + esc(l) + '</div>' +
    '</button>';
  };

  var tbl = function (title, rows, cols) {
    var body = (rows && rows.length) ?
      rows.map(function (r) {
        return '<tr>' + cols.map(function (c) {
          var v = c[1](r);
          return '<td>' + (c[2] ? v : esc(v)) + '</td>';
        }).join('') + '</tr>';
      }).join('') :
      '<tr><td colspan="' + cols.length + '" style="text-align:center;color:var(--ink2);padding:24px 12px">No ticket records logged for this filter selection</td></tr>';

    return '<div class="card" style="margin-bottom:14px"><h4 style="margin-bottom:10px;font-size:14px">' + esc(title) + '</h4>' +
      '<table><thead><tr>' + cols.map(function (c) { return '<th>' + esc(c[0]) + '</th>'; }).join('') + '</tr></thead><tbody>' +
      body +
      '</tbody></table></div>';
  };

  // Section A: 12 Dashboard KPI Cards
  var kpi12Html = '<div class="dash-kpi-grid">' +
    '<div class="dash-kpi-card" onclick="attnGoto(\'all\',\'\',\'\')" style="cursor:pointer" title="View all tickets">' +
      '<div class="dash-num" style="color:#4F46E5">' + (kc.total_tickets != null ? kc.total_tickets : 0) + '</div>' +
      '<div class="dash-lbl">1. Total Tickets</div>' +
    '</div>' +
    '<div class="dash-kpi-card" onclick="attnGoto(\'open\',\'\',\'\')" style="cursor:pointer" title="View new & intake tickets">' +
      '<div class="dash-num" style="color:#2563EB">' + (kc.new_tickets != null ? kc.new_tickets : 0) + '</div>' +
      '<div class="dash-lbl">2. New Tickets</div>' +
    '</div>' +
    '<div class="dash-kpi-card" onclick="attnGoto(\'open\',\'\',\'\')" style="cursor:pointer" title="View in progress tickets">' +
      '<div class="dash-num" style="color:#0284C7">' + (kc.in_progress != null ? kc.in_progress : 0) + '</div>' +
      '<div class="dash-lbl">3. In Progress</div>' +
    '</div>' +
    '<div class="dash-kpi-card" onclick="attnGoto(\'PENDING\',\'\',\'\')" style="cursor:pointer" title="View pending tickets">' +
      '<div class="dash-num" style="color:#D97706">' + (kc.pending_tickets != null ? kc.pending_tickets : 0) + '</div>' +
      '<div class="dash-lbl">4. Pending Tickets</div>' +
    '</div>' +
    '<div class="dash-kpi-card" onclick="attnGoto(\'RESOLVED\',\'\',\'\')" style="cursor:pointer" title="View resolved tickets">' +
      '<div class="dash-num" style="color:#059669">' + (kc.resolved_tickets != null ? kc.resolved_tickets : 0) + '</div>' +
      '<div class="dash-lbl">5. Resolved Tickets</div>' +
    '</div>' +
    '<div class="dash-kpi-card" onclick="attnGoto(\'CLOSED\',\'\',\'\')" style="cursor:pointer" title="View closed tickets">' +
      '<div class="dash-num" style="color:#10B981">' + (kc.closed_tickets != null ? kc.closed_tickets : 0) + '</div>' +
      '<div class="dash-lbl">6. Closed Tickets</div>' +
    '</div>' +
    '<div class="dash-kpi-card" onclick="attnGoto(\'open\',\'\',\'P1\')" style="cursor:pointer" title="View P1 Critical tickets">' +
      '<div class="dash-num" style="color:#DC2626">' + (kc.p1_critical != null ? kc.p1_critical : 0) + '</div>' +
      '<div class="dash-lbl">7. P1 – Critical Tickets</div>' +
    '</div>' +
    '<div class="dash-kpi-card" onclick="attnGoto(\'open\',\'\',\'P2\')" style="cursor:pointer" title="View P2 High Priority tickets">' +
      '<div class="dash-num" style="color:#EA580C">' + (kc.p2_high != null ? kc.p2_high : 0) + '</div>' +
      '<div class="dash-lbl">8. P2 – High Priority Tickets</div>' +
    '</div>' +
    '<div class="dash-kpi-card" onclick="attnGoto(\'open\',\'risk\',\'\')" style="cursor:pointer" title="View SLA At Risk tickets">' +
      '<div class="dash-num" style="color:#B45309">' + (kc.sla_at_risk != null ? kc.sla_at_risk : 0) + '</div>' +
      '<div class="dash-lbl">9. SLA at Risk</div>' +
    '</div>' +
    '<div class="dash-kpi-card" onclick="attnGoto(\'open\',\'breach\',\'\')" style="cursor:pointer" title="View SLA Breaches">' +
      '<div class="dash-num" style="color:#B91C1C">' + (kc.sla_breaches != null ? kc.sla_breaches : 0) + '</div>' +
      '<div class="dash-lbl">10. SLA Breaches</div>' +
    '</div>' +
    '<div class="dash-kpi-card" onclick="attnGoto(\'open\',\'escalated\',\'\')" style="cursor:pointer" title="View Escalated tickets">' +
      '<div class="dash-num" style="color:#C026D3">' + (kc.escalated_tickets != null ? kc.escalated_tickets : 0) + '</div>' +
      '<div class="dash-lbl">11. Escalated Tickets</div>' +
    '</div>' +
    '<div class="dash-kpi-card" title="Overall SLA Compliance rate">' +
      '<div class="dash-num" style="color:#059669">' + (kc.sla_compliance_pct != null ? kc.sla_compliance_pct : 100) + '%</div>' +
      '<div class="dash-lbl">12. SLA Compliance (%)</div>' +
    '</div>' +
  '</div>';

  var now = new Date();
  var defaultTo = formatISODate(now);
  var d30 = new Date(now.getTime() - 30 * 24 * 3600 * 1000);
  var defaultFrom = formatISODate(d30);
  var activeFrom = DASH_FILT.date_from || defaultFrom;
  var activeTo = DASH_FILT.date_to || defaultTo;

  // Section B & C: Trend Analysis + Priority Donut Chart
  var trendAndDonutHtml = '<div class="grid2" style="margin-bottom:20px">' +
    '<div class="dash-card">' +
      '<div class="dash-card-header">' +
        '<div>' +
          '<div class="dash-card-title">Ticket-Wise Trend Analysis</div>' +
          '<div class="dash-card-subtitle">Volume of tickets created vs resolved over time</div>' +
        '</div>' +
        '<div class="dash-switcher">' +
          '<button type="button" class="dash-switcher-btn dash-trend-btn ' + (window.DASH_TREND_VIEW === 'week' ? 'active' : '') + '" data-mode="week" onclick="setDashTrendView(\'week\')">Week</button>' +
          '<button type="button" class="dash-switcher-btn dash-trend-btn ' + (window.DASH_TREND_VIEW === 'month' ? 'active' : '') + '" data-mode="month" onclick="setDashTrendView(\'month\')">Month</button>' +
          '<button type="button" class="dash-switcher-btn dash-trend-btn ' + (window.DASH_TREND_VIEW === 'custom' ? 'active' : '') + '" data-mode="custom" onclick="setDashTrendView(\'custom\')">Custom Date Range</button>' +
        '</div>' +
      '</div>' +
      '<div id="dash_trend_custom_bar" class="dash-card-custom-dates-bar" style="display:' + (window.DASH_TREND_VIEW === 'custom' ? 'flex' : 'none') + '">' +
        '<div class="dash-custom-bar-inner">' +
          '<span class="dash-custom-bar-label">' +
            '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:4px"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>' +
            'Custom Date Range:' +
          '</span>' +
          '<div class="dash-inline-date-group">' +
            '<label class="dash-inline-date-lbl">From</label>' +
            '<div class="dash-date-input-wrap">' +
              '<input id="trend_date_from" type="date" class="qf-input dash-calendar-input" value="' + esc(activeFrom) + '" onclick="openCalendarPicker(\'trend_date_from\')" onchange="onTrendDateChange()">' +
              '<button type="button" class="dash-calendar-btn" onclick="openCalendarPicker(\'trend_date_from\')" title="Select Date From Calendar">' +
                '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>' +
              '</button>' +
            '</div>' +
          '</div>' +
          '<div class="dash-inline-date-group">' +
            '<label class="dash-inline-date-lbl">To</label>' +
            '<div class="dash-date-input-wrap">' +
              '<input id="trend_date_to" type="date" class="qf-input dash-calendar-input" value="' + esc(activeTo) + '" onclick="openCalendarPicker(\'trend_date_to\')" onchange="onTrendDateChange()">' +
              '<button type="button" class="dash-calendar-btn" onclick="openCalendarPicker(\'trend_date_to\')" title="Select Date To Calendar">' +
                '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>' +
              '</button>' +
            '</div>' +
          '</div>' +
          '<button type="button" class="qf-btn qf-btn-primary" style="height:32px;padding:0 14px;font-size:12px;border-radius:6px" onclick="applyTrendCustomDates()">Apply Range</button>' +
        '</div>' +
      '</div>' +
      '<div id="dash_trend_chart_container">' + renderDashTrendChartContent(DASH.trend || [], window.DASH_TREND_VIEW) + '</div>' +
    '</div>' +
    '<div class="dash-card">' +
      '<div class="dash-card-header">' +
        '<div>' +
          '<div class="dash-card-title">Priority Distribution</div>' +
          '<div class="dash-card-subtitle">Ticket distribution by priority (Count &amp; %)</div>' +
        '</div>' +
      '</div>' +
      renderDashDonutChart(DASH.priority_distribution || []) +
    '</div>' +
  '</div>';

  // Section D & E: Ticket Ageing + Application / Role-Wise Tickets
  var ageingAndAppRoleHtml = '<div class="grid2" style="margin-bottom:20px">' +
    '<div class="dash-card">' +
      '<div class="dash-card-header">' +
        '<div>' +
          '<div class="dash-card-title">Ticket Ageing</div>' +
          '<div class="dash-card-subtitle">Number of tickets pending based on ageing period</div>' +
        '</div>' +
        '<div class="dash-switcher">' +
          '<button type="button" class="dash-switcher-btn dash-ageing-btn ' + (window.DASH_AGEING_VIEW === 'week' ? 'active' : '') + '" data-mode="week" onclick="setDashAgeingView(\'week\')">Week</button>' +
          '<button type="button" class="dash-switcher-btn dash-ageing-btn ' + (window.DASH_AGEING_VIEW === 'month' ? 'active' : '') + '" data-mode="month" onclick="setDashAgeingView(\'month\')">Month</button>' +
          '<button type="button" class="dash-switcher-btn dash-ageing-btn ' + (window.DASH_AGEING_VIEW === 'custom' ? 'active' : '') + '" data-mode="custom" onclick="setDashAgeingView(\'custom\')">Custom Date Range</button>' +
        '</div>' +
      '</div>' +
      '<div id="dash_ageing_custom_bar" class="dash-card-custom-dates-bar" style="display:' + (window.DASH_AGEING_VIEW === 'custom' ? 'flex' : 'none') + '">' +
        '<div class="dash-custom-bar-inner">' +
          '<span class="dash-custom-bar-label">' +
            '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:4px"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>' +
            'Custom Date Range:' +
          '</span>' +
          '<div class="dash-inline-date-group">' +
            '<label class="dash-inline-date-lbl">From</label>' +
            '<div class="dash-date-input-wrap">' +
              '<input id="ageing_date_from" type="date" class="qf-input dash-calendar-input" value="' + esc(activeFrom) + '" onclick="openCalendarPicker(\'ageing_date_from\')">' +
              '<button type="button" class="dash-calendar-btn" onclick="openCalendarPicker(\'ageing_date_from\')" title="Select Date From Calendar">' +
                '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>' +
              '</button>' +
            '</div>' +
          '</div>' +
          '<div class="dash-inline-date-group">' +
            '<label class="dash-inline-date-lbl">To</label>' +
            '<div class="dash-date-input-wrap">' +
              '<input id="ageing_date_to" type="date" class="qf-input dash-calendar-input" value="' + esc(activeTo) + '" onclick="openCalendarPicker(\'ageing_date_to\')">' +
              '<button type="button" class="dash-calendar-btn" onclick="openCalendarPicker(\'ageing_date_to\')" title="Select Date To Calendar">' +
                '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>' +
              '</button>' +
            '</div>' +
          '</div>' +
          '<button type="button" class="qf-btn qf-btn-primary" style="height:32px;padding:0 14px;font-size:12px;border-radius:6px" onclick="applyAgeingCustomDates()">Apply Range</button>' +
        '</div>' +
      '</div>' +
      renderDashAgeing(DASH.ticket_ageing || []) +
    '</div>' +
    '<div class="dash-card">' +
      '<div class="dash-card-header">' +
        '<div>' +
          '<div class="dash-card-title">Application / Role-Wise Tickets</div>' +
          '<div class="dash-card-subtitle">Ticket distribution by application intake and user roles</div>' +
        '</div>' +
        '<div class="dash-switcher">' +
          '<button type="button" id="dash_app_btn" class="dash-switcher-btn ' + (window.DASH_APPROLE_VIEW === 'app' ? 'active' : '') + '" onclick="setDashAppRoleView(\'app\')">Application</button>' +
          '<button type="button" id="dash_role_btn" class="dash-switcher-btn ' + (window.DASH_APPROLE_VIEW === 'role' ? 'active' : '') + '" onclick="setDashAppRoleView(\'role\')">User Role</button>' +
        '</div>' +
      '</div>' +
      '<div id="dash_approle_container">' + renderDashAppRoleContent(DASH, window.DASH_APPROLE_VIEW) + '</div>' +
    '</div>' +
  '</div>';

  // Section F & G: Category-Wise Tickets & District-Wise Tickets
  var catAndDistHtml = '<div class="grid2" style="margin-bottom:20px">' +
    '<div class="dash-card">' +
      '<div class="dash-card-header">' +
        '<div>' +
          '<div class="dash-card-title">Category-Wise Tickets</div>' +
          '<div class="dash-card-subtitle">Ticket distribution by category (Count &amp; %)</div>' +
        '</div>' +
      '</div>' +
      '<div style="overflow-x:auto"><table>' +
        '<thead><tr><th>Category</th><th>Total Tickets</th><th>Open</th><th>Percentage (%)</th></tr></thead>' +
        '<tbody>' + renderDashCategory(DASH.by_category || []) + '</tbody>' +
      '</table></div>' +
    '</div>' +
    '<div class="dash-card">' +
      '<div class="dash-card-header">' +
        '<div>' +
          '<div class="dash-card-title">District-Wise Tickets</div>' +
          '<div class="dash-card-subtitle">Statewide MMU surveillance across districts</div>' +
        '</div>' +
        '<div><input type="text" class="qf-input" style="height:32px;font-size:12px;width:160px;padding:0 8px" placeholder="Search district…" oninput="filterDashDistrictTable(this.value)"></div>' +
      '</div>' +
      '<div style="overflow-x:auto;max-height:360px"><table>' +
        '<thead><tr><th>District Name</th><th>Total Tickets</th><th>Open</th><th>Resolved</th><th>Pending</th><th>SLA Breaches</th><th>Action</th></tr></thead>' +
        '<tbody id="dash_district_tbody">' + renderDashDistrictTable(DASH.by_district || []) + '</tbody>' +
      '</table></div>' +
    '</div>' +
  '</div>';

  // Section H: Live Alerts & Recent Activities
  var liveActivitiesHtml = '<div class="dash-card" style="margin-bottom:20px">' +
    '<div class="dash-card-header">' +
      '<div>' +
        '<div class="dash-card-title">' +
          '<span>Live Alerts &amp; Recent Activities</span>' +
          '<span style="display:inline-flex;align-items:center;gap:4px;font-size:11px;font-weight:700;color:#059669;background:#ECFDF5;border:1px solid #A7F3D0;padding:2px 8px;border-radius:12px"><span style="width:6px;height:6px;border-radius:50%;background:#10B981"></span> Live Feed</span>' +
        '</div>' +
        '<div class="dash-card-subtitle">Real-time alerts, critical priority updates, SLA warnings, escalations, assignments, and ticket status changes</div>' +
      '</div>' +
    '</div>' +
    '<div class="dash-activity-chips">' +
      '<button type="button" class="dash-activity-chip ' + (window.DASH_ACTIVITY_FILTER === 'all' ? 'active' : '') + '" data-filter="all" onclick="setDashActivityFilter(\'all\')">All Activities</button>' +
      '<button type="button" class="dash-activity-chip ' + (window.DASH_ACTIVITY_FILTER === 'p1_p2' ? 'active' : '') + '" data-filter="p1_p2" onclick="setDashActivityFilter(\'p1_p2\')">P1/P2 Critical &amp; High</button>' +
      '<button type="button" class="dash-activity-chip ' + (window.DASH_ACTIVITY_FILTER === 'breach' ? 'active' : '') + '" data-filter="breach" onclick="setDashActivityFilter(\'breach\')">SLA Breaches</button>' +
      '<button type="button" class="dash-activity-chip ' + (window.DASH_ACTIVITY_FILTER === 'escalate' ? 'active' : '') + '" data-filter="escalate" onclick="setDashActivityFilter(\'escalate\')">Escalations</button>' +
      '<button type="button" class="dash-activity-chip ' + (window.DASH_ACTIVITY_FILTER === 'resolved' ? 'active' : '') + '" data-filter="resolved" onclick="setDashActivityFilter(\'resolved\')">Resolutions</button>' +
      '<button type="button" class="dash-activity-chip ' + (window.DASH_ACTIVITY_FILTER === 'status' ? 'active' : '') + '" data-filter="status" onclick="setDashActivityFilter(\'status\')">Status Changes</button>' +
    '</div>' +
    '<div id="dash_activity_feed_container" class="dash-activity-feed">' +
      renderDashActivitiesContent(DASH.recent_activities || [], window.DASH_ACTIVITY_FILTER) +
    '</div>' +
  '</div>';

  return '<div class="card" style="margin-bottom:20px;padding:16px 20px;border-radius:12px;background:#fff;border:1px solid #E5E7EB;box-shadow:0 1px 3px rgba(0,0,0,0.04)">' +
    '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;padding-bottom:10px;border-bottom:1px solid #F3F4F6;flex-wrap:wrap;gap:10px">' +
      '<div style="font-size:15px;font-weight:700;color:var(--ink);display:flex;align-items:center;gap:8px">' +
        '<span>Daily Monitoring &amp; Operational Surveillance</span>' +
        '<span style="display:inline-flex;align-items:center;gap:5px;font-size:11px;font-weight:700;color:#059669;background:#ECFDF5;border:1px solid #A7F3D0;padding:2px 8px;border-radius:12px"><span style="width:6px;height:6px;border-radius:50%;background:#10B981"></span> Live</span>' +
        (hasActiveFilters ? '<span style="font-size:11px;color:var(--pur);background:#F5F3FF;border:1px solid #DDD6FE;padding:2px 8px;border-radius:12px;font-weight:600">Active Filters</span>' : '') +
      '</div>' +
      '<div style="display:flex;align-items:center;gap:8px">' +
        '<button class="qf-btn qf-btn-export" onclick="exportDash()" title="Export filtered dashboard summary report to Excel" style="height:34px;padding:0 14px;font-size:12.5px">' +
          '<span style="margin-right:6px"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg></span> Export Summary (Excel)' +
        '</button>' +
      '</div>' +
    '</div>' +

    '<div class="qf-grid">' +
      '<div class="qf-fld" style="flex:1.1;min-width:160px">' +
        '<label class="qf-label">Time Window</label>' +
        '<select id="dash_time" class="qf-select" onchange="onDashTimePresetChange(this.value)">' +
          timeSelectHtml +
        '</select>' +
      '</div>' +

      '<div class="qf-fld" style="flex:1.2;min-width:170px">' +
        '<label class="qf-label">District</label>' +
        '<select id="dash_dist" class="qf-select" onchange="applyDashFilters()">' +
          distSelectHtml +
        '</select>' +
      '</div>' +

      '<div class="qf-fld" style="flex:1.2;min-width:170px">' +
        '<label class="qf-label">Department</label>' +
        '<select id="dash_team" class="qf-select" onchange="applyDashFilters()">' +
          teamSelectHtml +
        '</select>' +
      '</div>' +

      '<div class="qf-fld" style="flex:1;min-width:140px">' +
        '<label class="qf-label">MMU / Vehicle</label>' +
        '<input id="dash_veh" class="qf-input" type="text" placeholder="e.g. APFE2929" value="' + esc(DASH_FILT.mmu_vehicle || '') + '" onkeydown="if(event.key===\'Enter\')applyDashFilters()">' +
      '</div>' +

      '<div class="qf-fld" style="flex:0 0 auto">' +
        '<label class="qf-label" style="visibility:hidden">Actions</label>' +
        '<div style="display:flex;gap:8px;align-items:center">' +
          '<button class="qf-btn qf-btn-primary" onclick="applyDashFilters()" style="height:38px;padding:0 18px">Filter</button>' +
          '<button class="qf-btn qf-btn-outline" onclick="clearDashFilters()" style="height:38px;padding:0 14px" title="Reset all dashboard filters">Reset</button>' +
        '</div>' +
      '</div>' +
    '</div>' +

    '<div id="dash_custom_dates" class="dash-custom-dates-bar" style="display:' + ((DASH_FILT.date_preset === 'custom' || (DASH_FILT.date_from && !DASH_FILT.date_preset)) ? 'flex' : 'none') + ';gap:14px;margin-top:14px;padding-top:14px;border-top:1px solid #F3F4F6;align-items:flex-end;flex-wrap:wrap">' +
      '<div class="qf-fld" style="flex:1;min-width:160px;max-width:240px">' +
        '<label class="qf-label">Date From (Calendar)</label>' +
        '<div class="dash-date-input-wrap">' +
          '<input id="dash_from" class="qf-input dash-calendar-input" type="date" value="' + esc(DASH_FILT.date_from || '') + '" onclick="openCalendarPicker(\'dash_from\')">' +
          '<button type="button" class="dash-calendar-btn" onclick="openCalendarPicker(\'dash_from\')" title="Select Date From Calendar"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg></button>' +
        '</div>' +
      '</div>' +
      '<div class="qf-fld" style="flex:1;min-width:160px;max-width:240px">' +
        '<label class="qf-label">Date To (Calendar)</label>' +
        '<div class="dash-date-input-wrap">' +
          '<input id="dash_to" class="qf-input dash-calendar-input" type="date" value="' + esc(DASH_FILT.date_to || '') + '" onclick="openCalendarPicker(\'dash_to\')">' +
          '<button type="button" class="dash-calendar-btn" onclick="openCalendarPicker(\'dash_to\')" title="Select Date To Calendar"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg></button>' +
        '</div>' +
      '</div>' +
      '<button class="qf-btn qf-btn-primary" onclick="applyDashFilters()" style="height:36px;padding:0 18px;margin-bottom:2px">Apply Dates</button>' +
    '</div>' +
  '</div>' +
  emptyFilterNoticeHtml +

  // Attention Required Grid
  '<div style="display:flex;align-items:center;justify-content:space-between;margin:20px 0 12px 2px">' +
    '<div style="font-size:15px;font-weight:700;color:var(--ink);display:flex;align-items:center;gap:6px">Attention Required</div>' +
    '<span style="font-size:11px;font-weight:700;color:var(--ink3);letter-spacing:0.04em;text-transform:uppercase">Click card to view queue</span>' +
  '</div>' +

  '<div class="attn">' +
    attn(t.p1_open, 'P1 open', "var(--crit)", "attnGoto('open','','P1')") +
    attn(t.breached, 'TAT breached', "var(--crit)", "attnGoto('open','breach','')") +
    attn(t.critical, 'Critical (<15m)', "#a3300c", "attnGoto('open','critical','')") +
    attn(t.at_risk, 'At risk (<60m)', "var(--warn)", "attnGoto('open','risk','')") +
    attn(t.pending, 'Pending', "var(--org)", "attnGoto('PENDING','','')") +
    attn(t.awaiting_confirmation, 'Awaiting MMU confirmation', "var(--pur)", "attnGoto('RESOLVED','','')") +
    attn(t.escalated, 'Escalated', "var(--mag)", "attnGoto('open','escalated','')") +
    attn(t.escalated_from_field, 'Escalated from field', "var(--mag)", "attnGoto('open','escalated','')") +
    attn(t.unassigned, 'Unassigned', "var(--org)", "attnGoto('open','unassigned','')") +
  '</div>' +

  // Section A: 12 KPI Cards
  '<div style="display:flex;align-items:center;justify-content:space-between;margin:24px 0 12px 2px">' +
    '<div style="font-size:15px;font-weight:700;color:var(--ink);display:flex;align-items:center;gap:6px">Dashboard KPI Cards</div>' +
    '<span style="font-size:11px;font-weight:700;color:var(--ink3);letter-spacing:0.04em;text-transform:uppercase">Operational benchmarks</span>' +
  '</div>' +
  kpi12Html +

  // Section B & C: Trend Analysis + Priority Donut Chart
  trendAndDonutHtml +

  // Section D & E: Ticket Ageing + Application / Role-Wise Tickets
  ageingAndAppRoleHtml +

  // Section F & G: Category-Wise Tickets & District-Wise Tickets
  catAndDistHtml +

  // Section H: Live Alerts & Recent Activities
  liveActivitiesHtml +

  // Chronic Equipment Watchdog
  (DASH.chronic_equipment && DASH.chronic_equipment.length ?
    ('<div class="card" style="margin-bottom:20px;border-left:4px solid #DC2626">' +
      '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;flex-wrap:wrap;gap:8px">' +
        '<div><div style="font-weight:800;font-size:15px;color:#991B1B">Chronic Failing Units Watchdog (≥ 3 Breakdowns in 30 Days)</div>' +
        '<div class="muted" style="font-size:12px;margin-top:2px">Identifies high-failure analyzers and MMUs requiring manufacturer warranty replacement / root-cause overhaul.</div></div>' +
        '<div class="pill-chronic" style="padding:4px 10px;font-size:12px">' + DASH.chronic_equipment.length + ' Chronic Unit' + (DASH.chronic_equipment.length === 1 ? '' : 's') + ' Flagged</div>' +
      '</div>' +
      '<div style="overflow-x:auto"><table><thead><tr><th>MMU Vehicle</th><th>District</th><th>Breakdowns (30d)</th><th>Open Status</th><th>Failing Issue Types</th><th>Last Breakdown</th><th>Action</th></tr></thead><tbody>' +
      DASH.chronic_equipment.map(function (c) {
        return '<tr>' +
          '<td><b>' + esc(c.mmu_vehicle) + '</b></td>' +
          '<td>' + esc(c.district || '—') + '</td>' +
          '<td><span class="pill-chronic">' + esc(c.n) + ' times</span></td>' +
          '<td>' + (c.open_n > 0 ? ('<span class="pill p-crit">' + c.open_n + ' Open</span>') : '<span class="pill p-ok">Resolved</span>') + '</td>' +
          '<td>' + esc((c.categories || '').split(',').map(function (cat) { return (META.routing[cat] || {}).label || cat; }).join(', ')) + '</td>' +
          '<td>' + esc(c.last_breakdown_at || '—') + '</td>' +
          '<td><button class="btn sm" onclick="viewVehicleTickets(\'' + esc(c.mmu_vehicle) + '\')">View Tickets</button></td>' +
        '</tr>';
      }).join('') +
      '</tbody></table></div></div>') : '') +

  // Other Departmental Tables
  '<div class="grid2">' +
    tbl('Tickets by responsible team', DASH.by_team, [['Team', function (r) { return META.teams[r.team] || r.team; }], ['Total', function (r) { return r.n; }], ['Open', function (r) { return r.open_n; }], ['Breached', function (r) { return r.breach_n; }]]) +
    tbl('By status', DASH.by_status, [['Status', function (r) { return (r.status || '').replace(/_/g, ' '); }], ['Count', function (r) { return r.n; }]]) +
    tbl('Repeat issues by MMU', DASH.repeat_vehicles, [
      ['MMU / Vehicle', function (r) { return '<a href="javascript:void(0)" onclick="viewVehicleTickets(\'' + esc(r.mmu_vehicle) + '\')" style="color:var(--pur);font-weight:700;text-decoration:underline">' + esc(r.mmu_vehicle) + '</a>'; }, true],
      ['Tickets', function (r) { return r.n; }],
      ['Action', function (r) { return '<button class="btn sm o" onclick="viewVehicleTickets(\'' + esc(r.mmu_vehicle) + '\')">View All</button>'; }, true]
    ]) +
    tbl('Daily volume (14 days)', DASH.daily, [['Date', function (r) { return r.d; }], ['Created', function (r) { return r.n; }], ['Closed', function (r) { return r.closed_n; }]]) +
  '</div>';
}

/* ---------- routing matrix ---------- */
function viewMatrix() {
  var rows = Object.keys(META.routing).map(function (k) {
    var r = META.routing[k];
    return '<tr><td><b>' + esc(r.label) + '</b></td><td>' + esc(META.teams[r.team]) + '</td><td>' + esc(r.owner) + '</td></tr>';
  }).join('');
  return '<div class="card" style="margin-bottom:14px"><h4 style="margin-bottom:4px;font-size:15px">Issue routing matrix</h4>' +
    '<div class="muted" style="margin-bottom:12px">SOP §5 — every classified issue routes to one responsible team with a named initial owner.</div>' +
    '<table><thead><tr><th>Issue type</th><th>Responsible team</th><th>Initial owner</th></tr></thead><tbody>' + rows + '</tbody></table></div>' +
    '<div class="card" style="margin-bottom:14px"><h4 style="margin-bottom:4px;font-size:15px">Emergency Response SLA &amp; TAT Monitoring</h4>' +
    '<div class="muted" style="margin-bottom:14px">SOP §8 — All 104 Emergency &amp; MMU issues operate under top-priority emergency dispatch with automated time-to-breach surveillance.</div>' +
    '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin-bottom:16px">' +
      '<div style="background:#F0FDF4;border:1.5px solid #BBF7D0;border-radius:10px;padding:14px">' +
        '<div style="font-size:11.5px;font-weight:700;color:#166534;text-transform:uppercase;letter-spacing:0.04em">Standard Emergency TAT</div>' +
        '<div style="font-size:22px;font-weight:800;color:#15803D;margin:6px 0">240 min <span style="font-size:13px;font-weight:600">(4 Hours)</span></div>' +
        '<div style="font-size:12px;color:#166534;line-height:1.4">Direct dispatch to local district engineer upon call intake</div>' +
      '</div>' +
      '<div style="background:#FEF3C7;border:1.5px solid #FDE68A;border-radius:10px;padding:14px">' +
        '<div style="font-size:11.5px;font-weight:700;color:#92400E;text-transform:uppercase;letter-spacing:0.04em">At-Risk Warning (SLA)</div>' +
        '<div style="font-size:22px;font-weight:800;color:#B45309;margin:6px 0">&le; 60 min</div>' +
        '<div style="font-size:12px;color:#92400E;line-height:1.4">Amber alert triggered; supervisory review initiated</div>' +
      '</div>' +
      '<div style="background:#FFF1F2;border:1.5px solid #FECDD3;border-radius:10px;padding:14px">' +
        '<div style="font-size:11.5px;font-weight:700;color:#9F1239;text-transform:uppercase;letter-spacing:0.04em">Critical Escalation</div>' +
        '<div style="font-size:22px;font-weight:800;color:#BE123C;margin:6px 0">&le; 15 min</div>' +
        '<div style="font-size:12px;color:#9F1239;line-height:1.4">Urgent escalation dispatched to Global Team Executive</div>' +
      '</div>' +
    '</div>' +
    '<table><thead><tr><th>Emergency Stage</th><th>Protocol &amp; Action Trigger</th><th>Countdown Target</th></tr></thead><tbody>' +
      '<tr><td><span class="pill p-ok">ON TRACK</span></td><td>Standard field diagnostic &amp; engineering repair workflow</td><td><b>&gt; 60 min remaining</b></td></tr>' +
      '<tr><td><span class="pill p-warn">AT RISK</span></td><td>Automated supervisory notification to District Team Lead</td><td><b>&le; 60 min remaining</b></td></tr>' +
      '<tr><td><span class="pill p-critical">CRITICAL</span></td><td>High-priority alert to Statewide Department Executive</td><td><b>&le; 15 min remaining</b></td></tr>' +
      '<tr><td><span class="pill p-crit">BREACHED</span></td><td>Statewide Command Center non-compliance escalation flag</td><td><b>Elapsed &gt; 240 min</b></td></tr>' +
    '</tbody></table></div>' +
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

// ==================== OFFLINE RESILIENCE & COMPRESSION ENGINE ====================

function compressImage(file, maxDim, quality, callback) {
  if (!file || !file.type.match(/image.*/)) {
    return callback(file, null);
  }
  var reader = new FileReader();
  reader.onload = function (e) {
    var img = new Image();
    img.onload = function () {
      var canvas = document.createElement('canvas');
      var w = img.width, h = img.height;
      if (w > h) {
        if (w > maxDim) { h = Math.round((h * maxDim) / w); w = maxDim; }
      } else {
        if (h > maxDim) { w = Math.round((w * maxDim) / h); h = maxDim; }
      }
      canvas.width = w;
      canvas.height = h;
      var ctx = canvas.getContext('2d');
      ctx.drawImage(img, 0, 0, w, h);
      var dataUrl = canvas.toDataURL('image/jpeg', quality || 0.75);
      canvas.toBlob(function (blob) {
        var compFile = new File([blob], file.name.replace(/\.[^/.]+$/, "") + ".jpg", {
          type: "image/jpeg",
          lastModified: Date.now()
        });
        callback(compFile, dataUrl);
      }, 'image/jpeg', quality || 0.75);
    };
    img.src = e.target.result;
  };
  reader.readAsDataURL(file);
}

function dataUrlToBlob(dataurl) {
  try {
    var arr = dataurl.split(','), mime = arr[0].match(/:(.*?);/)[1],
        bstr = atob(arr[1]), n = bstr.length, u8arr = new Uint8Array(n);
    while (n--) { u8arr[n] = bstr.charCodeAt(n); }
    return new Blob([u8arr], { type: mime });
  } catch (e) { return null; }
}

function getLTOutbox() {
  try { return JSON.parse(localStorage.getItem('ccc_lt_outbox') || '[]'); } catch (e) { return []; }
}
function saveLTOutbox(items) {
  localStorage.setItem('ccc_lt_outbox', JSON.stringify(items));
}
function enqueueLTOutbox(item) {
  var list = getLTOutbox();
  item.outbox_id = 'OB-' + Date.now();
  item.queued_at = new Date().toLocaleString();
  list.push(item);
  saveLTOutbox(list);
}
function removeLTOutboxItem(outboxId) {
  var list = getLTOutbox().filter(function (x) { return x.outbox_id !== outboxId; });
  saveLTOutbox(list);
}

var SYNCING_OUTBOX = false;
function syncLTOutbox(manual) {
  if (SYNCING_OUTBOX) return;
  var list = getLTOutbox();
  if (!list.length) {
    if (manual) toast('Outbox is empty — all reports are synced');
    return;
  }
  if (!navigator.onLine) {
    if (manual) toast('Offline / No cellular signal. Will auto-sync when network returns.');
    return;
  }
  SYNCING_OUTBOX = true;
  var item = list[0];
  var fd = new FormData();
  fd.append('category', item.category);
  fd.append('reason_codes', JSON.stringify(item.reason_codes));
  if (item.machine_id) fd.append('machine_id', item.machine_id);
  fd.append('priority', item.priority);
  fd.append('problem', item.problem || '');
  if (item.photos && item.photos.length) {
    item.photos.forEach(function (p) {
      var blob = dataUrlToBlob(p.dataUrl || p.data_url);
      if (blob) fd.append('photos', blob, p.name || 'field_photo.jpg');
    });
  } else if (item.photo_data_url) {
    var blob = dataUrlToBlob(item.photo_data_url);
    if (blob) fd.append('photo', blob, item.photo_name || 'field_photo.jpg');
  }

  apiForm('/lt/tickets', fd).then(function (d) {
    removeLTOutboxItem(item.outbox_id);
    SYNCING_OUTBOX = false;
    playAlertSound('new');
    toast('Outbox Ticket ' + d.ticket_no + ' synced successfully!');
    if (TAB === 'mine') loadLTMine();
    else render();
    if (getLTOutbox().length > 0) {
      setTimeout(function () { syncLTOutbox(false); }, 600);
    }
  }).catch(function (e) {
    SYNCING_OUTBOX = false;
    if (manual) toast('Sync failed: ' + (typeof e === 'string' ? e : 'Network unreachable'));
  });
}

function saveLTFormDraft() {
  if (!ME || ME.role !== 'LT') return;
  var draft = {
    category: document.getElementById('lt_cat') ? document.getElementById('lt_cat').value : '',
    reasons: LT_SELECTED_REASONS,
    machine: document.getElementById('lt_machine') ? document.getElementById('lt_machine').value : '',
    machine_id: document.getElementById('lt_machine_id') ? document.getElementById('lt_machine_id').value : '',
    notes: document.getElementById('lt_notes') ? document.getElementById('lt_notes').value : ''
  };
  localStorage.setItem('ccc_lt_draft_' + ME.username, JSON.stringify(draft));
}

function clearLTFormDraft() {
  if (ME) localStorage.removeItem('ccc_lt_draft_' + ME.username);
}

function restoreLTFormDraft() {
  if (!ME || ME.role !== 'LT') return;
  try {
    var raw = localStorage.getItem('ccc_lt_draft_' + ME.username);
    if (!raw) return;
    var draft = JSON.parse(raw);
    if (draft.category && document.getElementById('lt_cat')) {
      document.getElementById('lt_cat').value = draft.category;
      ltCategoryChanged(function () {
        LT_SELECTED_REASONS = draft.reasons || [];
        var cbs = document.querySelectorAll('#lt_reasons_box input[type="checkbox"]');
        cbs.forEach(function (cb) {
          if (LT_SELECTED_REASONS.indexOf(cb.value) >= 0) cb.checked = true;
        });
      });
    }
    if (draft.machine && document.getElementById('lt_machine')) document.getElementById('lt_machine').value = draft.machine;
    if (draft.machine_id && document.getElementById('lt_machine_id')) document.getElementById('lt_machine_id').value = draft.machine_id;
    if (draft.notes && document.getElementById('lt_notes')) document.getElementById('lt_notes').value = draft.notes;
  } catch (e) {}
}

window._LT_PHOTOS = [];

function ltPhotoPreview() {
  var inp = document.getElementById('lt_photo');
  if (!inp || !inp.files || !inp.files.length) return;
  var prev = document.getElementById('lt_photo_prev');
  if (!prev) return;

  var newFiles = Array.from(inp.files);
  if (!window._LT_PHOTOS) window._LT_PHOTOS = [];

  var statusMsg = document.createElement('div');
  statusMsg.className = 'muted';
  statusMsg.style.marginTop = '6px';
  statusMsg.id = 'lt_compress_status';
  statusMsg.textContent = 'Optimizing ' + newFiles.length + ' photo(s) for mobile upload…';
  prev.appendChild(statusMsg);

  var completed = 0;
  newFiles.forEach(function (f) {
    compressImage(f, 1280, 0.75, function (compFile, dataUrl) {
      var sizeKb = Math.round(compFile.size / 1024);
      window._LT_PHOTOS.push({
        file: compFile,
        dataUrl: dataUrl,
        name: f.name,
        sizeKb: sizeKb
      });
      completed++;
      if (completed === newFiles.length) {
        renderLTPhotosPreview();
      }
    });
  });
  inp.value = '';
}

function removeLTPhoto(idx) {
  if (!window._LT_PHOTOS) return;
  window._LT_PHOTOS.splice(idx, 1);
  renderLTPhotosPreview();
}

function renderLTPhotosPreview() {
  var prev = document.getElementById('lt_photo_prev');
  if (!prev) return;
  if (!window._LT_PHOTOS || !window._LT_PHOTOS.length) {
    prev.innerHTML = '';
    return;
  }
  var html = '';
  window._LT_PHOTOS.forEach(function (p, idx) {
    html += '<div class="photo-thumb-card">' +
      '<img src="' + p.dataUrl + '" alt="Photo preview">' +
      '<button type="button" class="photo-remove-btn" title="Remove image" onclick="removeLTPhoto(' + idx + ')">×</button>' +
      '<div class="photo-size">' + p.sizeKb + ' KB</div>' +
    '</div>';
  });
  prev.innerHTML = html;
}

function viewLTReport() {
  var outboxCount = getLTOutbox().length;
  var outboxBanner = outboxCount > 0 ? (
    '<div class="offline-alert-box">' +
      '<div class="offline-alert-text"><b>' + outboxCount + ' Outbox Report' + (outboxCount > 1 ? 's' : '') + ' Pending Sync</b><br>Saved safely offline. Will auto-upload when signal returns.</div>' +
      '<button class="btn o sm" onclick="syncLTOutbox(true)">Sync Now</button>' +
    '</div>'
  ) : '';

  setTimeout(restoreLTFormDraft, 50);

  return outboxBanner +
    '<div class="card"><h3 style="margin-bottom:4px">Report an Issue</h3>' +
    '<div class="muted" style="margin-bottom:16px">Tell us what\'s wrong — automatically routes to your district\'s support team. (Works online &amp; offline)</div>' +
    '<div class="fld"><label>What kind of issue? *</label><select id="lt_cat" onchange="ltCategoryChanged(); saveLTFormDraft();"><option value="">Loading…</option></select></div>' +
    '<div class="fld"><label>What\'s wrong? (select all that apply) *</label><div id="lt_reasons_box" class="ltreasons"><div class="muted">Select an issue type first</div></div></div>' +
    '<div class="fld"><label>Machine (optional)</label><input id="lt_machine" list="lt_machineDL" placeholder="Start typing the machine name…" oninput="ltMachineSearchInput(); saveLTFormDraft();" autocomplete="off"><datalist id="lt_machineDL"></datalist><input type="hidden" id="lt_machine_id"></div>' +
    '<div class="fld"><label>Add photos / evidence (auto-compressed for rural network) (optional)</label><input type="file" id="lt_photo" accept="image/*" multiple onchange="ltPhotoPreview()"><div id="lt_photo_prev" class="photo-gallery"></div></div>' +
    '<div class="fld"><label>Anything else? (optional)</label><textarea id="lt_notes" rows="3" placeholder="Extra details, if any" oninput="saveLTFormDraft()"></textarea></div>' +
    '<div style="display:flex;gap:10px;margin-top:14px">' +
      '<button class="btn" style="min-width:180px" onclick="submitLTTicket()">Submit report</button>' +
    '</div>' +
    '</div>';
}

function apiForm(p, fd) {
  var h = {}; if (TOK) h.Authorization = 'Bearer ' + TOK;
  return fetch(API + p, { method: 'POST', headers: h, body: fd }).then(function (r) {
    if (r.status === 401) { logout(); throw 'auth'; }
    return r.json().then(function (d) { if (!r.ok) throw (d.detail || ('HTTP ' + r.status)); return d; });
  });
}

function submitLTTicket() {
  var cat = gv('lt_cat') || (document.getElementById('lt_cat') ? document.getElementById('lt_cat').value : '');
  if (!cat) return toast('Select an issue type');
  if (!LT_SELECTED_REASONS.length) return toast('Select at least one reason');
  
  var mid = gv('lt_machine_id');
  var pri = 'P1';
  var problem = gv('lt_notes');
  var photos = (window._LT_PHOTOS && window._LT_PHOTOS.length) ? window._LT_PHOTOS : [];

  // If strictly offline, queue immediately without waiting for timeout
  if (!navigator.onLine) {
    var outboxPhotos = photos.map(function (p) {
      return { dataUrl: p.dataUrl, name: p.name || 'field_photo.jpg' };
    });
    enqueueLTOutbox({
      category: cat,
      reason_codes: LT_SELECTED_REASONS,
      machine_id: mid || null,
      priority: pri,
      problem: problem,
      photos: outboxPhotos
    });
    clearLTFormDraft();
    window._LT_PHOTOS = [];
    toast('Offline: Saved to Outbox! Will auto-upload when signal returns.');
    TAB = 'mine'; render(); load();
    return;
  }

  // Attempt live upload
  var fd = new FormData();
  fd.append('category', cat);
  fd.append('reason_codes', JSON.stringify(LT_SELECTED_REASONS));
  if (mid) fd.append('machine_id', mid);
  fd.append('priority', pri);
  fd.append('problem', problem);
  photos.forEach(function (p) {
    fd.append('photos', p.file, p.name || 'field_photo.jpg');
  });

  toast('Uploading report…');
  apiForm('/lt/tickets', fd).then(function (d) {
    clearLTFormDraft();
    window._LT_PHOTOS = [];
    toast('Reported! Ticket ' + d.ticket_no + ' sent to district team');
    TAB = 'mine'; render(); load();
  }).catch(function (e) {
    // On network failure or drop, save to outbox so nothing is lost
    var outboxPhotos = photos.map(function (p) {
      return { dataUrl: p.dataUrl, name: p.name || 'field_photo.jpg' };
    });
    enqueueLTOutbox({
      category: cat,
      reason_codes: LT_SELECTED_REASONS,
      machine_id: mid || null,
      priority: pri,
      problem: problem,
      photos: outboxPhotos
    });
    clearLTFormDraft();
    window._LT_PHOTOS = [];
    toast('Network dropped during upload. Saved to Outbox for auto-sync!');
    TAB = 'mine'; render(); load();
  });
}

function loadLTMine() {
  syncLTOutbox(false);
  api('GET', '/lt/tickets').then(function (rows) { LT_TICKETS = rows; render(); }).catch(function () { render(); });
}

function viewLTMine() {
  var outbox = getLTOutbox();
  var outboxHtml = '';
  if (outbox.length > 0) {
    outboxHtml = '<div style="margin-bottom:18px">' +
      '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">' +
        '<h4 style="margin:0;font-size:15px;color:#92400E">Offline Outbox (' + outbox.length + ' Pending Sync)</h4>' +
        '<button class="btn o sm" onclick="syncLTOutbox(true)">Sync All Outbox</button>' +
      '</div>' +
      outbox.map(function (item) {
        var photoPrev = item.photo_data_url ? ('<img src="' + item.photo_data_url + '" style="max-width:120px;max-height:120px;border-radius:8px;margin-top:8px;object-fit:cover">') : '';
        return '<div class="outbox-card">' +
          '<div class="outbox-card-header">' +
            '<div><b>' + esc(item.category) + ' Issue</b> · <span class="muted">' + esc(item.queued_at) + '</span></div>' +
            '<span class="outbox-badge">Queued for Upload</span>' +
          '</div>' +
          '<div><b>Reasons:</b> ' + esc((item.reason_codes || []).join(', ')) + '</div>' +
          (item.problem ? ('<div style="margin-top:6px">' + esc(item.problem) + '</div>') : '') +
          photoPrev +
          '<div style="display:flex;gap:8px;margin-top:10px">' +
            '<button class="btn sm" onclick="syncLTOutbox(true)">Upload Now</button>' +
            '<button class="btn o sm" onclick="removeLTOutboxItem(\'' + item.outbox_id + '\'); render();">Discard</button>' +
          '</div>' +
        '</div>';
      }).join('') +
    '</div>';
  }

  if (!LT_TICKETS.length && !outbox.length) {
    return '<div class="card"><div class="empty">You haven\'t reported anything yet.</div></div>';
  }

  var ticketsHtml = LT_TICKETS.map(function (t) {
    var photo = t.photo_path ? ('<img src="/uploads/' + esc(t.photo_path) + '" style="max-width:140px;max-height:140px;border-radius:10px;margin-top:10px;object-fit:cover">') : '';
    var actions = '';
    var statusBadge = statusPill(t.status);
    var confirmedNote = '';

    if (t.status === 'RESOLVED') {
      actions = '<div style="background:#F0FDF4;border:1.5px solid #86EFAC;border-radius:10px;padding:12px 14px;margin-top:12px">' +
        '<div style="font-size:13px;font-weight:700;color:#166534;margin-bottom:8px">Support team / CDA has marked this issue as resolved. Please verify:</div>' +
        '<div style="display:flex;gap:10px;flex-wrap:wrap">' +
          '<button class="btn g sm" onclick="ltConfirmFixed(' + t.id + ')">Confirmed — It\'s Fixed</button>' +
          '<button class="btn r sm" onclick="openLTNotResolvedModal(' + t.id + ',\'' + esc(t.ticket_no) + '\')">Not Resolved</button>' +
        '</div>' +
      '</div>';
    } else if (t.status === 'CLOSURE_CONFIRMATION') {
      statusBadge = '<span class="pill p-ok">CONFIRMED BY YOU</span>';
      confirmedNote = '<div style="margin-top:8px;font-size:12.5px;color:var(--ok);font-weight:600;display:flex;align-items:center;gap:6px">' +
        '<span>Resolution confirmed by you</span>' +
        (t.confirmed_at ? ('<span class="muted" style="font-weight:normal">&middot; ' + formatDT(t.confirmed_at) + '</span>') : '') +
        '<span class="muted" style="font-weight:normal">(Awaiting final closure by Command Center)</span>' +
      '</div>';
    } else if (t.status === 'CLOSED') {
      actions = '<button class="btn o sm" onclick="ltReopenSame(' + t.id + ')">Reopen — broke again</button>';
    }

    return '<div class="card" style="margin-bottom:12px">' +
      '<div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px">' +
      '<div><b>' + esc(t.ticket_no) + '</b><div class="muted">' + esc(t.category_label || '') + (t.created_at ? (' &middot; <span style="font-weight:600;color:var(--ink)">Raised: ' + formatDT(t.created_at) + '</span>') : '') + '</div></div>' +
      '<div style="text-align:right">' + statusBadge + ' ' + tatPill(t) + '</div></div>' +
      '<div style="margin-top:8px">' + esc(t.problem || '') + '</div>' +
      (t.resolution ? ('<div class="muted" style="margin-top:8px"><b>Resolution:</b> ' + esc(t.resolution) + '</div>') : '') +
      confirmedNote +
      photo + (actions ? ('<div style="margin-top:12px">' + actions + '</div>') : '') + '</div>';
  }).join('');

  return outboxHtml + ticketsHtml;
}

function openLTNotResolvedModal(id, ticketNo) {
  document.getElementById('modal').innerHTML = '<div class="ovl" onclick="if(event.target===this)closeModal()"><div class="sheet" style="max-width:540px">' +
    '<div class="sh" style="background:#dc2626;color:#fff"><div><div style="font-size:17px;font-weight:800">Issue Still Not Resolved</div>' +
    '<div style="font-size:12.5px;opacity:.9;margin-top:2px">Ticket: <b>' + esc(ticketNo) + '</b> &middot; Returning to Support Team</div></div>' +
    '<button class="x" onclick="closeModal()">&times;</button></div>' +
    '<div class="sb">' +
      '<p style="margin:0 0 14px;color:#4b5563;font-size:13.5px;line-height:1.5">Please specify what is still not working or why this problem is not resolved. The ticket will be returned immediately to the assigned team and CDA as <b>In Progress</b> for further investigation.</p>' +
      '<div class="fld">' +
        '<label style="font-weight:700">Reason / Observations (Required) *</label>' +
        '<textarea id="lt_nr_reason" rows="4" placeholder="Describe in detail what is still failing or not working..." style="width:100%;box-sizing:border-box"></textarea>' +
      '</div>' +
      '<div style="display:flex;justify-content:flex-end;gap:10px;margin-top:16px;border-top:1px solid var(--line);padding-top:14px">' +
        '<button class="btn o" onclick="closeModal()">Cancel</button>' +
        '<button class="btn r" onclick="submitLTNotResolved(' + id + ')">Send Back to Support Team</button>' +
      '</div>' +
    '</div></div></div>';
  setTimeout(function () {
    var el = document.getElementById('lt_nr_reason');
    if (el) el.focus();
  }, 50);
}

function submitLTNotResolved(id) {
  var reasonEl = document.getElementById('lt_nr_reason');
  var reason = reasonEl ? reasonEl.value.trim() : '';
  if (!reason) return toast('Please describe why the issue is not resolved');
  api('POST', '/ticket/action', { id: id, action: 'not_resolved', note: reason })
    .then(function () {
      toast('Ticket returned to support team as In Progress');
      closeModal();
      loadLTMine();
    })
    .catch(function (e) {
      toast(typeof e === 'string' ? e : 'Could not submit action');
    });
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
function goAdmin(t) { TAB = 'admin'; ADMIN_TAB = t; saveState(); render(); if (!ADMIN_LOADED[t]) loadAdminSection(t); }
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
  else if (t === 'vehicles') api('GET', '/admin/vehicles').then(function (d) { ADMIN_VEHICLES = d; ADMIN_LOADED.vehicles = true; if (ADMIN_TAB === 'vehicles') render(); });
  else if (t === 'tickettypes') loadAdminTicketTypes();
  else if (t === 'priorities') loadAdminPriorities();
  else if (t === 'slapolicies') loadAdminSlaPolicies();
  else if (t === 'calendars') loadAdminCalendars();
  else if (t === 'routingrules') loadAdminRoutingRules();
  else if (t === 'hierarchysource') loadAdminHierarchyConfig();
  else if (t === 'assignmentexceptions') loadAdminAssignmentExceptions();
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
    tickettypes: 'Ticket Types & Approval Rules',
    reasons: 'Sub-Categories (Incident / Request Reasons)',
    priorities: 'Priorities & Impact/Urgency Matrix',
    slapolicies: 'SLA Policies (Response & Resolution Targets)',
    calendars: 'Business Calendars & Holidays',
    routingrules: 'Routing Rules (L1-L4 Local Mapping)',
    hierarchysource: 'Hierarchy Source (Local vs External API)',
    assignmentexceptions: 'Assignment Exceptions',
    machines: 'Diagnostic Machines & Equipment',
    sla: 'SLA Priorities & TAT Benchmarks',
    users: 'System Users & Role Assignments',
    audit: 'System Administrator Audit Log'
  };
  var bar = '<div class="card" style="margin-bottom:14px;display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap">' +
    '<div><div style="font-size:16px;font-weight:800;color:var(--ink)">' + esc(labels[ADMIN_TAB] || 'Admin Portal') + '</div>' +
    '<div style="font-size:12.5px;color:var(--ink2);margin-top:2px">Manage global master data, mappings and access permissions</div></div>' +
    '<button class="btn o sm" onclick="loadAdminSection(ADMIN_TAB)">&#8635; Refresh Data</button></div>';
  var body = '';
  if (!ADMIN_LOADED[ADMIN_TAB]) body = '<div class="card"><div class="empty">Loading…</div></div>';
  else if (ADMIN_TAB === 'teams') body = viewAdminTeams();
  else if (ADMIN_TAB === 'categories') body = viewAdminCategories();
  else if (ADMIN_TAB === 'geo') body = viewAdminGeo();
  else if (ADMIN_TAB === 'vehicles') body = viewAdminVehicles();
  else if (ADMIN_TAB === 'tickettypes') body = viewAdminTicketTypes();
  else if (ADMIN_TAB === 'priorities') body = viewAdminPriorities();
  else if (ADMIN_TAB === 'slapolicies') body = viewAdminSlaPolicies();
  else if (ADMIN_TAB === 'calendars') body = viewAdminCalendars();
  else if (ADMIN_TAB === 'routingrules') body = viewAdminRoutingRules();
  else if (ADMIN_TAB === 'hierarchysource') body = viewAdminHierarchySource();
  else if (ADMIN_TAB === 'assignmentexceptions') body = viewAdminAssignmentExceptions();
  else if (ADMIN_TAB === 'reasons') body = viewAdminReasons();
  else if (ADMIN_TAB === 'machines') body = viewAdminMachines();
  else if (ADMIN_TAB === 'sla') body = viewAdminSla();
  else if (ADMIN_TAB === 'users') { body = viewAdminUsers(); setTimeout(function () { syncDynamicUserForm('au'); }, 10); }
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
  var name = prompt('New name for ' + code + ':'); if (!name) return;
  api('PUT', '/admin/teams/' + code, { name: name }).then(function () { toast('Renamed'); loadAdminSection('teams'); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
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
  var label = prompt('Label:', c.label); if (label === null) return;
  var owner = prompt('Default owner:', c.default_owner || ''); if (owner === null) return;
  api('PUT', '/admin/categories/' + code, { label: label, default_owner: owner }).then(function () { toast('Updated'); loadAdminSection('categories'); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
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
      '<td><button class="btn ' + (z.is_active ? 'r' : 'g') + ' sm" onclick="adminToggleZone(' + z.id + ',' + (!z.is_active) + ')">' + (z.is_active ? 'Deactivate' : 'Activate') + '</button></td></tr>';
  }).join('');
  var districtOpts = ADMIN_DISTRICTS.filter(function (d) { return d.is_active; }).map(function (d) { return '<option value="' + d.id + '">' + esc(d.name) + '</option>'; }).join('');
  var zoneOpts = '<option value="">No zone (category-default routing)</option>' + ADMIN_ZONES.filter(function (z) { return z.is_active; }).map(function (z) { return '<option value="' + z.id + '">' + esc(z.name) + '</option>'; }).join('');
  var mandalRows = ADMIN_MANDALS.map(function (m) {
    var d = ADMIN_DISTRICTS.find(function (x) { return x.id === m.district_id; });
    var z = ADMIN_ZONES.find(function (x) { return x.id === m.zone_id; });
    return '<tr><td><b>' + esc(m.name) + '</b></td><td>' + esc(d ? d.name : m.district_id) + '</td><td>' + esc(z ? z.name : '—') + '</td>' +
      '<td>' + (m.is_active ? '<span class="pill p-ok">Active</span>' : '<span class="pill p-mut">Inactive</span>') + '</td>' +
      '<td><button class="btn ' + (m.is_active ? 'r' : 'g') + ' sm" onclick="adminToggleMandal(' + m.id + ',' + (!m.is_active) + ')">' + (m.is_active ? 'Deactivate' : 'Activate') + '</button></td></tr>';
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
  var name = prompt('New name:'); if (!name) return;
  api('PUT', '/admin/districts/' + id, { name: name }).then(function () { toast('Renamed'); loadAdminSection('geo'); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
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

function viewAdminVehicles() {
  var rows = ADMIN_VEHICLES.map(function (v) {
    return '<tr><td><b>' + esc(v.registration_no) + '</b></td>' +
      '<td><span class="pill ' + (v.vehicle_type === 'AMBULANCE' ? 'p-crit' : 'p-mut') + '">' + esc(v.vehicle_type || 'MMU') + '</span></td>' +
      '<td>' + (v.is_active ? '<span class="pill p-ok">Active</span>' : '<span class="pill p-mut">Inactive</span>') + '</td>' +
      '<td><button class="btn ' + (v.is_active ? 'r' : 'g') + ' sm" onclick="adminToggleVehicle(' + v.id + ',' + (!v.is_active) + ')">' + (v.is_active ? 'Deactivate' : 'Activate') + '</button></td></tr>';
  }).join('');
  return '<div class="card" style="margin-bottom:14px"><h4 style="margin-bottom:4px;font-size:15px">Vehicles &amp; Ambulances</h4>' +
    '<div class="muted" style="margin-bottom:10px">Manage mobile healthcare units (MMU) and emergency ambulances (108).</div>' +
    '<div style="overflow-x:auto"><table><thead><tr><th>Registration no.</th><th>Type</th><th>Status</th><th></th></tr></thead><tbody>' + rows + '</tbody></table></div></div>' +
    '<div class="card"><h4 style="margin-bottom:10px;font-size:14px">Add vehicle / ambulance</h4><div class="grid3">' +
    '<div class="fld"><label>Registration number</label><input id="veh_reg" placeholder="AP39UL4276"></div>' +
    '<div class="fld"><label>Vehicle Type</label><select id="veh_type"><option value="MMU">MMU (Mobile Medical Unit)</option><option value="AMBULANCE">Ambulance (108 Emergency)</option></select></div>' +
    '<div class="fld" style="display:flex;align-items:flex-end"><button class="btn" onclick="adminCreateVehicle()">Add vehicle</button></div>' +
    '</div></div>';
}
function adminCreateVehicle() {
  var reg = gv('veh_reg'); if (!reg) return toast('Registration number is required');
  var vtype = document.getElementById('veh_type') ? document.getElementById('veh_type').value : 'MMU';
  api('POST', '/admin/vehicles', { registration_no: reg, vehicle_type: vtype }).then(function () { toast('Vehicle added'); loadAdminSection('vehicles'); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}
function adminToggleVehicle(id, active) {
  api('PUT', '/admin/vehicles/' + id, { is_active: active }).then(function () { toast(active ? 'Activated' : 'Deactivated'); loadAdminSection('vehicles'); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}

function viewAdminReasons() {
  var activeCats = ADMIN_CATEGORIES.filter(function (c) { return c.is_active; });
  var catOpts = activeCats.map(function (c) { return '<option value="' + c.code + '">' + esc(c.label) + '</option>'; }).join('');
  var catLabel = function (code) { var c = ADMIN_CATEGORIES.find(function (x) { return x.code === code; }); return c ? c.label : code; };
  var ttOpts = Object.keys(META.ticket_types || {}).map(function (k) { return '<option value="' + k + '">' + esc(META.ticket_types[k].label) + '</option>'; }).join('');
  var ttLabel = function (code) { return (META.ticket_types && META.ticket_types[code] && META.ticket_types[code].label) || code; };
  var rows = ADMIN_REASONS.map(function (r) {
    return '<tr><td><b>' + esc(r.code) + '</b></td><td>' + esc(r.label) + '</td><td>' + esc(catLabel(r.category_code)) + '</td>' +
      '<td>' + esc(ttLabel(r.ticket_type)) + '</td>' +
      '<td>' + (r.is_active ? '<span class="pill p-ok">Active</span>' : '<span class="pill p-mut">Inactive</span>') + '</td>' +
      '<td style="display:flex;gap:6px"><button class="btn o sm" onclick="adminRenameReason(\'' + r.code + '\')">Rename</button>' +
      '<button class="btn ' + (r.is_active ? 'r' : 'g') + ' sm" onclick="adminToggleReason(\'' + r.code + '\',' + (!r.is_active) + ')">' + (r.is_active ? 'Deactivate' : 'Activate') + '</button></td></tr>';
  }).join('');
  return '<div class="card" style="margin-bottom:14px"><h4 style="margin-bottom:10px;font-size:14px">Sub-Category Master</h4>' +
    '<div class="muted" style="margin-bottom:10px">Fault/request classifications under each Category, selectable from Register Call, the LT field portal, and /intake. (Table name in the API stays "reasons" for backward compatibility with the LT portal.)</div>' +
    '<div style="overflow-x:auto"><table><thead><tr><th>Code</th><th>Label</th><th>Category</th><th>Ticket Type</th><th>Status</th><th></th></tr></thead><tbody>' + rows + '</tbody></table></div></div>' +
    '<div class="card"><h4 style="margin-bottom:10px;font-size:14px">Add sub-category</h4>' +
    (activeCats.length ? ('<div class="grid3">' +
      '<div class="fld"><label>Code</label><input id="ar_code" placeholder="NO_POWER"></div>' +
      '<div class="fld"><label>Label</label><input id="ar_label" placeholder="No power / won\'t switch on"></div>' +
      '<div class="fld"><label>Category</label><select id="ar_category">' + catOpts + '</select></div>' +
      '<div class="fld"><label>Ticket Type</label><select id="ar_tt">' + ttOpts + '</select></div>' +
      '<div class="fld" style="display:flex;align-items:flex-end"><button class="btn" onclick="adminCreateReason()">Add sub-category</button></div>' +
      '</div>') : '<div class="muted">No active categories yet - add one on the Categories tab first.</div>') +
    '</div>';
}
function adminAddReason() {
  var b = { category: document.getElementById('ar_cat').value, reason: document.getElementById('ar_text').value, requires_resolution: document.getElementById('ar_req_res').checked };
  api('POST', '/admin/reasons', b).then(function () { toast('Reason added'); loadAdminSection('reasons'); }).catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}
function adminCreateReason() {
  var code = gv('ar_code'), label = gv('ar_label'), cat = document.getElementById('ar_category').value;
  var tt = document.getElementById('ar_tt') ? document.getElementById('ar_tt').value : 'INCIDENT';
  if (!code || !label) return toast('Code and label are required');
  api('POST', '/admin/reasons', { code: code, category_code: cat, label: label, ticket_type: tt }).then(function () { toast('Sub-category added'); loadAdminSection('reasons'); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}
function adminRenameReason(code) {
  var r = ADMIN_REASONS.find(function (x) { return x.code === code; });
  var label = prompt('New label:', r ? r.label : ''); if (!label) return;
  api('PUT', '/admin/reasons/' + code, { label: label }).then(function () { toast('Renamed'); loadAdminSection('reasons'); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
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
      '<td><span class="pill p-mut">' + esc(roleLabel(u.role)) + '</span></td>' +
      '<td>' + esc(u.hr_emp_code || '—') + '</td>' +
      '<td>' + esc(u.reporting_manager_id ? mgrName(u.reporting_manager_id) : '—') + '</td>' +
      '<td>' + (dispatchLabel ? ('<span class="pill p-ok">' + dispatchLabel + '</span>') : '<span class="muted">—</span>') + '</td>' +
      '<td>' + esc(loc) + '</td>' +
      '<td>' + (u.active ? '<span class="pill p-ok">Active</span>' : '<span class="pill p-mut">Inactive</span>') + '</td>' +
      '<td style="display:flex;gap:6px">' +
      '<button class="btn o sm" onclick="openEditUserModal(' + u.id + ')">Edit</button>' +
      '<button class="btn ' + (u.active ? 'r' : 'g') + ' sm" onclick="adminToggleUser(' + u.id + ',' + (!u.active) + ')">' + (u.active ? 'Deactivate' : 'Activate') + '</button>' +
      '</td></tr>';
  }).join('');
  var roleOpts = function (sel) { return ADMIN_ROLES.map(function (r) { return '<option value="' + r + '"' + (r === sel ? ' selected' : '') + '>' + esc(roleLabel(r)) + '</option>'; }).join(''); };
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
    '<div style="overflow-x:auto"><table><thead><tr><th>Username</th><th>Name</th><th>Role</th><th>HR code</th><th>Reports to</th><th>Dispatch / Lead</th><th>Location</th><th>Status</th><th>Actions</th></tr></thead><tbody>' + rows + '</tbody></table></div></div>' +
    '<div class="card"><h4 style="margin-bottom:6px;font-size:14px">Add New User</h4>' +
    '<div id="au_dynamic_badge" class="dynamic-role-card"></div>' +
    '<div class="grid3">' +
    '<div class="fld"><label>Username *</label><input id="au_uname" placeholder="e.g. tech6"></div>' +
    '<div class="fld"><label>Full Name *</label><input id="au_name" placeholder="Full name"></div>' +
    '<div class="fld"><label>Department / Role *</label><select id="au_new_role" onchange="syncDynamicUserForm(\'au\')">' + roleOpts() + '</select></div>' +
    '<div class="fld"><label>Phone / Contact</label><input id="au_phone" placeholder="10-digit mobile"></div>' +
    '<div class="fld"><label>Temporary Password *</label><input id="au_pw" type="password" placeholder="min 8 characters"></div>' +
    '<div class="fld"><label>HR Employee Code</label><input id="au_hr_code" placeholder="e.g. EMP1234"></div>' +
    '<div class="fld"><label>Reporting Manager</label><select id="au_report_to">' + mgrOpts + '</select></div>' +
    '</div>' +
    '<input type="hidden" id="au_is_manager" value="0">' +
    '<div class="leadership-group" id="au_leadership_group">' +
      '<div class="leadership-title">Leadership &amp; Dispatch Role (Team Executive vs Local Team Lead)</div>' +
      '<div class="leadership-options">' +
        '<label class="leadership-opt selected" id="au_opt_eng_label" onclick="setLeadershipMode(\'au\', \'eng\')">' +
          '<div><div class="leadership-opt-title">Field Engineer</div><div class="leadership-opt-sub">Standard technician for maintenance &amp; repairs</div></div>' +
          '<input type="radio" name="au_leadership_mode" id="au_mode_eng" value="eng" checked>' +
        '</label>' +
        '<label class="leadership-opt" id="au_opt_lead_label" onclick="setLeadershipMode(\'au\', \'lead\')">' +
          '<div><div class="leadership-opt-title">Local Team Lead</div><div class="leadership-opt-sub">District ground supervisor (Dispatches local MMU tickets)</div></div>' +
          '<input type="radio" name="au_leadership_mode" id="au_mode_lead" value="lead">' +
        '</label>' +
        '<label class="leadership-opt" id="au_opt_exec_label" onclick="setLeadershipMode(\'au\', \'exec\')">' +
          '<div><div class="leadership-opt-title">Team Executive</div><div class="leadership-opt-sub">Statewide department head (Oversees all 26 districts)</div></div>' +
          '<input type="radio" name="au_leadership_mode" id="au_mode_exec" value="exec">' +
        '</label>' +
      '</div>' +
    '</div>' +
    '<div id="au_location_section">' +
      '<div style="font-weight:700;font-size:13px;margin:12px 0 6px;color:var(--ink)" id="au_loc_title">Location &amp; District Assignment</div>' +
      '<div class="grid3">' +
      '<div class="fld" id="au_district_wrap"><label id="au_dist_label">District</label><select id="au_district" onchange="syncDynamicUserDistrict(\'au\')">' + distOpts + '</select></div>' +
      '<div class="fld" id="au_mandal_wrap"><label>Mandal (LT Only)</label><select id="au_mandal">' + mandOpts + '</select></div>' +
      '<div class="fld" id="au_vehicle_wrap"><label>Vehicle (LT Only)</label><select id="au_vehicle">' + vehOpts + '</select></div>' +
      '</div>' +
    '</div>' +
    '<div style="display:flex;justify-content:flex-end;margin-top:10px"><button class="btn" onclick="adminCreateUser()">Create User Account</button></div>' +
    '</div>';
}

function setLeadershipMode(prefix, mode) {
  var isMgrEl = document.getElementById(prefix + '_is_manager');
  var distEl = document.getElementById(prefix + '_district');
  
  if (isMgrEl) {
    if (isMgrEl.type === 'checkbox') isMgrEl.checked = (mode === 'exec' || mode === 'lead');
    else isMgrEl.value = (mode === 'exec' || mode === 'lead') ? '1' : '0';
  }
  if (mode === 'exec') {
    if (distEl) distEl.value = '';
  }
  
  var rEng = document.getElementById(prefix + '_mode_eng');
  var rLead = document.getElementById(prefix + '_mode_lead');
  var rExec = document.getElementById(prefix + '_mode_exec');
  if (rEng) rEng.checked = (mode === 'eng');
  if (rLead) rLead.checked = (mode === 'lead');
  if (rExec) rExec.checked = (mode === 'exec');

  var lEng = document.getElementById(prefix + '_opt_eng_label');
  var lLead = document.getElementById(prefix + '_opt_lead_label');
  var lExec = document.getElementById(prefix + '_opt_exec_label');
  if (lEng) lEng.classList.toggle('selected', mode === 'eng');
  if (lLead) lLead.classList.toggle('selected', mode === 'lead');
  if (lExec) lExec.classList.toggle('selected', mode === 'exec');

  syncDynamicUserForm(prefix);
}

function syncDynamicUserForm(prefix) {
  var roleEl = document.getElementById(prefix === 'au' ? 'au_new_role' : 'medit_role');
  var isMgrEl = document.getElementById(prefix + '_is_manager');
  var distEl = document.getElementById(prefix + '_district');
  var mandWrap = document.getElementById(prefix + '_mandal_wrap');
  var vehWrap = document.getElementById(prefix + '_vehicle_wrap');
  var distWrap = document.getElementById(prefix + '_district_wrap');
  var distLabel = document.getElementById(prefix + '_dist_label');
  var leadGroup = document.getElementById(prefix + '_leadership_group');
  var badgeEl = document.getElementById(prefix + '_dynamic_badge');

  if (!roleEl) return;
  var role = roleEl.value;
  var isMgr = isMgrEl ? (isMgrEl.type === 'checkbox' ? isMgrEl.checked : isMgrEl.value === '1') : false;
  var distId = distEl ? distEl.value : '';
  var distName = distId ? ((ADMIN_DISTRICTS.find(function (d) { return String(d.id) === String(distId); }) || {}).name || '') : '';
  var roleName = roleLabel(role);

  var isLT = (role === 'LT');
  var isOrgWide = (role === 'CC_MANAGER' || role === 'CALL_TAKER');

  // Leadership selector visibility
  if (leadGroup) {
    leadGroup.classList.toggle('hide', isOrgWide || isLT);
  }

  // 2. Location Fields visibility
  if (mandWrap) mandWrap.classList.toggle('hide', !isLT);
  if (vehWrap) vehWrap.classList.toggle('hide', !isLT);
  if (distWrap) distWrap.classList.toggle('hide', isOrgWide);

  // Dynamic label & helper for district
  if (distLabel) {
    if (isMgr && distId) distLabel.innerHTML = 'Assigned District (Supervised by this Lead) *';
    else if (isMgr) distLabel.innerHTML = 'Assigned District (Select for Local Lead, Leave Blank for Statewide)';
    else distLabel.innerHTML = 'District (Optional)';
  }

  // 3. Dynamic Computed Badge & Helper Banner
  if (badgeEl) {
    var cardClass = 'dynamic-role-card';
    var badgeHtml = '';
    var titleHtml = '';
    var descHtml = '';

    if (role === 'CC_MANAGER') {
      cardClass += ' global-exec';
      badgeHtml = '<span class="pill pill-global">Global Command Executive</span>';
      titleHtml = 'Global Command Center Administrator';
      descHtml = 'Has statewide supervisory access across all 26 districts, departments, Daily Monitoring KPI dashboard, and master settings.';
    } else if (role === 'CALL_TAKER') {
      cardClass += ' global-exec';
      badgeHtml = '<span class="pill pill-global">Central Call Taker</span>';
      titleHtml = '104 Inbound Breakdown Agent';
      descHtml = 'Handles incoming breakdown calls from MMU doctors and field staff, registering and auto-routing emergency tickets.';
    } else if (isLT) {
      cardClass += ' lt-tech';
      badgeHtml = '<span class="pill pill-eng">Field Lab Technician</span>';
      titleHtml = 'MMU Diagnostics Operator' + (distName ? (' (' + esc(distName) + ' District)') : '');
      descHtml = 'Operates mobile diagnostic analyzers. Setting District, Mandal, and MMU Vehicle pre-fills their self-service incident reporting portal.';
    } else {
      // Departmental Engineer / Team Lead / Team Executive
      if (isMgr) {
        if (distId) {
          cardClass += ' local-lead';
          badgeHtml = '<span class="pill pill-lead">Local Team Lead · ' + esc(distName) + '</span>';
          titleHtml = esc(distName) + ' District ' + esc(roleName) + ' Lead';
          descHtml = 'Ground supervisor for <b>' + esc(distName) + ' District</b>. Receives 80% SLA alerts for ' + esc(distName) + ' MMUs and coordinates local ' + esc(roleName) + ' engineers in this district.';
        } else {
          cardClass += ' statewide-exec';
          badgeHtml = '<span class="pill pill-exec">Statewide Team Executive</span>';
          titleHtml = 'Statewide ' + esc(roleName) + ' Executive';
          descHtml = 'Statewide Head overseeing the entire <b>' + esc(roleName) + ' department across all 26 districts</b> in Andhra Pradesh. Receives statewide 80% SLA warnings and delegates tickets statewide.';
        }
      } else {
        cardClass += ' standard-eng';
        if (distId) {
          badgeHtml = '<span class="pill pill-eng">Field Engineer · ' + esc(distName) + '</span>';
          titleHtml = esc(roleName) + ' (' + esc(distName) + ' District)';
          descHtml = 'Field technician assigned to resolve equipment and diagnostic issues in ' + esc(distName) + ' district.';
        } else {
          badgeHtml = '<span class="pill pill-eng">Statewide Field Engineer</span>';
          titleHtml = 'Statewide ' + esc(roleName);
          descHtml = 'Field engineer available for statewide assignment and mobile diagnostic support across Andhra Pradesh.';
        }
      }
    }

    badgeEl.className = cardClass;
    badgeEl.innerHTML = '<div class="dynamic-role-header"><div class="dynamic-role-title">' + titleHtml + '</div>' + badgeHtml + '</div>' +
      '<div class="dynamic-role-desc">' + descHtml + '</div>';
  }
}

function syncDynamicUserDistrict(prefix) {
  var distEl = document.getElementById(prefix + '_district');
  var msel = document.getElementById(prefix + '_mandal');
  var did = distEl ? distEl.value : '';
  if (msel) {
    var filtered = ADMIN_MANDALS.filter(function (m) {
      return m.is_active && (!did || m.district_id === +did);
    });
    msel.innerHTML = '<option value="">No mandal</option>' + filtered.map(function (m) {
      return '<option value="' + m.id + '">' + esc(m.name) + '</option>';
    }).join('');
  }
  
  // Auto-switch radio button to 'lead' if district is chosen while is_manager is true
  var isMgrEl = document.getElementById(prefix + '_is_manager');
  var isMgr = isMgrEl ? (isMgrEl.type === 'checkbox' ? isMgrEl.checked : isMgrEl.value === '1') : false;
  if (isMgr) {
    var targetMode = did ? 'lead' : 'exec';
    var rLead = document.getElementById(prefix + '_mode_lead');
    var rExec = document.getElementById(prefix + '_mode_exec');
    if (rLead) rLead.checked = (targetMode === 'lead');
    if (rExec) rExec.checked = (targetMode === 'exec');
    var lLead = document.getElementById(prefix + '_opt_lead_label');
    var lExec = document.getElementById(prefix + '_opt_exec_label');
    if (lLead) lLead.classList.toggle('selected', targetMode === 'lead');
    if (lExec) lExec.classList.toggle('selected', targetMode === 'exec');
  }

  syncDynamicUserForm(prefix);
}

function adminCreateUser() {
  var username = gv('au_uname'), name = gv('au_name'), role = document.getElementById('au_new_role').value, phone = gv('au_phone'), pw = gv('au_pw'),
    hrCode = gv('au_hr_code'), reportTo = document.getElementById('au_report_to').value,
    isManagerVal = document.getElementById('au_is_manager').value,
    isManager = isManagerVal === '1',
    districtId = document.getElementById('au_district').value, mandalId = document.getElementById('au_mandal').value, vehicleId = document.getElementById('au_vehicle').value;
  if (!username || !name || !pw) return toast('Username, name and password are required');
  api('POST', '/admin/users', {
    username: username, name: name, role: role, phone: phone, password: pw,
    hr_emp_code: hrCode, reporting_manager_id: reportTo ? +reportTo : null, is_team_manager: isManager,
    district_id: districtId ? +districtId : null, mandal_id: mandalId ? +mandalId : null, vehicle_id: vehicleId ? +vehicleId : null
  })
    .then(function () { toast('User created successfully'); ADMIN_LOADED.users = false; loadAdminSection('users'); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
}

function openEditUserModal(id) {
  var u = ADMIN_USERS.find(function (x) { return x.id === id; });
  if (!u) return toast('User not found');

  var currentMode = u.is_team_manager ? (u.district_id ? 'lead' : 'exec') : 'eng';

  var roleOpts = ADMIN_ROLES.map(function (r) {
    return '<option value="' + r + '"' + (r === u.role ? ' selected' : '') + '>' + esc(roleLabel(r)) + '</option>';
  }).join('');

  var mgrOpts = '<option value="">No reporting manager</option>' + ADMIN_USERS.filter(function (x) {
    return x.active && x.id !== u.id;
  }).map(function (x) {
    return '<option value="' + x.id + '"' + (x.id === u.reporting_manager_id ? ' selected' : '') + '>' + esc(x.name) + ' (' + esc(x.username) + ')</option>';
  }).join('');

  var distOpts = '<option value="">No district</option>' + ADMIN_DISTRICTS.filter(function (d) {
    return d.is_active;
  }).map(function (d) {
    return '<option value="' + d.id + '"' + (d.id === u.district_id ? ' selected' : '') + '>' + esc(d.name) + '</option>';
  }).join('');

  var mandOpts = '<option value="">No mandal</option>' + ADMIN_MANDALS.filter(function (m) {
    return m.is_active && (!u.district_id || m.district_id === u.district_id);
  }).map(function (m) {
    return '<option value="' + m.id + '"' + (m.id === u.mandal_id ? ' selected' : '') + '>' + esc(m.name) + '</option>';
  }).join('');

  var vehOpts = '<option value="">No vehicle</option>' + ADMIN_VEHICLES.filter(function (v) {
    return v.is_active;
  }).map(function (v) {
    return '<option value="' + v.id + '"' + (v.id === u.vehicle_id ? ' selected' : '') + '>' + esc(v.registration_no) + '</option>';
  }).join('');

  document.getElementById('modal').innerHTML = '<div class="ovl" onclick="if(event.target===this)closeModal()"><div class="sheet" style="max-width:760px">' +
    '<div class="sh"><div><div style="font-size:18px;font-weight:800">Edit User Details</div>' +
    '<div style="font-size:12.5px;opacity:.9;margin-top:2px">Username: <b>@' + esc(u.username) + '</b></div></div>' +
    '<button class="x" onclick="closeModal()">&times;</button></div>' +
    '<div class="sb">' +
    '<div id="medit_dynamic_badge" class="dynamic-role-card"></div>' +
    '<div class="grid2">' +
      '<div class="fld"><label>Full Name *</label><input id="medit_name" value="' + esc(u.name || '') + '"></div>' +
      '<div class="fld"><label>Department / Role *</label><select id="medit_role" onchange="syncDynamicUserForm(\'medit\')">' + roleOpts + '</select></div>' +
      '<div class="fld"><label>Phone / Contact</label><input id="medit_phone" value="' + esc(u.phone || '') + '"></div>' +
      '<div class="fld"><label>HR Employee Code</label><input id="medit_hr_code" value="' + esc(u.hr_emp_code || '') + '"></div>' +
      '<div class="fld"><label>Reporting Manager</label><select id="medit_report_to">' + mgrOpts + '</select></div>' +
      '<div class="fld"><label>Account Status</label><select id="medit_active"><option value="1"' + (u.active ? ' selected' : '') + '>Active</option><option value="0"' + (!u.active ? ' selected' : '') + '>Inactive</option></select></div>' +
    '</div>' +
    '<input type="hidden" id="medit_is_manager" value="' + (u.is_team_manager ? '1' : '0') + '">' +
    '<div class="leadership-group" id="medit_leadership_group">' +
      '<div class="leadership-title">Leadership &amp; Dispatch Role (Team Executive vs Local Team Lead)</div>' +
      '<div class="leadership-options">' +
        '<label class="leadership-opt ' + (currentMode === 'eng' ? 'selected' : '') + '" id="medit_opt_eng_label" onclick="setLeadershipMode(\'medit\', \'eng\')">' +
          '<div><div class="leadership-opt-title">Field Engineer</div><div class="leadership-opt-sub">Standard technician for maintenance &amp; repairs</div></div>' +
          '<input type="radio" name="medit_leadership_mode" id="medit_mode_eng" value="eng" ' + (currentMode === 'eng' ? 'checked' : '') + '>' +
        '</label>' +
        '<label class="leadership-opt ' + (currentMode === 'lead' ? 'selected' : '') + '" id="medit_opt_lead_label" onclick="setLeadershipMode(\'medit\', \'lead\')">' +
          '<div><div class="leadership-opt-title">Local Team Lead</div><div class="leadership-opt-sub">District ground supervisor (Dispatches local MMU tickets)</div></div>' +
          '<input type="radio" name="medit_leadership_mode" id="medit_mode_lead" value="lead" ' + (currentMode === 'lead' ? 'checked' : '') + '>' +
        '</label>' +
        '<label class="leadership-opt ' + (currentMode === 'exec' ? 'selected' : '') + '" id="medit_opt_exec_label" onclick="setLeadershipMode(\'medit\', \'exec\')">' +
          '<div><div class="leadership-opt-title">Team Executive</div><div class="leadership-opt-sub">Statewide department head (Oversees all 26 districts)</div></div>' +
          '<input type="radio" name="medit_leadership_mode" id="medit_mode_exec" value="exec" ' + (currentMode === 'exec' ? 'checked' : '') + '>' +
        '</label>' +
      '</div>' +
    '</div>' +
    '<div id="medit_location_section">' +
      '<div style="font-weight:700;font-size:13.5px;margin:12px 0 6px;color:var(--ink)" id="medit_loc_title">Location &amp; District Assignment</div>' +
      '<div class="grid3">' +
        '<div class="fld" id="medit_district_wrap"><label id="medit_dist_label">District</label><select id="medit_district" onchange="syncDynamicUserDistrict(\'medit\')">' + distOpts + '</select></div>' +
        '<div class="fld" id="medit_mandal_wrap"><label>Mandal (LT Only)</label><select id="medit_mandal">' + mandOpts + '</select></div>' +
        '<div class="fld" id="medit_vehicle_wrap"><label>Vehicle (LT Only)</label><select id="medit_vehicle">' + vehOpts + '</select></div>' +
      '</div>' +
    '</div>' +
    '<div style="font-weight:700;font-size:13.5px;margin-top:10px;margin-bottom:8px;color:var(--ink)">Reset Password (Optional)</div>' +
    '<div class="fld"><label>New Password</label><input id="medit_pw" type="password" placeholder="Leave blank to keep current password"></div>' +
    '<div style="display:flex;justify-content:flex-end;gap:10px;margin-top:20px;border-top:1px solid var(--line);padding-top:14px">' +
      '<button class="btn o" onclick="closeModal()">Cancel</button>' +
      '<button class="btn" onclick="saveUserEdit(' + u.id + ')">Save Changes</button>' +
    '</div>' +
    '</div></div></div>';

  setTimeout(function () { syncDynamicUserForm('medit'); }, 10);
}

function closeModal() {
  var m = document.getElementById('modal');
  if (m) m.innerHTML = '';
}

function saveUserEdit(id) {
  var name = gv('medit_name'),
      role = document.getElementById('medit_role').value,
      phone = gv('medit_phone'),
      hrCode = gv('medit_hr_code'),
      reportTo = document.getElementById('medit_report_to').value,
      active = document.getElementById('medit_active').value === '1',
      isManagerVal = document.getElementById('medit_is_manager').value,
      isManager = isManagerVal === '1',
      districtId = document.getElementById('medit_district').value,
      mandalId = document.getElementById('medit_mandal').value,
      vehicleId = document.getElementById('medit_vehicle').value,
      pw = gv('medit_pw');

  if (!name) return toast('User name is required');

  var payload = {
    name: name,
    role: role,
    phone: phone,
    hr_emp_code: hrCode,
    reporting_manager_id: reportTo ? +reportTo : null,
    active: active,
    is_team_manager: isManager,
    district_id: districtId ? +districtId : null,
    mandal_id: mandalId ? +mandalId : null,
    vehicle_id: vehicleId ? +vehicleId : null
  };
  if (pw) {
    if (pw.length < 8) return toast('Password must be at least 8 characters');
    payload.password = pw;
  }

  api('PUT', '/admin/users/' + id, payload).then(function () {
    toast('User details updated successfully');
    closeModal();
    ADMIN_LOADED.users = false;
    loadAdminSection('users');
  }).catch(function (e) {
    toast(typeof e === 'string' ? e : 'Failed to update user');
  });
}

function adminToggleUser(id, active) {
  api('PUT', '/admin/users/' + id, { active: active }).then(function () { toast(active ? 'Activated' : 'Deactivated'); loadAdminSection('users'); })
    .catch(function (e) { toast(typeof e === 'string' ? e : 'Failed'); });
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
window.addEventListener('hashchange', function () {
  if (TOK) {
    restoreState();
    render();
    if (TAB === 'queue') load(true);
    else if (TAB === 'dash') load(true);
    else if (TAB === 'mine') load(true);
    else if (TAB === 'admin') loadAdminSection(ADMIN_TAB);
    if (CURRENT_MODAL_TICKET_ID) openT(CURRENT_MODAL_TICKET_ID);
  }
});

window.addEventListener('online', function () {
  toast('Cellular signal / Internet connection restored');
  syncLTOutbox(false);
});
window.addEventListener('offline', function () {
  toast('Offline / No cellular connection. Reports will save to Outbox.');
});

// Dismiss popovers, notifications, and mobile menu when clicking or tapping anywhere outside
function handleOutsideDismiss(e) {
  var target = e.target;
  if (!target) return;

  // 1. Close notifications if clicking outside #npanel and outside #bell
  if (NOTIF_OPEN) {
    var npanelEl = document.getElementById('npanel');
    var bellEl = document.getElementById('bell');
    var isInsideNpanel = npanelEl && npanelEl.contains(target);
    var isInsideBell = bellEl && bellEl.contains(target);
    if (!isInsideNpanel && !isInsideBell) {
      closeNotifs();
    }
  }

  // 2. Close mobile sidebar if clicking outside #sidebar and outside #nav_toggle
  var sb = document.getElementById('sidebar');
  if (sb && sb.classList.contains('show')) {
    var navToggleEl = document.getElementById('nav_toggle');
    var isInsideSidebar = sb.contains(target);
    var isInsideToggle = navToggleEl && navToggleEl.contains(target);
    if (!isInsideSidebar && !isInsideToggle) {
      closeSidebar();
    }
  }
}

document.addEventListener('click', handleOutsideDismiss, true);
document.addEventListener('touchend', handleOutsideDismiss, { passive: true });

// Close active overlays on Escape key
document.addEventListener('keydown', function (e) {
  if (e.key === 'Escape' || e.keyCode === 27) {
    if (NOTIF_OPEN) {
      closeNotifs();
      return;
    }
    var sb = document.getElementById('sidebar');
    if (sb && sb.classList.contains('show')) {
      closeSidebar();
      return;
    }
    var m = document.getElementById('modal');
    if (m && m.innerHTML.trim() !== '') {
      closeModal();
      return;
    }
  }
});