var API='/cccapi', TOK=sessionStorage.getItem('ccc_tok')||'', ME=null, META=null, TAB='queue', ROWS=[], ROWTOTAL=0, DASH=null,
  FILT={status:'open',scope:'',priority:'',category:'',mmu_vehicle:'',district:'',date_from:'',date_to:'',q:'',page:1,page_size:50},
  NOTIFS=[], NOTIF_OPEN=false, POLL_TIMER=null, CLOCK_TIMER=null,
  ADMIN_TAB='teams', ADMIN_TEAMS=[], ADMIN_CATEGORIES=[], ADMIN_SLA=null, ADMIN_USERS=[], ADMIN_ROLES=[], ADMIN_AUDIT=[], ADMIN_LOADED={},
  ADMIN_DISTRICTS=[], ADMIN_ZONES=[], ADMIN_MANDALS=[], ADMIN_VEHICLES=[];
function esc(s){return (s==null?'':String(s)).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
function api(m,p,b){var h={'Content-Type':'application/json'};if(TOK)h.Authorization='Bearer '+TOK;
  return fetch(API+p,{method:m,headers:h,body:b?JSON.stringify(b):undefined}).then(function(r){
    if(r.status===401){logout();throw'auth';}
    return r.json().then(function(d){if(!r.ok)throw(d.detail||('HTTP '+r.status));return d;});});}
function toast(m){var t=document.createElement('div');t.className='toast';t.textContent=m;document.body.appendChild(t);setTimeout(function(){t.style.transition='all 0.3s ease';t.style.opacity='0';t.style.transform='translateX(-50%) translateY(20px)';setTimeout(function(){t.remove();},300);},3000);}
function doLogin(){var u=document.getElementById('u').value.trim(),p=document.getElementById('p').value;
  document.getElementById('lerr').textContent='';
  api('POST','/auth',{username:u,password:p}).then(function(d){TOK=d.token;ME=d.user;sessionStorage.setItem('ccc_tok',TOK);sessionStorage.setItem('ccc_me',JSON.stringify(d.user));boot();})
  .catch(function(e){document.getElementById('lerr').textContent=(e==='auth'?'':(e||'Login failed'));});}
function logout(){TOK='';ME=null;sessionStorage.clear();if(POLL_TIMER)clearInterval(POLL_TIMER);if(CLOCK_TIMER)clearInterval(CLOCK_TIMER);var _u=document.getElementById('u'),_p=document.getElementById('p'),_e=document.getElementById('lerr');if(_u)_u.value='';if(_p)_p.value='';if(_e)_e.textContent='';document.getElementById('app').classList.add('hide');document.getElementById('login').classList.remove('hide');}
function boot(){document.getElementById('login').classList.add('hide');document.getElementById('app').classList.remove('hide');
  try{ME=ME||JSON.parse(sessionStorage.getItem('ccc_me'));}catch(e){}
  document.getElementById('who').innerHTML='<b>'+esc(ME.name)+'</b>'+esc(roleLabel(ME.role));
  api('GET','/meta').then(function(m){META=m;render();load();loadNotifs();startPolling();});}
function startPolling(){
  if(POLL_TIMER)clearInterval(POLL_TIMER);
  if(CLOCK_TIMER)clearInterval(CLOCK_TIMER);
  POLL_TIMER=setInterval(function(){load();loadNotifs();},18000);
  CLOCK_TIMER=setInterval(tickClock,30000);}
function roleLabel(r){return ({CC_MANAGER:'CC Manager',CALL_TAKER:'Call Taker',SERVICE:'Service Engineer',APPLICATION:'Application Person',QUALITY:'Quality Person',TECHNICAL:'Technical Team',NETWORK:'Network Team',FIELD_OPS:'Field Operations',FLEET:'Fleet Team'})[r]||r;}
function tabsFor(){var t=[['queue','Ticket Queue']];
  if(ME.role==='CALL_TAKER'||ME.role==='CC_MANAGER')t.push(['new','Register Call']);
  if(ME.role==='CC_MANAGER')t.push(['dash','Daily Monitoring']);
  t.push(['matrix','Routing Matrix']);
  if(ME.role==='CC_MANAGER')t.push(['admin','Admin Portal']);
  return t;}
function render(){document.getElementById('tabs').innerHTML=tabsFor().map(function(x){return '<button class="tab'+(TAB===x[0]?' on':'')+'" onclick="go(\''+x[0]+'\')">'+esc(x[1])+'</button>';}).join('');
  var b=document.getElementById('body');
  if(TAB==='new'){b.innerHTML=viewNew();setTimeout(function(){previewRoute();loadNewCallGeo();},0);}
  else if(TAB==='dash')b.innerHTML=viewDash();
  else if(TAB==='matrix')b.innerHTML=viewMatrix();
  else if(TAB==='admin')b.innerHTML=viewAdmin();
  else b.innerHTML=viewQueue();}
function go(t){TAB=t;render();load();if(t==='admin')loadAdminSection(ADMIN_TAB);}
function queueQS(){
  var keys=['status','scope','priority','category','mmu_vehicle','district','date_from','date_to','page','page_size'];
  return keys.map(function(k){return k+'='+encodeURIComponent(FILT[k]||'');}).join('&')+'&q_='+encodeURIComponent(FILT.q||'');}
function load(){
  if(TAB==='queue'){api('GET','/tickets?'+queueQS()).then(function(d){ROWS=d.rows||[];ROWTOTAL=d.total||0;render();});}
  if(TAB==='dash'){api('GET','/dashboard').then(function(d){DASH=d;render();});}}
function setFilt(k,v){FILT[k]=v;FILT.page=1;load();}
function gotoPage(p){if(p<1)return;FILT.page=p;load();}

/* ---------- queue ---------- */
function parseDT(s){if(!s)return null;var p=s.split(/[- :]/);return new Date(+p[0],+p[1]-1,+p[2],+p[3]||0,+p[4]||0,0);}
function computeTier(dueAt,tatMins){var d=parseDT(dueAt);if(!d)return null;var mins=(d.getTime()-Date.now())/60000;
  var sla=(META&&META.sla)||{at_risk_minutes:60,at_risk_fraction:.2,critical_minutes:15,critical_fraction:.05};
  var tm=tatMins||240;
  if(mins<0)return{state:'BREACHED',mins:mins};
  if(mins<=Math.max(sla.critical_minutes,tm*sla.critical_fraction))return{state:'CRITICAL',mins:mins};
  if(mins<=Math.max(sla.at_risk_minutes,tm*sla.at_risk_fraction))return{state:'AT RISK',mins:mins};
  return{state:'ON TRACK',mins:mins};}
function tickClock(){if(TAB!=='queue'||!ROWS.length)return;
  ROWS.forEach(function(t){if(t.status==='CLOSED')return;var r=computeTier(t.due_at,t.tat_mins);if(r){t.tat_state=r.state;t.mins_left=Math.round(r.mins);}});
  render();}
function tatPill(t){var s=t.tat_state;var k=s==='BREACHED'?'p-crit':(s==='CRITICAL'?'p-critical':(s==='AT RISK'?'p-warn':(s==='MET'||s==='ON TRACK'?'p-ok':'p-mut')));
  var extra=(t.mins_left!=null&&t.status!=='CLOSED')?(' · '+(t.mins_left<0?('+'+Math.abs(t.mins_left)):t.mins_left)+'m'):'';
  return '<span class="pill '+k+'">'+esc(s)+extra+'</span>';}
function gv(i){var e=document.getElementById(i);return e?e.value.trim():'';}
function applyFilters(){FILT.mmu_vehicle=gv('qf_veh');FILT.district=gv('qf_dist');FILT.q=gv('qf_q');
  FILT.priority=gv('qf_pri');FILT.category=gv('qf_cat');FILT.date_from=gv('qf_from');FILT.date_to=gv('qf_to');FILT.page=1;load();}
function clearFilters(){FILT.mmu_vehicle='';FILT.district='';FILT.q='';FILT.priority='';FILT.category='';FILT.date_from='';FILT.date_to='';FILT.page=1;load();render();}
function viewQueue(){
  var f=function(k,v,lab){return '<button class="tab'+((FILT[k]||'')===v?' on':'')+'" onclick="setFilt(\''+k+'\',\''+v+'\')">'+lab+'</button>';};
  var bar='<div class="tabs" style="margin-bottom:12px">'+f('status','open','Open')+f('status','','All')+f('status','CLOSED','Closed')+
    f('scope','','&mdash;')+f('scope','breach','TAT Breached')+f('scope','risk','At Risk')+f('scope','critical','Critical')+f('scope','escalated','Escalated')+f('scope','unassigned','Unassigned')+'</div>';
  var cats=(META&&META.routing)?'<option value="">Any category</option>'+Object.keys(META.routing).map(function(k){return '<option value="'+k+'"'+(FILT.category===k?' selected':'')+'>'+esc(META.routing[k].label)+'</option>';}).join(''):'';
  var pris=(META&&META.priority)?'<option value="">Any priority</option>'+Object.keys(META.priority).map(function(k){return '<option value="'+k+'"'+(FILT.priority===k?' selected':'')+'>'+k+'</option>';}).join(''):'';
  bar+='<div class="card" style="margin-bottom:12px"><div class="grid3">'+
    '<div class="fld"><label>Vehicle</label><input id="qf_veh" value="'+esc(FILT.mmu_vehicle)+'" onkeydown="if(event.key===\'Enter\')applyFilters()"></div>'+
    '<div class="fld"><label>District</label><input id="qf_dist" value="'+esc(FILT.district)+'" onkeydown="if(event.key===\'Enter\')applyFilters()"></div>'+
    '<div class="fld"><label>Keyword</label><input id="qf_q" value="'+esc(FILT.q)+'" placeholder="ticket / problem text" onkeydown="if(event.key===\'Enter\')applyFilters()"></div>'+
    '<div class="fld"><label>Priority</label><select id="qf_pri">'+pris+'</select></div>'+
    '<div class="fld"><label>Category</label><select id="qf_cat">'+cats+'</select></div>'+
    '<div class="fld"><label>Created from</label><input id="qf_from" type="date" value="'+esc(FILT.date_from)+'"></div>'+
    '<div class="fld"><label>Created to</label><input id="qf_to" type="date" value="'+esc(FILT.date_to)+'"></div>'+
    '<div class="fld" style="display:flex;align-items:flex-end;gap:8px"><button class="btn sm" onclick="applyFilters()">Apply</button><button class="btn o sm" onclick="clearFilters()">Clear</button></div>'+
    '</div></div>';
  if(!ROWS.length)return bar+'<div class="card"><div class="empty">No tickets in this view.</div></div>';
  var rows=ROWS.map(function(t){
    return '<tr class="row" onclick="openT('+t.id+')">'+
      '<td><b>'+esc(t.ticket_no)+'</b><div class="muted">'+esc(t.source)+'</div></td>'+
      '<td>'+esc(t.mmu_vehicle||'—')+'<div class="muted">'+esc(t.district||'')+'</div></td>'+
      '<td>'+esc(t.category_label||'')+'</td>'+
      '<td><span class="pill p-'+esc(t.priority)+'">'+esc(t.priority)+'</span>'+(t.vip?' <span class="pill p-crit">VIP</span>':'')+'</td>'+
      '<td>'+esc(t.team_label||'')+'</td>'+
      '<td><span class="pill p-mut">'+esc((t.status||'').replace(/_/g,' '))+'</span>'+(t.escalated?' <span class="pill p-crit">ESC</span>':'')+'</td>'+
      '<td>'+tatPill(t)+'<div class="muted">'+esc(t.due_at||'')+'</div></td>'+
      '<td style="max-width:280px">'+esc((t.problem||'').slice(0,90))+'</td></tr>';}).join('');
  var pages=Math.max(1,Math.ceil(ROWTOTAL/FILT.page_size));
  var pager='<div class="pager"><span>'+ROWTOTAL+' ticket'+(ROWTOTAL===1?'':'s')+' &middot; page '+FILT.page+' of '+pages+'</span>'+
    '<button class="btn o sm" '+(FILT.page<=1?'disabled':'')+' onclick="gotoPage('+(FILT.page-1)+')">&larr; Prev</button>'+
    '<button class="btn o sm" '+(FILT.page>=pages?'disabled':'')+' onclick="gotoPage('+(FILT.page+1)+')">Next &rarr;</button></div>';
  return bar+'<div class="card"><div style="overflow-x:auto"><table><thead><tr><th>Ticket</th><th>MMU / District</th><th>Category</th><th>Pri</th><th>Team</th><th>Status</th><th>TAT</th><th>Problem</th></tr></thead><tbody>'+rows+'</tbody></table></div></div>'+pager;}

/* ---------- register call ---------- */
function viewNew(){
  var cats=Object.keys(META.routing).map(function(k){return '<option value="'+k+'">'+esc(META.routing[k].label)+'</option>';}).join('');
  var pri=Object.keys(META.priority).map(function(k){return '<option value="'+k+'">'+k+' — '+esc(META.priority[k])+'</option>';}).join('');
  return '<div class="card"><h3 style="margin-bottom:4px">Register a toll-free call</h3>'+
   '<div class="muted" style="margin-bottom:16px">SOP §4 — capture every field, classify the issue, and the system routes it to the responsible team automatically.</div>'+
   '<div class="grid3">'+
    '<div class="fld"><label>MMU / Vehicle number *</label><input id="f_veh" list="vehListDL" placeholder="AP39UL4276" oninput="vehicleSearchInput()" autocomplete="off"><datalist id="vehListDL"></datalist><input type="hidden" id="f_vehicle_id"></div>'+
    '<div class="fld"><label>District</label><select id="f_district_id" onchange="districtChanged()"><option value="">Loading…</option></select></div>'+
    '<div class="fld"><label>Mandal</label><select id="f_mandal_id"><option value="">Select district first</option></select></div>'+
    '<div class="fld"><label>Location</label><input id="f_loc" placeholder="Village / landmark"></div>'+
    '<div class="fld"><label>Caller name</label><input id="f_cname"></div>'+
    '<div class="fld"><label>Caller contact</label><input id="f_cph" placeholder="10 digits"></div>'+
    '<div class="fld"><label>Equipment / machine</label><input id="f_eq" placeholder="XL-200 / H360 / tablet"></div>'+
   '</div>'+
   '<div class="fld"><label>Nature of the problem *</label><textarea id="f_prob" rows="3" placeholder="What exactly is happening?"></textarea></div>'+
   '<div class="grid3">'+
    '<div class="fld"><label>Error message / code</label><input id="f_err"></div>'+
    '<div class="fld"><label>Operational impact</label><input id="f_imp" placeholder="MMU stopped / partial / none"></div>'+
    '<div class="fld"><label>Priority *</label><select id="f_pri">'+pri+'</select></div>'+
   '</div>'+
   '<div class="fld"><label>Issue category *</label><select id="f_cat" onchange="previewRoute()">'+cats+'</select></div>'+
   '<div class="fld" style="display:flex;align-items:center;gap:8px"><input type="checkbox" id="f_vip" style="width:auto"> <label style="margin:0;text-transform:none;font-size:13px;font-weight:600;color:var(--ink2)">VIP / high-profile caller (auto-escalates to P1)</label></div>'+
   '<div class="route" id="rpre"></div>'+
   '<button class="btn" style="margin-top:14px" onclick="createT()">Create ticket &amp; route</button></div>';}
function previewRoute(){var c=document.getElementById('f_cat').value,r=META.routing[c];
  document.getElementById('rpre').innerHTML='Routes to <b>'+esc(META.teams[r.team])+'</b> &mdash; initial owner <b>'+esc(r.owner)+'</b>';}
var NEW_DISTRICTS=[], VEH_DEBOUNCE=null, VEH_RESULTS=[];
function loadNewCallGeo(){
  api('GET','/districts').then(function(rows){
    NEW_DISTRICTS=rows;
    var sel=document.getElementById('f_district_id');
    if(sel)sel.innerHTML='<option value="">Select district…</option>'+rows.map(function(d){return '<option value="'+d.id+'">'+esc(d.name)+'</option>';}).join('');
  }).catch(function(){});}
function districtChanged(){
  var did=document.getElementById('f_district_id').value;
  var msel=document.getElementById('f_mandal_id');
  if(!msel)return;
  if(!did){msel.innerHTML='<option value="">Select district first</option>';return;}
  msel.innerHTML='<option value="">Loading…</option>';
  api('GET','/mandals?district_id='+did).then(function(rows){
    msel.innerHTML='<option value="">Select mandal…</option>'+rows.map(function(m){return '<option value="'+m.id+'">'+esc(m.name)+'</option>';}).join('');
  }).catch(function(){});}
function vehicleSearchInput(){
  clearTimeout(VEH_DEBOUNCE);
  var q=document.getElementById('f_veh').value.trim();
  document.getElementById('f_vehicle_id').value='';
  if(q.length<2)return;
  VEH_DEBOUNCE=setTimeout(function(){
    api('GET','/vehicles/search?q='+encodeURIComponent(q)).then(function(rows){
      VEH_RESULTS=rows;
      document.getElementById('vehListDL').innerHTML=rows.map(function(v){return '<option value="'+esc(v.registration_no)+'">';}).join('');
      var exact=rows.find(function(v){return v.registration_no===q.toUpperCase();});
      if(exact)document.getElementById('f_vehicle_id').value=exact.id;
    }).catch(function(){});
  },300);}
function createT(){
  var g=function(i){var e=document.getElementById(i);return e?e.value.trim():'';};
  if(!g('f_prob'))return toast('Nature of the problem is required');
  var districtId=g('f_district_id'), mandalId=g('f_mandal_id'), vehicleId=g('f_vehicle_id');
  var districtName=districtId?((NEW_DISTRICTS.find(function(d){return String(d.id)===districtId;})||{}).name||''):'';
  api('POST','/ticket',{mmu_vehicle:g('f_veh'),vehicle_id:vehicleId?+vehicleId:null,district:districtName,
    district_id:districtId?+districtId:null,mandal_id:mandalId?+mandalId:null,location:g('f_loc'),caller_name:g('f_cname'),
    caller_phone:g('f_cph'),equipment:g('f_eq'),problem:g('f_prob'),error_code:g('f_err'),impact:g('f_imp'),
    category:g('f_cat'),priority:g('f_pri'),vip:document.getElementById('f_vip').checked})
  .then(function(d){toast('Ticket '+d.ticket_no+' created → '+d.team+(d.vip?' (VIP: bumped to P1)':''));TAB='queue';render();load();})
  .catch(function(e){toast(typeof e==='string'?e:'Failed');});}

/* ---------- ticket detail ---------- */
var MODAL_TICK=null;
function openT(id){api('GET','/ticket/'+id).then(function(d){renderT(d.ticket,d.events);});}
function closeT(){document.getElementById('modal').innerHTML='';if(MODAL_TICK){clearInterval(MODAL_TICK);MODAL_TICK=null;}}
function reopenT(id){var reason=prompt('Reason for reopening this ticket (required):');if(reason===null)return;if(!reason.trim()){toast('A reason is required to reopen');return;}
  api('POST','/ticket/action',{id:id,action:'reopen',note:reason.trim()}).then(function(){toast('Ticket reopened');closeT();load();})
  .catch(function(e){toast(typeof e==='string'?e:'Reopen failed');});}
function updateModalCountdown(t){var el=document.getElementById('modalTat');if(!el)return;
  var r=computeTier(t.due_at,t.tat_mins);if(!r)return;t.tat_state=r.state;t.mins_left=Math.round(r.mins);el.outerHTML=tatPill(t).replace('<span ','<span id="modalTat" ');}
function row(k,v){return v?('<div style="display:flex;gap:10px;padding:5px 0;border-bottom:1px solid #f4eff8"><div class="muted" style="min-width:130px">'+esc(k)+'</div><div>'+esc(v)+'</div></div>'):'';}
function renderT(t,evs){
  var mine=(ME.role===t.team)||ME.role==='CC_MANAGER'||ME.role==='CALL_TAKER';
  var A=[];
  if(mine){
    if(t.status==='NEW'||t.status==='ASSIGNED')A.push('<button class="btn" onclick="act('+t.id+',\'acknowledge\')">Acknowledge</button>');
    if(t.status==='ACKNOWLEDGED')A.push('<button class="btn" onclick="act('+t.id+',\'start\')">Start investigation</button>');
    if(['ACKNOWLEDGED','IN_PROGRESS','PENDING'].indexOf(t.status)>=0){
      A.push('<button class="btn o" onclick="act('+t.id+',\'update\')">Save update</button>');
      A.push('<button class="btn w" onclick="act('+t.id+',\'pending\')">Mark pending</button>');
      A.push('<button class="btn g" onclick="act('+t.id+',\'resolve\')">Resolve</button>');}
    if(t.status==='RESOLVED')A.push('<button class="btn g" onclick="act('+t.id+',\'confirm\')">Confirm with MMU</button>');
    if(t.status==='CLOSURE_CONFIRMATION')A.push('<button class="btn" onclick="act('+t.id+',\'close\')">Close ticket</button>');
    if(t.status!=='CLOSED')A.push('<button class="btn r" onclick="act('+t.id+',\'escalate\')">Escalate to CC Manager</button>');}
  if((ME.role==='CC_MANAGER'||ME.role==='CALL_TAKER')&&t.status==='CLOSED'){
    var closedDt=parseDT(t.closed_at),windowH=(META.sla&&META.sla.reopen_window_hours)||24;
    var withinWindow=closedDt?((Date.now()-closedDt.getTime())/3600000<=windowH):true;
    if(withinWindow)A.push('<button class="btn o" onclick="reopenT('+t.id+')">Reopen</button>');
    else A.push('<span class="muted">Reopen window ('+windowH+'h) has passed - register a new ticket</span>');}
  var reroute=(ME.role==='CC_MANAGER'||ME.role==='CALL_TAKER')?
    ('<div class="grid2" style="margin-top:12px"><div class="fld"><label>Re-route to team</label><select id="a_team">'+
      Object.keys(META.teams).map(function(k){return '<option value="'+k+'"'+(k===t.team?' selected':'')+'>'+esc(META.teams[k])+'</option>';}).join('')+
      '</select><button class="btn o sm" style="margin-top:7px" onclick="act('+t.id+',\'reassign\')">Apply re-route</button></div>'+
      '<div class="fld"><label>Change priority</label><select id="a_pri">'+Object.keys(META.priority).map(function(k){return '<option value="'+k+'"'+(k===t.priority?' selected':'')+'>'+k+'</option>';}).join('')+
      '</select><button class="btn o sm" style="margin-top:7px" onclick="act('+t.id+',\'repriority\')">Apply priority</button></div></div>'):'';
  var canAssign=t.status!=='CLOSED'&&((ME.role===t.team&&ME.is_team_manager)||ME.role==='CC_MANAGER');
  var assignBlock=canAssign?('<div class="fld" style="margin-top:12px"><label>Assign to engineer</label>'+
      '<select id="a_assignee_sel"><option value="">Loading roster…</option></select> '+
      '<button class="btn o sm" onclick="act('+t.id+',\'assign\')">Assign</button></div>'):'';
  var form=(mine&&t.status!=='CLOSED')?('<div class="grid2" style="margin-top:6px">'+
      '<div class="fld"><label>Diagnosis</label><textarea id="a_diag" rows="2">'+esc(t.diagnosis||'')+'</textarea></div>'+
      '<div class="fld"><label>Action taken</label><textarea id="a_act" rows="2">'+esc(t.action_taken||'')+'</textarea></div>'+
      '<div class="fld"><label>Root cause</label><input id="a_rc" value="'+esc(t.root_cause||'')+'"></div>'+
      '<div class="fld"><label>Parts / replacement</label><input id="a_parts" value="'+esc(t.parts||'')+'"></div>'+
      '<div class="fld"><label>Resolution (required to resolve)</label><textarea id="a_res" rows="2">'+esc(t.resolution||'')+'</textarea></div>'+
      '<div class="fld"><label>Pending reason (required to hold)</label><input id="a_pend" value="'+esc(t.pending_reason||'')+'"></div>'+
      '<div class="fld"><label>Confirmed by (MMU / field)</label><input id="a_conf" value="'+esc(t.confirmed_by||'')+'" placeholder="Name at the MMU who confirmed"></div>'+
      '<div class="fld"><label>Note</label><input id="a_note" placeholder="Escalation / re-route remark"></div></div>'):'';
  document.getElementById('modal').innerHTML='<div class="ovl" onclick="if(event.target===this)closeT()"><div class="sheet">'+
    '<div class="sh"><div><div style="font-size:19px;font-weight:800">'+esc(t.ticket_no)+' &middot; '+esc(t.category_label)+(t.vip?' <span class="pill p-crit">VIP</span>':'')+'</div>'+
      '<div style="font-size:12.5px;opacity:.9;margin-top:3px">'+esc(t.mmu_vehicle||'—')+' &middot; '+esc(t.district||'')+' &middot; '+esc(t.team_label)+' &middot; '+esc(t.priority)+'</div></div>'+
      '<button class="x" onclick="closeT()">&times;</button></div><div class="sb">'+
    '<div style="display:flex;gap:9px;flex-wrap:wrap;margin-bottom:14px"><span class="pill p-mut">'+esc((t.status||'').replace(/_/g,' '))+'</span>'+tatPill(t).replace('<span ','<span id="modalTat" ')+
      (t.escalated?'<span class="pill p-crit">ESCALATED</span>':'')+'<span class="pill p-mut">TAT '+esc(t.tat_mins)+' min</span>'+
      (t.paused_minutes?'<span class="pill p-mut">Paused '+esc(t.paused_minutes)+'m so far</span>':'')+'</div>'+
    '<div class="grid2"><div>'+row('Problem',t.problem)+row('Equipment',t.equipment)+row('Error code',t.error_code)+row('Impact',t.impact)+
      row('Caller',(t.caller_name||'')+(t.caller_phone?(' · '+t.caller_phone):''))+row('Location',t.location)+'</div>'+
     '<div>'+row('Created',t.created_at)+row('Due (TAT)',t.due_at)+row('Acknowledged',t.acknowledged_at)+row('Resolved',t.resolved_at)+
      row('Assigned to',t.assignee)+row('Confirmed by',t.confirmed_by)+row('Closed',t.closed_at)+row('Owner',t.owner)+'</div></div>'+
    form+reroute+assignBlock+
    '<div style="display:flex;gap:9px;flex-wrap:wrap;margin-top:14px">'+A.join('')+'</div>'+
    '<h4 style="margin:18px 0 8px;font-size:14px">Audit trail</h4><div class="tl">'+
      (evs||[]).map(function(e){return '<div class="e"><b>'+esc(e.action)+'</b> — '+esc(e.detail||'')+'<div class="muted">'+esc(e.at)+' · '+esc(e.actor)+' ('+esc(e.actor_role)+')</div></div>';}).join('')+
    '</div></div></div></div>';
  if(canAssign){
    var rosterUrl='/users/team-roster'+(ME.role==='CC_MANAGER'?('?team='+encodeURIComponent(t.team)):'');
    api('GET',rosterUrl).then(function(rows){
      var sel=document.getElementById('a_assignee_sel');
      if(sel)sel.innerHTML='<option value="">Select engineer…</option>'+rows.map(function(u){return '<option value="'+esc(u.username)+'"'+(u.username===t.assignee?' selected':'')+'>'+esc(u.name)+'</option>';}).join('');
    }).catch(function(){});}
  if(MODAL_TICK)clearInterval(MODAL_TICK);
  if(t.status!=='CLOSED')MODAL_TICK=setInterval(function(){updateModalCountdown(t);},30000);}
function act(id,a){
  var g=function(i){var e=document.getElementById(i);return e?e.value.trim():undefined;};
  var b={id:id,action:a,diagnosis:g('a_diag'),action_taken:g('a_act'),root_cause:g('a_rc'),parts:g('a_parts'),
         resolution:g('a_res'),pending_reason:g('a_pend'),confirmed_by:g('a_conf'),note:g('a_note'),
         team:g('a_team'),priority:g('a_pri'),assignee:g('a_assignee_sel')};
  api('POST','/ticket/action',b).then(function(){toast('Done: '+a);closeT();load();})
   .catch(function(e){toast(typeof e==='string'?e:'Action failed');});}

/* ---------- notifications ---------- */
function loadNotifs(){api('GET','/notifications').then(function(d){NOTIFS=d.rows||[];renderBell();if(NOTIF_OPEN)renderNotifPanel();}).catch(function(){});}
function renderBell(){var n=NOTIFS.filter(function(x){return !x.read_at;}).length;var b=document.getElementById('nbadge');
  if(!b)return;if(n>0){b.textContent=n>99?'99+':n;b.classList.remove('hide');}else{b.classList.add('hide');}}
function toggleNotifs(){NOTIF_OPEN=!NOTIF_OPEN;if(NOTIF_OPEN){renderNotifPanel();}else{document.getElementById('npanel').innerHTML='';}}
function renderNotifPanel(){
  var body=!NOTIFS.length?'<div class="empty" style="padding:24px">No notifications</div>':
    NOTIFS.map(function(n){return '<div class="ni'+(n.read_at?'':' unread')+'" onclick="openNotif('+n.id+','+(n.ticket_id||'null')+')">'+
      '<div class="t">'+esc((n.type||'').replace(/_/g,' '))+'</div><div>'+esc(n.message)+'</div><div class="muted">'+esc(n.created_at)+'</div></div>';}).join('');
  document.getElementById('npanel').innerHTML='<div class="npanel"><div class="nh">Notifications</div>'+body+'</div>';}
function openNotif(id,ticketId){var n=NOTIFS.find(function(x){return x.id===id;});
  if(n&&!n.read_at){api('POST','/notifications/'+id+'/read',{}).then(function(){n.read_at='now';renderBell();if(NOTIF_OPEN)renderNotifPanel();}).catch(function(){});}
  NOTIF_OPEN=false;document.getElementById('npanel').innerHTML='';
  if(ticketId){TAB='queue';render();openT(ticketId);}}

/* ---------- dashboard ---------- */
function attnGoto(status,scope,priority){TAB='queue';FILT.status=status||'';FILT.scope=scope||'';FILT.priority=priority||'';
  FILT.mmu_vehicle='';FILT.district='';FILT.q='';FILT.category='';FILT.date_from='';FILT.date_to='';FILT.page=1;render();load();}
function viewDash(){
  if(!DASH)return '<div class="card"><div class="empty">Loading daily monitoring…</div></div>';
  var t=DASH.today||{},k=DASH.kpi||{};
  var kpi=function(n,l,c){return '<div class="kpi"><div class="n" style="color:'+(c||'var(--pur)')+'">'+esc(n==null?'—':n)+'</div><div class="l">'+esc(l)+'</div></div>';};
  var attn=function(n,l,c,onclick){return '<button class="c" onclick="'+onclick+'"><div class="n" style="color:'+c+'">'+esc(n==null?0:n)+'</div><div class="l">'+esc(l)+'</div></button>';};
  var tbl=function(title,rows,cols){return '<div class="card" style="margin-bottom:14px"><h4 style="margin-bottom:10px;font-size:14px">'+esc(title)+'</h4>'+
    '<table><thead><tr>'+cols.map(function(c){return '<th>'+esc(c[0])+'</th>';}).join('')+'</tr></thead><tbody>'+
    (rows||[]).map(function(r){return '<tr>'+cols.map(function(c){return '<td>'+esc(c[1](r))+'</td>';}).join('')+'</tr>';}).join('')+
    '</tbody></table></div>';};
  return '<div class="card" style="margin-bottom:14px"><h4 style="margin-bottom:10px;font-size:14px">Attention required</h4><div class="attn">'+
      attn(t.p1_open,'P1 open',"var(--crit)","attnGoto('open','','P1')")+
      attn(t.breached,'TAT breached',"var(--crit)","attnGoto('open','breach','')")+
      attn(t.critical,'Critical',"#a3300c","attnGoto('open','critical','')")+
      attn(t.at_risk,'At risk',"var(--warn)","attnGoto('open','risk','')")+
      attn(t.pending,'Pending',"var(--org)","attnGoto('PENDING','','')")+
      attn(t.awaiting_confirmation,'Awaiting MMU confirmation',"var(--pur)","attnGoto('RESOLVED','','')")+
      attn(t.escalated,'Escalated',"var(--mag)","attnGoto('open','escalated','')")+
      attn(t.unassigned,'Unassigned',"var(--org)","attnGoto('open','unassigned','')")+
    '</div></div>'+
    '<div class="kpis">'+
      kpi(t.tickets,'Tickets today')+kpi(t.open,'Open tickets')+kpi(t.closed,'Closed today','var(--ok)')+
      kpi(t.breached,'TAT breached','var(--crit)')+kpi(t.at_risk,'At risk','var(--warn)')+kpi(t.escalated,'Escalated','var(--mag)')+
    '</div>'+
    '<div class="kpis">'+
      kpi(k.tat_compliance_pct==null?'—':k.tat_compliance_pct+'%','TAT compliance','var(--ok)')+
      kpi(k.tat_breach_pct==null?'—':k.tat_breach_pct+'%','TAT breach %','var(--crit)')+
      kpi(k.avg_ack_mins==null?'—':k.avg_ack_mins+'m','Avg acknowledgement')+
      kpi(k.avg_resolution_mins==null?'—':k.avg_resolution_mins+'m','Avg resolution')+
      kpi(k.escalation_pct+'%','Escalation %','var(--mag)')+kpi(k.closed_total,'Closed (all time)')+
    '</div>'+
    '<div class="grid2">'+
      tbl('Tickets by category',DASH.by_category,[['Category',function(r){return (META.routing[r.category]||{}).label||r.category;}],['Total',function(r){return r.n;}],['Open',function(r){return r.open_n;}]])+
      tbl('Tickets by responsible team',DASH.by_team,[['Team',function(r){return META.teams[r.team]||r.team;}],['Total',function(r){return r.n;}],['Open',function(r){return r.open_n;}],['Breached',function(r){return r.breach_n;}]])+
      tbl('By priority',DASH.by_priority,[['Priority',function(r){return r.priority;}],['Total',function(r){return r.n;}],['Open',function(r){return r.open_n;}]])+
      tbl('By status',DASH.by_status,[['Status',function(r){return (r.status||'').replace(/_/g,' ');}],['Count',function(r){return r.n;}]])+
      tbl('Repeat issues by MMU',DASH.repeat_vehicles,[['MMU / Vehicle',function(r){return r.mmu_vehicle;}],['Tickets',function(r){return r.n;}]])+
      tbl('Daily volume (14 days)',DASH.daily,[['Date',function(r){return r.d;}],['Created',function(r){return r.n;}],['Closed',function(r){return r.closed_n;}]])+
    '</div>';}

/* ---------- routing matrix ---------- */
function viewMatrix(){
  var rows=Object.keys(META.routing).map(function(k){var r=META.routing[k];
    return '<tr><td><b>'+esc(r.label)+'</b></td><td>'+esc(META.teams[r.team])+'</td><td>'+esc(r.owner)+'</td></tr>';}).join('');
  var tat=Object.keys(META.tat).map(function(k){return '<tr><td><span class="pill p-'+k+'">'+k+'</span></td><td>'+esc(META.priority[k])+'</td><td><b>'+esc(META.tat[k])+' min</b></td></tr>';}).join('');
  return '<div class="card" style="margin-bottom:14px"><h4 style="margin-bottom:4px;font-size:15px">Issue routing matrix</h4>'+
    '<div class="muted" style="margin-bottom:12px">SOP §5 — every classified issue routes to one responsible team with a named initial owner.</div>'+
    '<table><thead><tr><th>Issue type</th><th>Responsible team</th><th>Initial owner</th></tr></thead><tbody>'+rows+'</tbody></table></div>'+
    '<div class="card" style="margin-bottom:14px"><h4 style="margin-bottom:4px;font-size:15px">Priority &amp; TAT</h4>'+
    '<div class="muted" style="margin-bottom:12px">SOP §8 — TAT drives the countdown, at-risk warning and breach flag on every ticket.</div>'+
    '<table><thead><tr><th>Priority</th><th>Example</th><th>TAT</th></tr></thead><tbody>'+tat+'</tbody></table></div>'+
    '<div class="card"><h4 style="margin-bottom:4px;font-size:15px">Ticket status flow</h4>'+
    '<div class="muted" style="margin-bottom:12px">SOP §11</div><div style="display:flex;gap:8px;flex-wrap:wrap">'+
    META.flow.map(function(s,i){return '<span class="pill p-mut">'+(i+1)+'. '+esc(s.replace(/_/g,' '))+'</span>';}).join('<span class="muted">→</span>')+'</div></div>';}

/* ---------- admin portal ----------
   goAdmin only auto-fetches on the FIRST visit to a sub-tab: fetch-then-render
   is async, and if it re-rendered on every visit it could land while the admin
   is mid-fill on a form on a slow connection, silently wiping their input
   (a real double-render race, not hypothetical - caught by hand-testing this
   exact flow). Revisits show cached data instantly; "Refresh" re-fetches
   explicitly. Actions (create/update) still refresh immediately afterward -
   that's a deliberate, user-initiated reload of a form that just submitted,
   not a background one racing live typing. */
function goAdmin(t){ADMIN_TAB=t;render();if(!ADMIN_LOADED[t])loadAdminSection(t);}
function loadAdminSection(t){
  if(t==='teams')api('GET','/admin/teams').then(function(d){ADMIN_TEAMS=d;ADMIN_LOADED.teams=true;if(ADMIN_TAB==='teams')render();});
  else if(t==='categories')api('GET','/admin/teams').then(function(d){ADMIN_TEAMS=d;
    api('GET','/admin/categories').then(function(d2){ADMIN_CATEGORIES=d2;ADMIN_LOADED.categories=true;if(ADMIN_TAB==='categories')render();});});
  else if(t==='sla')api('GET','/admin/sla').then(function(d){ADMIN_SLA=d;ADMIN_LOADED.sla=true;if(ADMIN_TAB==='sla')render();});
  else if(t==='users')api('GET','/admin/roles').then(function(r){ADMIN_ROLES=r;
    api('GET','/users').then(function(d){ADMIN_USERS=d;ADMIN_LOADED.users=true;if(ADMIN_TAB==='users')render();});});
  else if(t==='geo')api('GET','/admin/districts').then(function(d){ADMIN_DISTRICTS=d;
    api('GET','/admin/zones').then(function(z){ADMIN_ZONES=z;
      api('GET','/admin/mandals').then(function(m){ADMIN_MANDALS=m;ADMIN_LOADED.geo=true;if(ADMIN_TAB==='geo')render();});});});
  else if(t==='vehicles')api('GET','/admin/vehicles').then(function(d){ADMIN_VEHICLES=d;ADMIN_LOADED.vehicles=true;if(ADMIN_TAB==='vehicles')render();});
  else if(t==='audit')api('GET','/admin/audit').then(function(d){ADMIN_AUDIT=d;ADMIN_LOADED.audit=true;if(ADMIN_TAB==='audit')render();});}
function viewAdmin(){
  var subs=[['teams','Teams'],['categories','Categories'],['geo','Geography'],['vehicles','Vehicles'],['sla','SLA & TAT'],['users','Users'],['audit','Audit Log']];
  var bar='<div class="tabs" style="margin-bottom:12px">'+subs.map(function(s){return '<button class="tab'+(ADMIN_TAB===s[0]?' on':'')+'" onclick="goAdmin(\''+s[0]+'\')">'+s[1]+'</button>';}).join('')+
    '<button class="btn o sm" style="margin-left:auto" onclick="loadAdminSection(ADMIN_TAB)">&#8635; Refresh</button></div>';
  var body='';
  if(!ADMIN_LOADED[ADMIN_TAB])body='<div class="card"><div class="empty">Loading…</div></div>';
  else if(ADMIN_TAB==='teams')body=viewAdminTeams();
  else if(ADMIN_TAB==='categories')body=viewAdminCategories();
  else if(ADMIN_TAB==='geo')body=viewAdminGeo();
  else if(ADMIN_TAB==='vehicles')body=viewAdminVehicles();
  else if(ADMIN_TAB==='sla')body=viewAdminSla();
  else if(ADMIN_TAB==='users')body=viewAdminUsers();
  else if(ADMIN_TAB==='audit')body=viewAdminAudit();
  return bar+body;}

function viewAdminTeams(){
  var rows=ADMIN_TEAMS.map(function(t){
    return '<tr><td><b>'+esc(t.code)+'</b></td><td>'+esc(t.name)+'</td>'+
      '<td>'+(t.is_active?'<span class="pill p-ok">Active</span>':'<span class="pill p-mut">Inactive</span>')+'</td>'+
      '<td style="display:flex;gap:6px"><button class="btn o sm" onclick="adminRenameTeam(\''+t.code+'\')">Rename</button>'+
      '<button class="btn '+(t.is_active?'r':'g')+' sm" onclick="adminToggleTeam(\''+t.code+'\','+(!t.is_active)+')">'+(t.is_active?'Deactivate':'Activate')+'</button></td></tr>';
  }).join('');
  return '<div class="card" style="margin-bottom:14px"><h4 style="margin-bottom:10px;font-size:14px">Teams</h4>'+
    '<div style="overflow-x:auto"><table><thead><tr><th>Code</th><th>Name</th><th>Status</th><th></th></tr></thead><tbody>'+rows+'</tbody></table></div></div>'+
    '<div class="card"><h4 style="margin-bottom:10px;font-size:14px">Add team</h4><div class="grid3">'+
    '<div class="fld"><label>Code</label><input id="at_code" placeholder="PHARMACY"></div>'+
    '<div class="fld"><label>Name</label><input id="at_name" placeholder="Pharmacy Team"></div>'+
    '<div class="fld" style="display:flex;align-items:flex-end"><button class="btn" onclick="adminCreateTeam()">Add team</button></div>'+
    '</div></div>';}
function adminCreateTeam(){
  var code=gv('at_code'),name=gv('at_name');
  if(!code||!name)return toast('Code and name are required');
  api('POST','/admin/teams',{code:code,name:name}).then(function(){toast('Team added');loadAdminSection('teams');})
   .catch(function(e){toast(typeof e==='string'?e:'Failed');});}
function adminRenameTeam(code){var name=prompt('New name for '+code+':');if(!name)return;
  api('PUT','/admin/teams/'+code,{name:name}).then(function(){toast('Renamed');loadAdminSection('teams');})
   .catch(function(e){toast(typeof e==='string'?e:'Failed');});}
function adminToggleTeam(code,active){
  api('PUT','/admin/teams/'+code,{is_active:active}).then(function(){toast(active?'Activated':'Deactivated');loadAdminSection('teams');})
   .catch(function(e){toast(typeof e==='string'?e:'Failed');});}

function viewAdminCategories(){
  var teamOpts=function(sel){return ADMIN_TEAMS.filter(function(t){return t.is_active;}).map(function(t){return '<option value="'+t.code+'"'+(t.code===sel?' selected':'')+'>'+esc(t.name)+'</option>';}).join('');};
  var rows=ADMIN_CATEGORIES.map(function(c){
    return '<tr><td><b>'+esc(c.code)+'</b></td><td>'+esc(c.label)+'</td>'+
      '<td><select id="ac_team_'+c.code+'">'+teamOpts(c.team_code)+'</select> <button class="btn o sm" onclick="adminMoveCategory(\''+c.code+'\')">Apply</button></td>'+
      '<td>'+esc(c.default_owner||'')+'</td>'+
      '<td><button class="btn '+(c.route_by_zone?'g':'o')+' sm" onclick="adminToggleRouteByZone(\''+c.code+'\','+(!c.route_by_zone)+')">'+(c.route_by_zone?'Zone-routed':'By category')+'</button></td>'+
      '<td>'+(c.is_active?'<span class="pill p-ok">Active</span>':'<span class="pill p-mut">Inactive</span>')+'</td>'+
      '<td style="display:flex;gap:6px"><button class="btn o sm" onclick="adminEditCategory(\''+c.code+'\')">Edit</button>'+
      '<button class="btn '+(c.is_active?'r':'g')+' sm" onclick="adminToggleCategory(\''+c.code+'\','+(!c.is_active)+')">'+(c.is_active?'Deactivate':'Activate')+'</button></td></tr>';
  }).join('');
  return '<div class="card" style="margin-bottom:14px"><h4 style="margin-bottom:10px;font-size:14px">Categories</h4>'+
    '<div class="muted" style="margin-bottom:10px">"Zone-routed" categories send tickets to the Mandal\'s Zone team (if configured) instead of the category\'s own team - use for issues needing physical dispatch (Machine, Fleet, Field). Leave centrally-handled categories (Application, Network, ...) on "By category".</div>'+
    '<div style="overflow-x:auto"><table><thead><tr><th>Code</th><th>Label</th><th>Team</th><th>Owner</th><th>Routing</th><th>Status</th><th></th></tr></thead><tbody>'+rows+'</tbody></table></div></div>'+
    '<div class="card"><h4 style="margin-bottom:10px;font-size:14px">Add category</h4><div class="grid3">'+
    '<div class="fld"><label>Code</label><input id="ac_code" placeholder="MEDSTOCK"></div>'+
    '<div class="fld"><label>Label</label><input id="ac_label" placeholder="Medicine stock issue"></div>'+
    '<div class="fld"><label>Team</label><select id="ac_new_team">'+teamOpts()+'</select></div>'+
    '<div class="fld"><label>Default owner</label><input id="ac_owner" placeholder="Pharmacist"></div>'+
    '<div class="fld" style="display:flex;align-items:flex-end"><button class="btn" onclick="adminCreateCategory()">Add category</button></div>'+
    '</div></div>';}
function adminCreateCategory(){
  var code=gv('ac_code'),label=gv('ac_label'),team=document.getElementById('ac_new_team').value,owner=gv('ac_owner');
  if(!code||!label)return toast('Code and label are required');
  api('POST','/admin/categories',{code:code,label:label,team_code:team,default_owner:owner}).then(function(){toast('Category added');loadAdminSection('categories');})
   .catch(function(e){toast(typeof e==='string'?e:'Failed');});}
function adminMoveCategory(code){
  var team=document.getElementById('ac_team_'+code).value;
  api('PUT','/admin/categories/'+code,{team_code:team}).then(function(){toast('Re-routed');loadAdminSection('categories');})
   .catch(function(e){toast(typeof e==='string'?e:'Failed');});}
function adminEditCategory(code){
  var c=ADMIN_CATEGORIES.find(function(x){return x.code===code;});
  var label=prompt('Label:',c.label);if(label===null)return;
  var owner=prompt('Default owner:',c.default_owner||'');if(owner===null)return;
  api('PUT','/admin/categories/'+code,{label:label,default_owner:owner}).then(function(){toast('Updated');loadAdminSection('categories');})
   .catch(function(e){toast(typeof e==='string'?e:'Failed');});}
function adminToggleCategory(code,active){
  api('PUT','/admin/categories/'+code,{is_active:active}).then(function(){toast(active?'Activated':'Deactivated');loadAdminSection('categories');})
   .catch(function(e){toast(typeof e==='string'?e:'Failed');});}
function adminToggleRouteByZone(code,routeByZone){
  api('PUT','/admin/categories/'+code,{route_by_zone:routeByZone}).then(function(){toast(routeByZone?'Now zone-routed':'Now routed by category');loadAdminSection('categories');})
   .catch(function(e){toast(typeof e==='string'?e:'Failed');});}

function viewAdminGeo(){
  var districtRows=ADMIN_DISTRICTS.map(function(d){
    return '<tr><td><b>'+esc(d.name)+'</b></td>'+
      '<td>'+(d.is_active?'<span class="pill p-ok">Active</span>':'<span class="pill p-mut">Inactive</span>')+'</td>'+
      '<td style="display:flex;gap:6px"><button class="btn o sm" onclick="adminRenameDistrict('+d.id+')">Rename</button>'+
      '<button class="btn '+(d.is_active?'r':'g')+' sm" onclick="adminToggleDistrict('+d.id+','+(!d.is_active)+')">'+(d.is_active?'Deactivate':'Activate')+'</button></td></tr>';
  }).join('');
  var zoneRows=ADMIN_ZONES.map(function(z){
    return '<tr><td><b>'+esc(z.name)+'</b></td><td>'+esc((META.teams||{})[z.team_code]||z.team_code)+'</td>'+
      '<td>'+(z.is_active?'<span class="pill p-ok">Active</span>':'<span class="pill p-mut">Inactive</span>')+'</td>'+
      '<td><button class="btn '+(z.is_active?'r':'g')+' sm" onclick="adminToggleZone('+z.id+','+(!z.is_active)+')">'+(z.is_active?'Deactivate':'Activate')+'</button></td></tr>';
  }).join('');
  var districtOpts=ADMIN_DISTRICTS.filter(function(d){return d.is_active;}).map(function(d){return '<option value="'+d.id+'">'+esc(d.name)+'</option>';}).join('');
  var zoneOpts='<option value="">No zone (category-default routing)</option>'+ADMIN_ZONES.filter(function(z){return z.is_active;}).map(function(z){return '<option value="'+z.id+'">'+esc(z.name)+'</option>';}).join('');
  var mandalRows=ADMIN_MANDALS.map(function(m){
    var d=ADMIN_DISTRICTS.find(function(x){return x.id===m.district_id;});
    var z=ADMIN_ZONES.find(function(x){return x.id===m.zone_id;});
    return '<tr><td><b>'+esc(m.name)+'</b></td><td>'+esc(d?d.name:m.district_id)+'</td><td>'+esc(z?z.name:'—')+'</td>'+
      '<td>'+(m.is_active?'<span class="pill p-ok">Active</span>':'<span class="pill p-mut">Inactive</span>')+'</td>'+
      '<td><button class="btn '+(m.is_active?'r':'g')+' sm" onclick="adminToggleMandal('+m.id+','+(!m.is_active)+')">'+(m.is_active?'Deactivate':'Activate')+'</button></td></tr>';
  }).join('');
  return '<div class="card" style="margin-bottom:14px"><h4 style="margin-bottom:10px;font-size:14px">Districts</h4>'+
    '<table><thead><tr><th>Name</th><th>Status</th><th></th></tr></thead><tbody>'+districtRows+'</tbody></table></div>'+
    '<div class="card" style="margin-bottom:14px"><div class="grid3">'+
    '<div class="fld"><label>New district name</label><input id="geo_district_name" placeholder="Hyderabad"></div>'+
    '<div class="fld" style="display:flex;align-items:flex-end"><button class="btn" onclick="adminCreateDistrict()">Add district</button></div></div></div>'+

    '<div class="card" style="margin-bottom:14px"><h4 style="margin-bottom:4px;font-size:15px">Zones</h4>'+
    '<div class="muted" style="margin-bottom:10px">A Zone maps a group of Mandals to one responsible Team - only used for categories flagged "zone-routed" on the Categories tab.</div>'+
    '<table><thead><tr><th>Name</th><th>Team</th><th>Status</th><th></th></tr></thead><tbody>'+zoneRows+'</tbody></table></div>'+
    '<div class="card" style="margin-bottom:14px"><div class="grid3">'+
    '<div class="fld"><label>New zone name</label><input id="geo_zone_name" placeholder="South Zone"></div>'+
    '<div class="fld"><label>Team</label><select id="geo_zone_team">'+Object.keys(META.teams).map(function(k){return '<option value="'+k+'">'+esc(META.teams[k])+'</option>';}).join('')+'</select></div>'+
    '<div class="fld" style="display:flex;align-items:flex-end"><button class="btn" onclick="adminCreateZone()">Add zone</button></div></div></div>'+

    '<div class="card" style="margin-bottom:14px"><h4 style="margin-bottom:10px;font-size:14px">Mandals</h4>'+
    '<div style="overflow-x:auto"><table><thead><tr><th>Name</th><th>District</th><th>Zone</th><th>Status</th><th></th></tr></thead><tbody>'+mandalRows+'</tbody></table></div></div>'+
    '<div class="card"><h4 style="margin-bottom:10px;font-size:14px">Add mandal</h4><div class="grid3">'+
    '<div class="fld"><label>Name</label><input id="geo_mandal_name" placeholder="Shamshabad"></div>'+
    '<div class="fld"><label>District</label><select id="geo_mandal_district">'+districtOpts+'</select></div>'+
    '<div class="fld"><label>Zone (optional)</label><select id="geo_mandal_zone">'+zoneOpts+'</select></div>'+
    '<div class="fld" style="display:flex;align-items:flex-end"><button class="btn" onclick="adminCreateMandal()">Add mandal</button></div>'+
    '</div></div>';}
function adminCreateDistrict(){
  var name=gv('geo_district_name');if(!name)return toast('District name is required');
  api('POST','/admin/districts',{name:name}).then(function(){toast('District added');loadAdminSection('geo');})
   .catch(function(e){toast(typeof e==='string'?e:'Failed');});}
function adminRenameDistrict(id){var name=prompt('New name:');if(!name)return;
  api('PUT','/admin/districts/'+id,{name:name}).then(function(){toast('Renamed');loadAdminSection('geo');})
   .catch(function(e){toast(typeof e==='string'?e:'Failed');});}
function adminToggleDistrict(id,active){
  api('PUT','/admin/districts/'+id,{is_active:active}).then(function(){toast(active?'Activated':'Deactivated');loadAdminSection('geo');})
   .catch(function(e){toast(typeof e==='string'?e:'Failed');});}
function adminCreateZone(){
  var name=gv('geo_zone_name'),team=document.getElementById('geo_zone_team').value;
  if(!name)return toast('Zone name is required');
  api('POST','/admin/zones',{name:name,team_code:team}).then(function(){toast('Zone added');loadAdminSection('geo');})
   .catch(function(e){toast(typeof e==='string'?e:'Failed');});}
function adminToggleZone(id,active){
  api('PUT','/admin/zones/'+id,{is_active:active}).then(function(){toast(active?'Activated':'Deactivated');loadAdminSection('geo');})
   .catch(function(e){toast(typeof e==='string'?e:'Failed');});}
function adminCreateMandal(){
  var name=gv('geo_mandal_name'),did=document.getElementById('geo_mandal_district').value,zid=document.getElementById('geo_mandal_zone').value;
  if(!name||!did)return toast('Mandal name and district are required');
  api('POST','/admin/mandals',{name:name,district_id:+did,zone_id:zid?+zid:null}).then(function(){toast('Mandal added');loadAdminSection('geo');})
   .catch(function(e){toast(typeof e==='string'?e:'Failed');});}
function adminToggleMandal(id,active){
  api('PUT','/admin/mandals/'+id,{is_active:active}).then(function(){toast(active?'Activated':'Deactivated');loadAdminSection('geo');})
   .catch(function(e){toast(typeof e==='string'?e:'Failed');});}

function viewAdminVehicles(){
  var rows=ADMIN_VEHICLES.map(function(v){
    return '<tr><td><b>'+esc(v.registration_no)+'</b></td>'+
      '<td>'+(v.is_active?'<span class="pill p-ok">Active</span>':'<span class="pill p-mut">Inactive</span>')+'</td>'+
      '<td><button class="btn '+(v.is_active?'r':'g')+' sm" onclick="adminToggleVehicle('+v.id+','+(!v.is_active)+')">'+(v.is_active?'Deactivate':'Activate')+'</button></td></tr>';
  }).join('');
  return '<div class="card" style="margin-bottom:14px"><h4 style="margin-bottom:4px;font-size:15px">Vehicles</h4>'+
    '<div class="muted" style="margin-bottom:10px">A registry entry only tracks the registration number - MMU vehicles move between Mandals, so location is captured fresh on each ticket and never stored here.</div>'+
    '<div style="overflow-x:auto"><table><thead><tr><th>Registration no.</th><th>Status</th><th></th></tr></thead><tbody>'+rows+'</tbody></table></div></div>'+
    '<div class="card"><h4 style="margin-bottom:10px;font-size:14px">Add vehicle</h4><div class="grid3">'+
    '<div class="fld"><label>Registration number</label><input id="veh_reg" placeholder="AP39UL4276"></div>'+
    '<div class="fld" style="display:flex;align-items:flex-end"><button class="btn" onclick="adminCreateVehicle()">Add vehicle</button></div>'+
    '</div></div>';}
function adminCreateVehicle(){
  var reg=gv('veh_reg');if(!reg)return toast('Registration number is required');
  api('POST','/admin/vehicles',{registration_no:reg}).then(function(){toast('Vehicle added');loadAdminSection('vehicles');})
   .catch(function(e){toast(typeof e==='string'?e:'Failed');});}
function adminToggleVehicle(id,active){
  api('PUT','/admin/vehicles/'+id,{is_active:active}).then(function(){toast(active?'Activated':'Deactivated');loadAdminSection('vehicles');})
   .catch(function(e){toast(typeof e==='string'?e:'Failed');});}

function viewAdminSla(){
  if(!ADMIN_SLA)return '<div class="card"><div class="empty">Loading…</div></div>';
  var tat=ADMIN_SLA.tat||{},sla=ADMIN_SLA.sla||{};
  return '<div class="card" style="margin-bottom:14px"><h4 style="margin-bottom:4px;font-size:15px">TAT per priority (minutes)</h4>'+
    '<div class="muted" style="margin-bottom:12px">Approved SLA/TAT values — editable once the official SLA is signed off.</div><div class="grid3">'+
    Object.keys(tat).map(function(k){return '<div class="fld"><label>'+k+'</label><input id="sla_tat_'+k+'" value="'+esc(tat[k])+'"></div>';}).join('')+
    '</div></div>'+
    '<div class="card"><h4 style="margin-bottom:4px;font-size:15px">SLA tiers</h4>'+
    '<div class="muted" style="margin-bottom:12px">A ticket goes AT RISK / CRITICAL once time-left drops to or below max(floor minutes, TAT &times; fraction).</div>'+
    '<div class="grid3">'+
    '<div class="fld"><label>At-risk floor (min)</label><input id="sla_arm" value="'+esc(sla.at_risk_minutes)+'"></div>'+
    '<div class="fld"><label>At-risk fraction (0-1)</label><input id="sla_arf" value="'+esc(sla.at_risk_fraction)+'"></div>'+
    '<div class="fld"><label>Critical floor (min)</label><input id="sla_cm" value="'+esc(sla.critical_minutes)+'"></div>'+
    '<div class="fld"><label>Critical fraction (0-1)</label><input id="sla_cf" value="'+esc(sla.critical_fraction)+'"></div>'+
    '<div class="fld"><label>Resolved follow-up (hours)</label><input id="sla_rfh" value="'+esc(sla.resolved_followup_hours)+'"></div>'+
    '<div class="fld"><label>Reopen window (hours)</label><input id="sla_rwh" value="'+esc(sla.reopen_window_hours)+'"></div>'+
    '<div class="fld" style="display:flex;align-items:flex-end"><button class="btn" onclick="adminSaveSla()">Save</button></div>'+
    '</div></div>'+
    '<div class="card"><h4 style="margin-bottom:4px;font-size:15px">VIP escalation keywords</h4>'+
    '<div class="muted" style="margin-bottom:12px">A new ticket auto-escalates to P1 if the problem text contains any of these (case-insensitive), or if the VIP box is checked at registration.</div>'+
    '<div class="fld"><label>Keywords (comma-separated)</label><input id="sla_vipkw" value="'+esc((ADMIN_SLA.vip_keywords||[]).join(', '))+'"></div>'+
    '<button class="btn o sm" onclick="adminSaveVipKeywords()">Save keywords</button></div>';}
function adminSaveSla(){
  var tat={};Object.keys(ADMIN_SLA.tat||{}).forEach(function(k){tat[k]=gv('sla_tat_'+k);});
  var sla={at_risk_minutes:gv('sla_arm'),at_risk_fraction:gv('sla_arf'),critical_minutes:gv('sla_cm'),critical_fraction:gv('sla_cf'),resolved_followup_hours:gv('sla_rfh'),reopen_window_hours:gv('sla_rwh')};
  api('PUT','/admin/sla',{tat:tat,sla:sla}).then(function(){toast('Saved');loadAdminSection('sla');})
   .catch(function(e){toast(typeof e==='string'?e:'Failed');});}
function adminSaveVipKeywords(){
  var keywords=gv('sla_vipkw').split(',').map(function(s){return s.trim();}).filter(Boolean);
  api('PUT','/admin/sla',{vip_keywords:keywords}).then(function(){toast('Saved');loadAdminSection('sla');})
   .catch(function(e){toast(typeof e==='string'?e:'Failed');});}

function viewAdminUsers(){
  var roleOpts=function(sel){return ADMIN_ROLES.map(function(r){return '<option value="'+r+'"'+(r===sel?' selected':'')+'>'+esc(roleLabel(r))+'</option>';}).join('');};
  var mgrName=function(id){var u=ADMIN_USERS.find(function(x){return x.id===id;});return u?u.name:'';};
  var rows=ADMIN_USERS.map(function(u){
    return '<tr><td><b>'+esc(u.username)+'</b></td><td>'+esc(u.name)+'</td>'+
      '<td><select id="au_role_'+u.id+'">'+roleOpts(u.role)+'</select> <button class="btn o sm" onclick="adminChangeRole('+u.id+')">Apply</button></td>'+
      '<td>'+esc(u.hr_emp_code||'—')+'</td>'+
      '<td>'+esc(u.reporting_manager_id?mgrName(u.reporting_manager_id):'—')+'</td>'+
      '<td><button class="btn '+(u.is_team_manager?'g':'o')+' sm" onclick="adminToggleTeamManager('+u.id+','+(!u.is_team_manager)+')">'+(u.is_team_manager?'Team Manager':'Make manager')+'</button></td>'+
      '<td>'+(u.active?'<span class="pill p-ok">Active</span>':'<span class="pill p-mut">Inactive</span>')+'</td>'+
      '<td style="display:flex;gap:6px"><button class="btn o sm" onclick="adminResetPassword('+u.id+')">Reset password</button>'+
      '<button class="btn '+(u.active?'r':'g')+' sm" onclick="adminToggleUser('+u.id+','+(!u.active)+')">'+(u.active?'Deactivate':'Activate')+'</button></td></tr>';
  }).join('');
  var mgrOpts='<option value="">No reporting manager</option>'+ADMIN_USERS.filter(function(u){return u.active;}).map(function(u){return '<option value="'+u.id+'">'+esc(u.name)+' ('+esc(u.username)+')</option>';}).join('');
  return '<div class="card" style="margin-bottom:14px"><h4 style="margin-bottom:10px;font-size:14px">Users</h4>'+
    '<div style="overflow-x:auto"><table><thead><tr><th>Username</th><th>Name</th><th>Role</th><th>HR code</th><th>Reports to</th><th>Dispatch</th><th>Status</th><th></th></tr></thead><tbody>'+rows+'</tbody></table></div></div>'+
    '<div class="card"><h4 style="margin-bottom:10px;font-size:14px">Add user</h4><div class="grid3">'+
    '<div class="fld"><label>Username</label><input id="au_uname" placeholder="tech6"></div>'+
    '<div class="fld"><label>Name</label><input id="au_name"></div>'+
    '<div class="fld"><label>Role</label><select id="au_new_role">'+roleOpts()+'</select></div>'+
    '<div class="fld"><label>Phone</label><input id="au_phone"></div>'+
    '<div class="fld"><label>Temporary password</label><input id="au_pw" placeholder="min 8 characters"></div>'+
    '<div class="fld"><label>HR employee code</label><input id="au_hr_code" placeholder="EMP1234"></div>'+
    '<div class="fld"><label>Reporting manager</label><select id="au_report_to">'+mgrOpts+'</select></div>'+
    '<div class="fld" style="display:flex;align-items:center;gap:8px"><input type="checkbox" id="au_is_manager" style="width:auto"> <label style="margin:0;text-transform:none;font-size:13px;font-weight:600;color:var(--ink2)">Team Manager for this role</label></div>'+
    '<div class="fld" style="display:flex;align-items:flex-end"><button class="btn" onclick="adminCreateUser()">Add user</button></div>'+
    '</div></div>';}
function adminCreateUser(){
  var username=gv('au_uname'),name=gv('au_name'),role=document.getElementById('au_new_role').value,phone=gv('au_phone'),pw=gv('au_pw'),
      hrCode=gv('au_hr_code'),reportTo=document.getElementById('au_report_to').value,isManager=document.getElementById('au_is_manager').checked;
  if(!username||!name||!pw)return toast('Username, name and password are required');
  api('POST','/admin/users',{username:username,name:name,role:role,phone:phone,password:pw,
      hr_emp_code:hrCode,reporting_manager_id:reportTo?+reportTo:null,is_team_manager:isManager})
   .then(function(){toast('User created');loadAdminSection('users');})
   .catch(function(e){toast(typeof e==='string'?e:'Failed');});}
function adminChangeRole(id){var role=document.getElementById('au_role_'+id).value;
  api('PUT','/admin/users/'+id,{role:role}).then(function(){toast('Role updated');loadAdminSection('users');})
   .catch(function(e){toast(typeof e==='string'?e:'Failed');});}
function adminToggleUser(id,active){
  api('PUT','/admin/users/'+id,{active:active}).then(function(){toast(active?'Activated':'Deactivated');loadAdminSection('users');})
   .catch(function(e){toast(typeof e==='string'?e:'Failed');});}
function adminToggleTeamManager(id,isManager){
  api('PUT','/admin/users/'+id,{is_team_manager:isManager}).then(function(){toast(isManager?'Now a Team Manager':'Team Manager removed');loadAdminSection('users');})
   .catch(function(e){toast(typeof e==='string'?e:'Failed');});}
function adminResetPassword(id){var pw=prompt('New temporary password (min 8 characters):');if(!pw)return;
  api('PUT','/admin/users/'+id,{password:pw}).then(function(){toast('Password reset');})
   .catch(function(e){toast(typeof e==='string'?e:'Failed');});}

function viewAdminAudit(){
  if(!ADMIN_AUDIT.length)return '<div class="card"><div class="empty">No admin actions recorded yet.</div></div>';
  var rows=ADMIN_AUDIT.map(function(e){
    return '<tr><td>'+esc(e.at)+'</td><td>'+esc(e.actor)+'<div class="muted">'+esc(e.actor_role)+'</div></td>'+
      '<td>'+esc(e.action)+'</td><td>'+esc(e.entity_type)+' · '+esc(e.entity_id)+'</td><td>'+esc(e.detail||'')+'</td></tr>';
  }).join('');
  return '<div class="card"><h4 style="margin-bottom:10px;font-size:14px">Recent admin activity</h4>'+
    '<div style="overflow-x:auto"><table><thead><tr><th>When</th><th>Who</th><th>Action</th><th>Entity</th><th>Detail</th></tr></thead><tbody>'+rows+'</tbody></table></div></div>';}

if(TOK){boot();}