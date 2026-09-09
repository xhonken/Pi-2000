/* Pi-2000 connection launcher around the upstream phpMyAdmin application. */
(()=>{
'use strict';
const d=Win2kDesktop,s=Win2kShell,legacy=s.actions.database;
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let current;
function open(){
 s.closeStart();if(current){current.focus();return current;}
 const w=d.makeWindow('MariaDB Manager','phpmyadmin-window');current=w;w.element.style.left=Math.max(4,(innerWidth-Math.min(1200,innerWidth*.96))/2)+'px';let profiles=[],sid=null,busy=false,closed=false;const dialogs=new Set();
 w.body.innerHTML='<div class="tool-toolbar pma-toolbar"></div><div class="pma-error" role="alert" hidden></div><div class="pma-launcher"><label>Saved connections<select aria-label="Saved connections" size="6"></select></label><p>Choose a saved MariaDB server, or create a connection. Database permissions are determined by your MariaDB account.</p><p>phpMyAdmin opens here with database navigation, structure, SQL, search, insert, import, export and administration.</p></div><iframe class="pma-frame" title="phpMyAdmin database administration" hidden></iframe>';
 const area=w.body.querySelector('.pma-toolbar'),select=w.body.querySelector('select'),frame=w.body.querySelector('iframe'),error=w.body.querySelector('.pma-error'),launcher=w.body.querySelector('.pma-launcher');
 async function run(fn){error.hidden=true;try{await fn();}catch(e){error.textContent=e.message;error.hidden=false;w.status.textContent=e.message;}}
 function button(label,fn){const b=document.createElement('button');b.type='button';b.className='win2k-button';b.textContent=label;b.onclick=()=>run(fn);area.append(b);return b;}
 frame.onload=w.onresize=()=>{try{frame.contentDocument.documentElement.style.setProperty('--pi2000-font-size',getComputedStyle(w.body).fontSize);}catch{}};
 const chosen=()=>{const p=profiles.find(p=>p.id===select.value);if(!p)throw Error('Select a saved connection.');return p;};
 async function refresh(id=select.value){profiles=(await d.api('/databases/connections')).connections;select.innerHTML=profiles.map(p=>'<option value="'+esc(p.id)+'">'+esc(p.name+' — '+p.username+' @ '+p.host+':'+p.port)+'</option>').join('');select.value=profiles.some(p=>p.id===id)?id:(profiles[0]?.id||'');}
 function dialog(title,html){
  const el=document.createElement('dialog');el.className='frame db-dialog';el.innerHTML='<div class="titlebar"><strong>'+esc(title)+'</strong></div><form class="db-dialog-fields">'+html+'<p class="db-dialog-error" role="alert"></p><div class="db-dialog-buttons"><button type="submit" class="win2k-button">OK</button><button type="button" class="win2k-button">Cancel</button></div></form>';
  document.body.append(el);dialogs.add(el);el.querySelector('[type=button]').onclick=()=>el.close();el.addEventListener('close',()=>{dialogs.delete(el);el.remove();});el.showModal();return el;
 }
 function edit(existing){
  const p=existing||{name:'',host:'127.0.0.1',port:3306,username:'',database:'',tls:'verify',ca:''};
  const el=dialog(existing?'Connection Properties':'New Connection',
   [['name','Connection name'],['host','Server'],['port','Port'],['username','Database user'],['database','Default database (optional)']].map(([n,label])=>'<label>'+label+'<input name="'+n+'" value="'+esc(p[n])+'" '+(['database'].includes(n)?'':'required')+'></label>').join('')+
   '<label>Password<input name="password" type="password" autocomplete="new-password"></label><label class="db-check"><input name="save_password" type="checkbox" '+(p.saved_password?'checked':'')+'>Save password encrypted for my account</label><label>Transport<select name="tls"><option value="verify">Verified TLS</option><option value="disabled">Unencrypted</option></select></label><label>Custom CA certificate (optional)<textarea name="ca">'+esc(p.ca)+'</textarea></label>');
  el.querySelector('[name=tls]').value=p.tls;
  el.querySelector('form').onsubmit=async e=>{e.preventDefault();const submit=el.querySelector('[type=submit]');submit.disabled=true;try{const data=Object.fromEntries(new FormData(e.target));data.port=Number(data.port);data.save_password=e.target.elements.save_password.checked;if(existing?.saved_password&&!data.password)delete data.password;const result=await d.api('/databases/connections'+(existing?'/'+existing.id:''),existing?'PUT':'POST',data);await refresh(result.id);el.close();}catch(e){el.querySelector('.db-dialog-error').textContent=e.message;}finally{submit.disabled=false;}};
 }
 async function password(p){if(p.saved_password)return undefined;return new Promise(resolve=>{const el=dialog('Connect to '+p.name,'<label>Password<input name="password" type="password" autocomplete="current-password" autofocus></label>');let done=false;el.querySelector('form').onsubmit=e=>{e.preventDefault();done=true;resolve(e.target.elements.password.value);el.close();};el.addEventListener('close',()=>{if(!done)resolve(null);});});}
 async function disconnect(){if(sid){await d.api('/phpmyadmin/session/'+sid,'DELETE');sid=null;}frame.src='about:blank';frame.hidden=true;launcher.hidden=false;w.status.textContent='Disconnected';}
 async function connect(){
  if(busy)return;const p=chosen(),secret=await password(p);if(secret===null)return;busy=true;connectButton.disabled=true;w.status.textContent='Connecting to '+p.name+'…';
  try{if(sid)await disconnect();const result=await d.api('/phpmyadmin/launch','POST',{connection:p.id,password:secret});if(closed){await d.api('/phpmyadmin/session/'+result.id,'DELETE');return;}sid=result.id;frame.src=result.url+(p.database?'index.php?route=/database/structure&db='+encodeURIComponent(p.database):'');launcher.hidden=true;frame.hidden=false;w.status.textContent=p.name+' — '+p.username+' @ '+p.host+':'+p.port+' — phpMyAdmin';}finally{busy=false;connectButton.disabled=false;}
 }
 button('New Connection',()=>edit());const connectButton=button('Connect',connect);
 button('Properties',()=>edit(chosen()));
 button('Delete Connection',async()=>{const p=chosen();if(!confirm('Delete saved connection "'+p.name+'"? Its databases will remain.'))return;await d.api('/databases/connections/'+p.id,'DELETE');await refresh();});
 button('Connections',()=>{launcher.hidden=sid?!launcher.hidden:false;frame.hidden=!sid||!launcher.hidden;});
 button('Disconnect',disconnect);
 button('Saved SQL Workspace',()=>{legacy();});
 select.ondblclick=()=>run(connect);
 w.beforeclose=async()=>{if(sid&&!confirm('Close MariaDB Manager and disconnect?'))return false;try{await disconnect();return true;}catch(e){error.textContent=e.message;error.hidden=false;return false;}};
 w.beforelogout=()=>!sid||confirm('Log off and disconnect MariaDB? Finish database operations first. Active transactions are not restored.');
 const unload=e=>{if(sid){e.preventDefault();e.returnValue='';}};window.addEventListener('beforeunload',unload);
 w.onclose=()=>{window.removeEventListener('beforeunload',unload);closed=true;for(const el of dialogs)el.close();if(sid)d.api('/phpmyadmin/session/'+sid,'DELETE').catch(()=>{});frame.src='about:blank';current=null;};
 run(()=>refresh());w.status.textContent='Private saved connections — phpMyAdmin';
 return w;
}
s.actions.databaseLegacy=legacy;
s.actions.database=open;
Win2kApps.register({type:'phpmyadmin-window',singleton:true,restore:open});
})();
