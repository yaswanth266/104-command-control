var API='/cccapi', TOK=sessionStorage.getItem('ccc_tok')||'', ME=null, META=null, TAB='queue', ROWS=[], ROWTOTAL=0, DASH=null,
  FILT={status:'open',scope:'',priority:'',category:'',mmu_vehicle:'',district:'',date_from:'',date_to:'',q:'',page:1,page_size:50},
  NOTIFS=[], NOTIF_OPEN=false, POLL_TIMER=null, CLOCK_TIMER=null;
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
  t.push(['matrix','Routing Matrix']);return t;}
function render(){document.getElementById('tabs').innerHTML=tabsFor().map(function(x){return '<button class="tab'+(TAB===x[0]?' on':'')+'" onclick="go(\''+x[0]+'\')">'+esc(x[1])+'</button>';}).join('');
  var b=document.getElementById('body');
  if(TAB==='new'){b.innerHTML=viewNew();setTimeout(previewRoute,0);}
  else if(TAB==='dash')b.innerHTML=viewDash();
  else if(TAB==='matrix')b.innerHTML=viewMatrix();
  else b.innerHTML=viewQueue();}
function go(t){TAB=t;render();load();}
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
    f('scope','','&mdash;')+f('scope','breach','TAT Breached')+f('scope','risk','At Risk')+f('scope','critical','Critical')+f('scope','escalated','Escalated')+'</div>';
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
      '<td><span class="pill p-'+esc(t.priority)+'">'+esc(t.priority)+'</span></td>'+
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
    '<div class="fld"><label>MMU / Vehicle number *</label><input id="f_veh" placeholder="AP39UL4276"></div>'+
    '<div class="fld"><label>District</label><input id="f_dist"></div>'+
    '<div class="fld"><label>Location</label><input id="f_loc" placeholder="Mandal / village"></div>'+
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
   '<div class="route" id="rpre"></div>'+
   '<button class="btn" style="margin-top:14px" onclick="createT()">Create ticket &amp; route</button></div>';}
function previewRoute(){var c=document.getElementById('f_cat').value,r=META.routing[c];
  document.getElementById('rpre').innerHTML='Routes to <b>'+esc(META.teams[r.team])+'</b> &mdash; initial owner <b>'+esc(r.owner)+'</b>';}
function createT(){
  var g=function(i){var e=document.getElementById(i);return e?e.value.trim():'';};
  if(!g('f_prob'))return toast('Nature of the problem is required');
  api('POST','/ticket',{mmu_vehicle:g('f_veh'),district:g('f_dist'),location:g('f_loc'),caller_name:g('f_cname'),
    caller_phone:g('f_cph'),equipment:g('f_eq'),problem:g('f_prob'),error_code:g('f_err'),impact:g('f_imp'),
    category:g('f_cat'),priority:g('f_pri')})
  .then(function(d){toast('Ticket '+d.ticket_no+' created → '+d.team);TAB='queue';render();load();})
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
  if((ME.role==='CC_MANAGER'||ME.role==='CALL_TAKER')&&t.status==='CLOSED')A.push('<button class="btn o" onclick="reopenT('+t.id+')">Reopen</button>');
  var reroute=(ME.role==='CC_MANAGER'||ME.role==='CALL_TAKER')?
    ('<div class="grid2" style="margin-top:12px"><div class="fld"><label>Re-route to team</label><select id="a_team">'+
      Object.keys(META.teams).map(function(k){return '<option value="'+k+'"'+(k===t.team?' selected':'')+'>'+esc(META.teams[k])+'</option>';}).join('')+
      '</select><button class="btn o sm" style="margin-top:7px" onclick="act('+t.id+',\'reassign\')">Apply re-route</button></div>'+
      '<div class="fld"><label>Change priority</label><select id="a_pri">'+Object.keys(META.priority).map(function(k){return '<option value="'+k+'"'+(k===t.priority?' selected':'')+'>'+k+'</option>';}).join('')+
      '</select><button class="btn o sm" style="margin-top:7px" onclick="act('+t.id+',\'repriority\')">Apply priority</button></div></div>'):'';
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
    '<div class="sh"><div><div style="font-size:19px;font-weight:800">'+esc(t.ticket_no)+' &middot; '+esc(t.category_label)+'</div>'+
      '<div style="font-size:12.5px;opacity:.9;margin-top:3px">'+esc(t.mmu_vehicle||'—')+' &middot; '+esc(t.district||'')+' &middot; '+esc(t.team_label)+' &middot; '+esc(t.priority)+'</div></div>'+
      '<button class="x" onclick="closeT()">&times;</button></div><div class="sb">'+
    '<div style="display:flex;gap:9px;flex-wrap:wrap;margin-bottom:14px"><span class="pill p-mut">'+esc((t.status||'').replace(/_/g,' '))+'</span>'+tatPill(t).replace('<span ','<span id="modalTat" ')+
      (t.escalated?'<span class="pill p-crit">ESCALATED</span>':'')+'<span class="pill p-mut">TAT '+esc(t.tat_mins)+' min</span></div>'+
    '<div class="grid2"><div>'+row('Problem',t.problem)+row('Equipment',t.equipment)+row('Error code',t.error_code)+row('Impact',t.impact)+
      row('Caller',(t.caller_name||'')+(t.caller_phone?(' · '+t.caller_phone):''))+row('Location',t.location)+'</div>'+
     '<div>'+row('Created',t.created_at)+row('Due (TAT)',t.due_at)+row('Acknowledged',t.acknowledged_at)+row('Resolved',t.resolved_at)+
      row('Confirmed by',t.confirmed_by)+row('Closed',t.closed_at)+row('Owner',t.owner)+'</div></div>'+
    form+reroute+
    '<div style="display:flex;gap:9px;flex-wrap:wrap;margin-top:14px">'+A.join('')+'</div>'+
    '<h4 style="margin:18px 0 8px;font-size:14px">Audit trail</h4><div class="tl">'+
      (evs||[]).map(function(e){return '<div class="e"><b>'+esc(e.action)+'</b> — '+esc(e.detail||'')+'<div class="muted">'+esc(e.at)+' · '+esc(e.actor)+' ('+esc(e.actor_role)+')</div></div>';}).join('')+
    '</div></div></div></div>';
  if(MODAL_TICK)clearInterval(MODAL_TICK);
  if(t.status!=='CLOSED')MODAL_TICK=setInterval(function(){updateModalCountdown(t);},30000);}
function act(id,a){
  var g=function(i){var e=document.getElementById(i);return e?e.value.trim():undefined;};
  var b={id:id,action:a,diagnosis:g('a_diag'),action_taken:g('a_act'),root_cause:g('a_rc'),parts:g('a_parts'),
         resolution:g('a_res'),pending_reason:g('a_pend'),confirmed_by:g('a_conf'),note:g('a_note'),
         team:g('a_team'),priority:g('a_pri')};
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

if(TOK){boot();}