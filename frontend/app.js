'use strict';
const $ = id => document.getElementById(id);
const cfg = window.ATTENDFLOW || {};
let token = '', challenge = null, stream = null, employees = [], attendance = [], tz = 'Asia/Kolkata', busy = false;
let clearResultTimer, lastSession = null;
function notify(message, error=false) { $('notice').textContent=message; $('notice').classList.toggle('error',error); }
function dateHere(){ return new Intl.DateTimeFormat('en-CA',{timeZone:tz,year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date()); }
function fmt(value){return value ? new Intl.DateTimeFormat('en-IN',{timeZone:tz,dateStyle:'medium',timeStyle:'short'}).format(new Date(value)) : '—';}
async function cognito(target,body){
  const r=await fetch(`https://cognito-idp.${cfg.region}.amazonaws.com/`,{method:'POST',headers:{'Content-Type':'application/x-amz-json-1.1','X-Amz-Target':'AWSCognitoIdentityProviderService.'+target},body:JSON.stringify(body)});
  const d=await r.json();if(!r.ok)throw new Error(d.message||'Sign in failed.');return d;
}
async function api(path,method='GET',body){
  if(!token)throw new Error('Sign in first.');
  const r=await fetch(cfg.apiUrl+path,{method,headers:{Authorization:token,'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});
  const d=await r.json();if(!r.ok){if(r.status===401)logout();throw new Error(d.error||d.message||'Request failed.');}return d;
}
function stopCamera(){if(stream)stream.getTracks().forEach(t=>t.stop());stream=null;$('video').srcObject=null;$('cameraHint').classList.remove('hidden');$('captureButton').disabled=true;}
function logout(){employees=[];attendance=[];['peopleRows','attendanceRows','reportList','stats'].forEach(id=>$(id).replaceChildren());$('resultTitle').textContent='Ready when you are.';$('resultText').textContent='';$('resultTime').textContent='';token='';lastSession=null;$('checkCapture').classList.add('hidden');challenge=null;stopCamera();$('workspace').classList.add('hidden');$('login').classList.remove('hidden');$('logout').classList.add('hidden');$('password').value='';$('newPassword').value='';}
$('logout').onclick=logout;
$('loginForm').onsubmit=async e=>{e.preventDefault();const button=e.submitter;button.disabled=true;$('loginStatus').textContent='Signing in…';try{
  if(!cfg.clientId||!cfg.apiUrl)throw new Error('Run scripts/setup.py configure and publish frontend/config.js first.');
  let result;
  if(challenge){result=await cognito('RespondToAuthChallenge',{ClientId:cfg.clientId,ChallengeName:'NEW_PASSWORD_REQUIRED',Session:challenge.Session,ChallengeResponses:{USERNAME:challenge.username,NEW_PASSWORD:$('newPassword').value}});}
  else result=await cognito('InitiateAuth',{ClientId:cfg.clientId,AuthFlow:'USER_PASSWORD_AUTH',AuthParameters:{USERNAME:$('username').value.trim(),PASSWORD:$('password').value}});
  if(result.ChallengeName==='NEW_PASSWORD_REQUIRED'){
    challenge={...result,username:result.ChallengeParameters.USER_ID_FOR_SRP||$('username').value.trim()};$('newPasswordLabel').classList.remove('hidden');$('newPassword').required=true;$('loginStatus').textContent='Choose a new password: 12+ characters with uppercase, lowercase, number and symbol.';return;
  }
  if(!result.AuthenticationResult)throw new Error('This sign-in challenge is not supported by the demo portal. Contact your administrator.');
  token=result.AuthenticationResult.IdToken;const me=await api('/me');tz=me.timezone;
  document.querySelectorAll('.admin-only').forEach(el=>el.classList.toggle('hidden',!me.roles.includes('Admin')));
  $('login').classList.add('hidden');$('workspace').classList.remove('hidden');$('logout').classList.remove('hidden');$('zone').textContent=tz;$('today').textContent=new Intl.DateTimeFormat('en-IN',{timeZone:tz,dateStyle:'full'}).format(new Date());
  $('loginStatus').textContent='';$('password').value='';$('newPassword').value='';challenge=null;
  ['fromDate','toDate','manualDate','reportDate'].forEach(id=>$(id).value=dateHere());document.querySelector('[name=start_date]').value=dateHere();
  switchTab('capture');
  if(me.roles.includes('Admin'))await Promise.all([loadPeople(),loadPolicy()]);
}catch(err){$('loginStatus').textContent=err.message;}finally{button.disabled=false;}};
function switchTab(tab){document.querySelectorAll('.tab').forEach(el=>el.classList.toggle('hidden',el.id!==tab));document.querySelectorAll('nav button').forEach(el=>el.classList.toggle('active',el.dataset.tab===tab));}
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>{switchTab(b.dataset.tab);if(b.dataset.tab==='attendance')safe(loadAttendance);if(b.dataset.tab==='reports')safe(loadReports);});
async function safe(fn){try{await fn();}catch(e){notify(e.message,true);}}
$('startCamera').onclick=()=>safe(async()=>{stopCamera();stream=await navigator.mediaDevices.getUserMedia({video:{facingMode:'user',width:{ideal:960},height:{ideal:720}},audio:false});$('video').srcObject=stream;await $('video').play();$('cameraHint').classList.add('hidden');$('captureButton').disabled=false;});
$('stopCamera').onclick=stopCamera;
window.addEventListener('pagehide',stopCamera);
async function snapshot(){if(!stream||!$('video').videoWidth)throw new Error('Start the camera and wait for its preview.');const c=$('canvas');c.width=$('video').videoWidth;c.height=$('video').videoHeight;c.getContext('2d').drawImage($('video'),0,0);return new Promise(resolve=>c.toBlob(resolve,'image/jpeg',.86));}
async function submitImage(blob,mode){
  if(busy)throw new Error('Wait for the current capture to finish.');
  if(!blob||blob.size>3*1024*1024)throw new Error('Choose a JPEG/PNG image under 3 MB.');
  busy=true;clearTimeout(clearResultTimer);$('captureButton').disabled=true;$('captureStatus').textContent='Uploading securely…';const start=performance.now();
  try{
    const j=await api('/sessions','POST',{mode,action:document.querySelector('[name=action]:checked').value,employee_id:$('enrollEmployee').value,content_type:blob.type});
    lastSession=j.session_id;$('checkCapture').classList.remove('hidden');
    const form=new FormData();Object.entries(j.upload.fields).forEach(([k,v])=>form.append(k,v));form.append('file',blob);
    const upload=await fetch(j.upload.url,{method:'POST',body:form});if(!upload.ok)throw new Error('Photo upload failed. Check S3 CORS and upload permissions.');
    $('captureStatus').textContent='Checking your photo…';
    for(let i=0;i<60;i++){
      const state=await api('/sessions/'+j.session_id);
      if(state.state==='DONE'){
        const r=state.result;$('resultTitle').textContent=r.name;$('resultText').textContent=r.message||`${r.action==='in'?'Clocked in':'Clocked out'} · ${r.status}`;$('resultTime').textContent=r.time?fmt(r.time):'';
        $('captureStatus').textContent=`Completed in ${((performance.now()-start)/1000).toFixed(1)} seconds.`;
        if(mode==='enroll')await loadPeople();
        clearResultTimer=setTimeout(()=>{$('resultTitle').textContent='Ready when you are.';$('resultText').textContent='Capture the next attendance event.';$('resultTime').textContent='';},15000);return;
      }
      if(['REJECTED','FAILED','EXPIRED'].includes(state.state))throw new Error(state.error||'Capture expired. Ask your administrator.');
      if(i===3)$('captureStatus').textContent='Still processing. Please wait; do not capture again.';
      await new Promise(r=>setTimeout(r,1000));
    }
    throw new Error(`Processing is delayed. Session ${j.session_id}. Check attendance with your administrator before recapturing.`);
  }finally{busy=false;$('captureButton').disabled=!stream;}
}
async function capture(mode,blob){try{await submitImage(blob||await snapshot(),mode);}catch(e){$('captureStatus').textContent=e.message;notify(e.message,true);}}
$('captureButton').onclick=()=>capture('attendance');$('enrollCamera').onclick=()=>capture('enroll');$('enrollUpload').onclick=()=>{const file=$('enrollFile').files[0];if(!file){notify('Choose a photo first.',true);return;}capture('enroll',file);};
function cell(row,text){const td=document.createElement('td');td.textContent=text;row.append(td);return td;}
function option(select,value,text){const o=document.createElement('option');o.value=value;o.textContent=text;select.append(o);}
async function loadPeople(){
 employees=(await api('/employees')).items;$('peopleRows').replaceChildren();
 for(const id of ['enrollEmployee','filterEmployee','manualEmployee']){$(id).replaceChildren();option($(id),'',id==='filterEmployee'?'All employees':'Select employee');}
 for(const e of employees){
  if(e.active&&e.consent_at&&!e.face_id&&!e.face_removal_pending)option($('enrollEmployee'),e.employee_id,e.name);
  option($('filterEmployee'),e.employee_id,e.name);option($('manualEmployee'),e.employee_id,e.name);
  const tr=document.createElement('tr');const name=cell(tr,e.name);const small=document.createElement('small');small.textContent=e.employee_id;name.append(small);
  cell(tr,e.department);cell(tr,e.workdays.map(i=>['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][i]).join(', ')+' · '+e.late_after);
  cell(tr,!e.active?'Inactive':e.face_removal_pending?'Removal pending':e.face_id?'Enrolled':e.consent_at?'Ready to enroll':'Manual only');
  const action=cell(tr,'');
  if(e.active&&!e.consent_at&&!e.face_removal_pending){const b=document.createElement('button');b.className='secondary small';b.textContent='Record consent';b.onclick=()=>safe(async()=>{if(!confirm('Has this employee voluntarily consented to face enrollment and been offered manual attendance?'))return;await api(`/employees/${e.employee_id}/consent`,'POST',{consent:true});await loadPeople();});action.append(b);}
  if(e.face_id||e.face_removal_pending){const b=document.createElement('button');b.className='danger';b.textContent='Remove face';b.onclick=()=>safe(async()=>{if(!confirm(`Remove ${e.name}’s stored face enrollment? Historical attendance will remain.`))return;await api(`/employees/${e.employee_id}/remove-face`,'POST',{});await loadPeople();});action.append(b);}
  if(e.active){const b=document.createElement('button');b.className='secondary small';b.textContent='Deactivate';b.onclick=()=>safe(async()=>{const end=prompt('Last scheduled employment date (YYYY-MM-DD). This disables captures and removes face enrollment.',dateHere());if(!end)return;await api(`/employees/${e.employee_id}/deactivate`,'POST',{end_date:end});await loadPeople();});action.append(b);}
  $('peopleRows').append(tr);
 }
}
['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].forEach((name,i)=>{const label=document.createElement('label');label.className='inline';const box=document.createElement('input');box.type='checkbox';box.name='workday';box.value=i;box.checked=i<5;label.append(box,document.createTextNode(name));$('workdays').append(label);});
$('refreshPeople').onclick=()=>safe(loadPeople);
$('employeeForm').onsubmit=e=>{e.preventDefault();safe(async()=>{const f=new FormData(e.target);const data=Object.fromEntries(f);data.workdays=f.getAll('workday').map(Number);data.consent=f.has('consent');const result=await api('/employees','POST',data);notify('Created '+result.name+'. Employee ID: '+result.employee_id);await loadPeople();e.target.reset();document.querySelector('[name=start_date]').value=dateHere();});};
function filters(){return new URLSearchParams({start:$('fromDate').value,end:$('toDate').value,employee_id:$('filterEmployee').value,status:$('filterStatus').value}).toString();}
async function loadAttendance(){const d=await api('/attendance?'+filters());attendance=d.items;$('attendanceRows').replaceChildren();$('stats').replaceChildren();for(const [label,value] of [['Attendance',d.summary.present_pct+'%'],['On time',d.summary.present],['Late',d.summary.late],['Absent',d.summary.absent]]){const box=document.createElement('div');box.className='stat';const b=document.createElement('b');b.textContent=value;const sm=document.createElement('small');sm.textContent=label;box.append(b,sm);$('stats').append(box);}
 for(const r of attendance){const tr=document.createElement('tr');cell(tr,r.name);cell(tr,r.date);cell(tr,fmt(r.clock_in));cell(tr,fmt(r.clock_out));const st=cell(tr,'');const badge=document.createElement('span');badge.className='badge '+r.status;badge.textContent=r.status;st.append(badge);cell(tr,r.source);const ac=cell(tr,'');const edit=document.createElement('button');edit.className='secondary small';edit.textContent='Edit';edit.onclick=()=>{$('manualEmployee').value=r.employee_id;$('manualDate').value=r.date;$('manualStatus').value=r.status;$('manualIn').value=r.clock_in||'';$('manualOut').value=r.clock_out||'';$('manualVersion').value=r.version;$('manualForm').scrollIntoView({behavior:'smooth'});};ac.append(edit);$('attendanceRows').append(tr);}
 if(!attendance.length){const tr=document.createElement('tr');const td=cell(tr,'No records for these filters. Absences appear after the scheduled day closes.');td.colSpan=7;$('attendanceRows').append(tr);}}
$('filterForm').onsubmit=e=>{e.preventDefault();safe(loadAttendance);};
$('export').onclick=()=>safe(async()=>{const d=await api('/export?'+filters());const url=URL.createObjectURL(new Blob([d.csv],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='attendance.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
$('manualForm').onsubmit=e=>{e.preventDefault();safe(async()=>{if(!confirm('Save this manual attendance change with an audit record?'))return;await api('/manual','POST',{employee_id:$('manualEmployee').value,date:$('manualDate').value,status:$('manualStatus').value,clock_in:$('manualIn').value,clock_out:$('manualOut').value,reason:$('manualReason').value,version:Number($('manualVersion').value)});notify('Correction saved. Regenerate affected reports if needed.');await loadAttendance();});};
$('resetManual').onclick=()=>{$('manualForm').reset();$('manualVersion').value='0';$('manualDate').value=dateHere();};
for(const id of ['manualEmployee','manualDate'])$(id).onchange=()=>{$('manualVersion').value='0';};
async function loadPolicy(){const p=await api('/config');$('holidays').value=p.holidays.join('\n');$('similarity').value=p.similarity;$('policyVersion').value=p.version||0;}
$('policyForm').onsubmit=e=>{e.preventDefault();safe(async()=>{await api('/config','POST',{holidays:$('holidays').value.split(/\s+/).filter(Boolean),similarity:Number($('similarity').value),version:Number($('policyVersion').value)});await loadPolicy();notify('Policy saved.');});};
async function loadReports(){const d=await api('/reports');$('reportList').replaceChildren();for(const r of d.items){const li=document.createElement('li');const a=document.createElement('a');a.href=r.url;a.target='_blank';a.rel='noopener noreferrer';a.textContent=r.key+' · '+fmt(r.updated);li.append(a);$('reportList').append(li);}if(!d.items.length)$('reportList').textContent='No saved reports yet.';}
$('refreshReports').onclick=()=>safe(loadReports);$('reportForm').onsubmit=e=>{e.preventDefault();safe(async()=>{await api('/reports','POST',{date:$('reportDate').value,mode:$('reportMode').value});notify('Report requested. Refresh the saved reports in a few seconds.');});};

$('checkCapture').onclick=()=>safe(async()=>{if(!lastSession)return;const j=await api('/sessions/'+lastSession);if(j.state==='DONE'){const r=j.result;$('resultTitle').textContent=r.name;$('resultText').textContent=r.message||`${r.action==='in'?'Clocked in':'Clocked out'} · ${r.status}`;$('resultTime').textContent=r.time?fmt(r.time):'';}else{$('captureStatus').textContent=j.error||('Current state: '+j.state);}});
