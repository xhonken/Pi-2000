(() => {
'use strict';
const $ = s => document.querySelector(s), shell = window.Win2kShell;
let account = null, usersWindow = null, browserWindow = null;
let items = [], folder = null, explorer = null, selected = null, highest = 30;
const windows = new Set();
let restoring = false, workspaceTimer = null, workspaceQueue = Promise.resolve();
const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function api(path, method = 'GET', data) {
 const response = await fetch('/api'+path, {method, headers: data ? {'Content-Type':'application/json'} : {}, body: data ? JSON.stringify(data) : undefined});
 const result = await response.json();
 if (!response.ok) { if (response.status === 401 && path !== '/login') locked(); const error=new Error(result.error || 'The operation failed.');error.status=response.status;throw error; }
 return result;
}
function locked() {
 account = null; window.dispatchEvent(new CustomEvent('win2k-user',{detail:null})); items = []; folder = null; selected = null; shell.setUser(null, api);
 clearTimeout(workspaceTimer);
 for (const win of [...windows]) win.close(true);
 $('#window').close(); shell.closeStart(); $('#session').hidden = true; $('#logon').hidden = false;
 $('#login-form').reset(); $('#login-form').elements.username.value = 'admin';
}
async function unlocked(user) { await shell.setUser(user, api); account = user; window.dispatchEvent(new CustomEvent('win2k-user',{detail:user})); document.querySelectorAll('[data-action=users]').forEach(button => button.hidden = user.role !== 'admin'); $('#logon').hidden = true; $('#session').hidden = false; $('#login-form').reset(); $('#start-button').focus(); await restoreWorkspace(); }
$('#login-form').onsubmit = async e => {
 e.preventDefault(); const form = e.target, submit = form.querySelector('[type=submit]');
 $('#login-error').textContent = ''; submit.disabled = true;
 try { const user = await api('/login','POST',{username:form.elements.username.value,password:form.elements.password.value}); await unlocked(user); }
 catch (error) { $('#login-error').textContent = error.message; form.elements.password.value = ''; }
 finally { submit.disabled = false; }
};
shell.actions.logout = async () => { try { for(const win of windows)if(win.beforelogout && !(await win.beforelogout()))return; await saveWorkspace(); await api('/logout','POST'); locked(); } catch (error) { shell.notify(error.message); } };
shell.actions.password = () => {
 shell.show('Change My Password', '<form id="password-form"><label class="form-row">Current password:<input name="current" type="password" autocomplete="current-password" required></label><label class="form-row">New password:<input name="password" type="password" autocomplete="new-password" minlength="12" required></label><label class="form-row">Repeat new password:<input name="repeat" type="password" autocomplete="new-password" minlength="12" required></label><p id="password-error" class="error" role="alert"></p><div class="actions"><button class="win2k-button">Save</button></div></form>');
 $('#password-form').onsubmit = async e => { e.preventDefault(); const f=e.target.elements; if(f.password.value!==f.repeat.value){$('#password-error').textContent='The passwords do not match.';return;} try { const result=await api('/password','POST',{current:f.current.value,password:f.password.value}); $('#window').close(); if(result.login_required){location.reload();return;} shell.notify('Password changed.'); }catch(error){$('#password-error').textContent=error.message;} };
};
async function refreshUsers() {
 const user=account; const result = await api('/users');
 if (!usersWindow || account!==user) return;
 const win = usersWindow;
 win.body.innerHTML = `<div class="explorer-toolbar"><button class="win2k-button" id="user-new">New User…</button><button class="win2k-button" id="user-refresh">Refresh</button><button class="win2k-button" id="user-self-password">Change My Password…</button></div><p class="users-help">Each user has a private Linux account and home. Administrators have Local Terminal, without automatic sudo. Only the creator can change roles.</p><div class="users-list"><table><thead><tr><th>Username</th><th>Role</th><th>Status</th><th>Actions</th></tr></thead><tbody></tbody></table></div>`;
 for (const user of result.users) {
  const row = document.createElement('tr');
  row.innerHTML = `<td>${escape(user.username)}${user.id === account.id ? ' (you)' : ''}</td><td>${user.is_owner ? 'Creator' : user.role === 'admin' ? 'Administrator' : 'User'}</td><td>${user.account_state==='pending' ? 'Setup incomplete' : user.active ? 'Enabled' : 'Disabled'}${user.linux_username ? '<br>'+escape(user.linux_username)+(user.linux_managed ? '' : ' (linked)') : ' · migration on next login'}</td><td class="user-actions"></td>`;
  const actions = row.querySelector('.user-actions');
  const button = (label, action) => { const b = document.createElement('button'); b.className = 'win2k-button'; b.textContent = label; b.onclick = action; actions.append(b); };
  if(account.is_owner || user.role!=='admin' || user.id===account.id) button('Storage Quota…',()=>storageQuotaDialog(user));
  if (user.is_owner || (user.role === 'admin' && !account.is_owner)) {
   if (user.id === account.id) button('Change My Password…', shell.actions.password);
   const note = document.createElement('small'); note.textContent = 'Protected Account'; actions.append(note);
  } else {
   if (account.is_owner) button(user.role === 'admin' ? 'Make User…' : 'Make Administrator…', () => userRoleDialog(user));
   button('Reset Password…', () => userPasswordDialog(user));
   button(user.active ? 'Disable…' : 'Enable…', () => userConfirm(user, 'active'));
   button('Delete…', () => userConfirm(user, 'delete'));
  }
  win.body.querySelector('tbody').append(row);
 }
 win.body.querySelector('#user-new').onclick = () => userPasswordDialog();
 win.body.querySelector('#user-self-password').onclick = shell.actions.password;
 win.body.querySelector('#user-refresh').onclick = () => refreshUsers().catch(error => {win.status.textContent = error.message;});
 win.status.textContent = `${result.users.length} accounts · The owner cannot be deleted or disabled`;
}
function storageQuotaDialog(user){
 shell.show('Storage Quota – '+user.username,`<form id="quota-form"><p>Storage for files, the desktop and the Recycle Bin.</p><label class="form-row">Quota in MB:<input name="quota" type="number" min="1" max="1048576" step="1" required value="${Math.floor(user.storage_quota/1048576)}"></label><p class="error" role="alert"></p><button class="win2k-button" type="submit">Save</button></form>`);
 $('#quota-form').onsubmit=async e=>{e.preventDefault();const form=e.target;try{await api('/users/'+user.id+'/storage','PATCH',{quota_mb:Number(form.elements.quota.value)});$('#window').close();await refreshUsers();window.dispatchEvent(new Event('win2k-files-refresh'));shell.notify('Storage quota updated.');}catch(error){form.querySelector('.error').textContent=error.message;}};
}
function userPasswordDialog(user) {
 shell.show(user ? 'Reset Password – '+user.username : 'New User', `<form id="user-form">${user ? `<p>Enter a new password for ${escape(user.username)}. Existing logins and terminals will be ended.</p>` : '<label class="form-row">Username:<input name="username" autocomplete="off" required minlength="3" maxlength="64" pattern="[A-Za-z0-9_.\\-]{3,64}"></label><p class="muted">3–64 characters: a–z, digits, dots, hyphens or underscores.</p>'}<label class="form-row">New password:<input name="password" type="password" autocomplete="new-password" required minlength="12" maxlength="1024"></label><label class="form-row">Repeat password:<input name="repeat" type="password" autocomplete="new-password" required minlength="12" maxlength="1024"></label><p class="error" id="user-error" role="alert"></p><div class="actions"><button type="button" class="win2k-button" data-action="close">Cancel</button><button class="win2k-button default" type="submit">${user ? 'Save Password' : 'Create User'}</button></div></form>`);
 $('#user-form').onsubmit = async e => {
  e.preventDefault(); const f = e.target.elements, submit = e.target.querySelector('[type=submit]');
  if (f.password.value !== f.repeat.value) { $('#user-error').textContent = 'The passwords do not match.'; return; }
  submit.disabled = true;
  try {
   await api(user ? `/users/${user.id}/password` : '/users', 'POST', user ? {password:f.password.value} : {username:f.username.value,password:f.password.value});
   e.target.reset(); $('#window').close(); await refreshUsers(); shell.notify(user ? 'Password changed.' : 'The user has been created.');
  } catch(error) { const el = $('#user-error'); if(el) el.textContent = error.message; }
  finally { submit.disabled = false; }
 };
}
function userRoleDialog(user) {
 const role = user.role === 'admin' ? 'user' : 'admin';
 const label = role === 'admin' ? 'Make Administrator' : 'Make User';
 shell.show(label, `<p>${escape(user.username)} will become ${role === 'admin' ? 'an administrator and can manage user accounts' : 'a user and can no longer manage accounts'}.</p><p>Existing logins and SSH terminals will be ended. The user must log in again.</p><p class="error" id="user-error" role="alert"></p><div class="actions"><button class="win2k-button" data-action="close">Cancel</button><button class="win2k-button" id="user-confirm">${label}</button></div>`);
 $('#user-confirm').onclick = async e => {
  e.target.disabled = true;
  try { await api('/users/'+user.id, 'PATCH', {role}); $('#window').close(); await refreshUsers(); shell.notify('Role changed.'); }
  catch(error) { const el = $('#user-error'); if(el) el.textContent = error.message; }
  finally { e.target.disabled = false; }
 };
}
function userConfirm(user, action) {
 const label = action === 'delete' ? 'Delete' : user.active ? 'Disable' : 'Enable';
 shell.show(`${label} user`, `<p>Do you want to ${label.toLowerCase()} ${escape(user.username)}?</p><p>${action === 'delete' ? 'The account will be permanently deleted, including its folders, connections and desktop settings.' : user.active ? 'The user cannot log in until the account is enabled again.' : 'The user can log in again with their existing password.'}</p>${action === 'delete' ? '<p>'+ (user.linux_managed ? 'The managed Linux account and its home will also be removed.' : 'The linked Linux account and its home will be preserved.') +'</p><label>Type the username to confirm: <input id="delete-username" autocomplete="off"></label>' : ''}${action === 'delete' || user.active ? '<p>Active logins and SSH terminals will be ended.</p>' : ''}<p class="error" id="user-error" role="alert"></p><div class="actions"><button class="win2k-button" data-action="close">Cancel</button><button class="win2k-button" id="user-confirm">${label}</button></div>`);
 $('#user-confirm').onclick = async e => {
  e.target.disabled = true;
  try { await api('/users/'+user.id, action === 'delete' ? 'DELETE' : 'PATCH', action === 'delete' ? {confirm:$('#delete-username').value} : {active:!user.active}); $('#window').close(); await refreshUsers(); }
  catch(error) { const el = $('#user-error'); if(el) el.textContent = error.message; }
  finally { e.target.disabled = false; }
 };
}
shell.actions.users = async () => {
 shell.closeStart(); if (account?.role !== 'admin') return;
 if (!usersWindow) { usersWindow = makeWindow('User Management', 'users-window'); usersWindow.onclose = () => {usersWindow = null;}; }
 usersWindow.focus(); usersWindow.status.textContent = 'Loading users…';
 try { await refreshUsers(); } catch(error) { if(usersWindow) usersWindow.status.textContent = error.message; }
};
function workspaceData() {
 return {windows:[...windows].map(win => ({type:win.type, ...(win.type==='editor-window'?{editorFiles:win.editorFiles||[]}:{}), terminal:win.terminalId || null, folder:win.fileParent ?? (win === explorer ? folder : null),
  left:parseFloat(win.element.style.left)||0, top:parseFloat(win.element.style.top)||0,
  width:parseFloat(win.element.style.width)||win.element.offsetWidth||760, height:parseFloat(win.element.style.height)||win.element.offsetHeight||510,
  hidden:win.element.hidden, maximized:win.element.classList.contains('maximized')}))};
}
function scheduleWorkspace() { if (!account || restoring) return; clearTimeout(workspaceTimer); workspaceTimer=setTimeout(()=>saveWorkspace().catch(error=>shell.notify(error.message)),150); }
function saveWorkspace() {
 clearTimeout(workspaceTimer); if (!account || restoring) return Promise.resolve();
 const user=account, data=workspaceData();
 workspaceQueue=workspaceQueue.catch(()=>{}).then(()=>account===user ? api('/workspace','PUT',data) : undefined);
 return workspaceQueue;
}
function applyLayout(win, layout) {
 if (!win || !layout) return;
 const el=win.element;
 el.style.width=`${Math.max(280,Math.min(layout.width,innerWidth-8))}px`; el.style.height=`${Math.max(200,Math.min(layout.height,innerHeight-60))}px`;
 el.style.left=`${Math.max(0,Math.min(layout.left,innerWidth-100))}px`; el.style.top=`${Math.max(0,Math.min(layout.top,innerHeight-100))}px`;
 el.classList.toggle('maximized',layout.maximized); el.hidden=layout.hidden; win.task.classList.toggle('active',!layout.hidden); win.onresize?.();
}
async function restoreWorkspace() {
 const user=account; restoring=true;
 try {
  const [layout, result]=await Promise.all([api('/workspace'),api('/terminals')]);
  if(account!==user)return;
  const remaining=new Map(result.terminals.map(term=>[term.id,term]));
  for (const entry of layout.windows) {
   if(account!==user)return;
   const win=await window.Win2kApps.restore(entry,account,{remaining});
   if(account!==user)return;
   applyLayout(win,entry);
  }
  for (const term of remaining.values()) startTerminal(term.profile,null,term.id);
 } catch(error) { shell.notify('Could not restore windows: '+error.message); }
 finally { restoring=false; }
}
window.addEventListener('pagehide',()=>{
 if(account && !restoring) fetch('/api/workspace',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(workspaceData()),keepalive:true}).catch(()=>{});
});
shell.actions.browser=async(url)=>{
 shell.closeStart();
 if(browserWindow){browserWindow.focus();if(url)await browserWindow.openUrl(url);return;}
 const user=account, win=makeWindow('Browser','browser-window');browserWindow=win;
 win.body.innerHTML='<div class="browser-toolbar"><button class="win2k-button browser-reconnect">Reconnect</button><button class="win2k-button browser-fullscreen">Full Screen</button><button class="win2k-button browser-stop">End Session…</button><span>Tabs and logins are private to your account.</span></div><div class="browser-content"><p class="browser-loading">Starting your browser…</p></div>';
 let disposed=false,connecting=false,monitor;
 async function connect(){
  if(disposed||connecting)return;
  connecting=true;
  win.status.textContent='Starting or reconnecting to your browser…';
  win.body.querySelector('.browser-reconnect').disabled=true;
  try{
   const result=await api('/browser/start','POST',url?{url}:{});url=null;
   if(disposed||account!==user)return;
   const frame=document.createElement('iframe');frame.title='Your Private Browser';frame.src=result.url;
   frame.allow='autoplay; fullscreen; clipboard-read; clipboard-write';frame.allowFullscreen=true;
   frame.onload=()=>frame.contentWindow.addEventListener('pointerdown',()=>{if(!disposed)win.focus();});
   win.body.querySelector('.browser-content').replaceChildren(frame);
   win.status.textContent='Click inside the browser to use it and enable audio. Your tabs remain open when you close this window.';
  }catch(error){if(!disposed){win.status.textContent=error.message;win.body.querySelector('.browser-content').textContent=error.message;}}
  finally{connecting=false;if(!disposed)win.body.querySelector('.browser-reconnect').disabled=false;}
 }
 win.openUrl=async target=>{if(connecting)throw Error('Browser is connecting. Try the shortcut again shortly.');url=target;await connect();};
 win.body.querySelector('.browser-reconnect').onclick=connect;
 win.body.querySelector('.browser-fullscreen').onclick=()=>win.body.querySelector('iframe')?.requestFullscreen().catch(error=>shell.notify(error.message));
 win.body.querySelector('.browser-stop').onclick=async()=>{
  if(!window.confirm('End your browser session? Playback will stop. Your profile and saved website logins will be preserved.'))return;
  try{await api('/browser/stop','POST',{});win.close();}catch(error){shell.notify(error.message);}
 };
 const offline=()=>{win.status.textContent='Network disconnected. Your browser continues running on the server.';};
 const online=()=>connect();
 window.addEventListener('offline',offline);window.addEventListener('online',online);
 async function checkBrowser(){
  try{
   const state=await api('/browser/status');
   if(disposed||connecting||account!==user)return;
   if(state.state==='stopped'){
    const reasons={memory_limit:'Browser stopped after reaching its memory limit.',crashed:'The browser process stopped unexpectedly.',disk_full:'Browser stopped because server storage is almost full.',idle_timeout:'Browser stopped after 24 hours without a connection.',ended:'The browser session was ended.',not_started:'No browser session is running.'};
    const message=(reasons[state.reason]||'The browser session ended.')+' Your saved profile is preserved. Select Reconnect to start again.';
    win.status.textContent=message;win.body.querySelector('.browser-content').textContent=message;
   }else if(state.warning){win.status.textContent=state.warning;}
   else if(win.body.querySelector('iframe'))win.status.textContent='Connected. Tabs and logins are private to your account.';
  }catch(error){if(!disposed&&!connecting)win.status.textContent=error.message+' Select Reconnect when the connection is available again.';}
  finally{if(!disposed)monitor=setTimeout(checkBrowser,10000);}
 }
 win.onclose=()=>{disposed=true;clearTimeout(monitor);window.removeEventListener('offline',offline);window.removeEventListener('online',online);win.body.querySelector('iframe')?.remove();browserWindow=null;};
 await connect();if(!disposed)monitor=setTimeout(checkBrowser,10000);
};
function makeWindow(title, type) {
 const app=window.Win2kApps.get(type);
 if(!app || !account || !app.allowed(account))throw new Error('You do not have access to this application.');
 if(app.singleton){const existing=[...windows].find(win=>win.type===type);if(existing){existing.focus();return existing;}}
 if(windows.size>=12)throw new Error('Maximum twelve open windows. Close a window first.');
 const element = document.createElement('section'); element.className = `app-window frame ${type}`; element.setAttribute('aria-label', title);
 const offset = (windows.size % 5) * 24;
 element.style.left = `${Math.min(145 + offset, Math.max(4, innerWidth - 760))}px`; element.style.top = `${40 + offset}px`;
 element.innerHTML = `<header class="win2k-titlebar"><strong>${escape(title)}</strong><div class="window-controls"><button class="win2k-button" data-control="min" aria-label="Minimise">_</button><button class="win2k-button" data-control="max" aria-label="Maximise">□</button><button class="win2k-button" data-control="close" aria-label="Close">×</button></div></header><div class="app-body"></div><div class="app-status" role="status"></div>`;
 $('#session').append(element);
 const task = document.createElement('button'); task.className='win2k-button task-entry';task.textContent=title;task.title=title;$('#tasks').append(task);
 const win = {element, type, beforeclose:null, body:element.querySelector('.app-body'), status:element.querySelector('.app-status'), task, onclose:null, onresize:null,
 focus(){ element.hidden=false;element.style.zIndex=++highest;windows.forEach(w=>{w.element.classList.toggle('inactive',w!==win);w.task.classList.toggle('active',w===win);});win.onresize?.(); scheduleWorkspace(); },
 async close(detach=false){if(!detach && win.beforeclose && !(await win.beforeclose()))return;observer.disconnect();win.uiCleanup?.();win.onclose?.();element.remove();task.remove();windows.delete(win);scheduleWorkspace();},
 title(value){element.querySelector('strong').textContent=value;task.textContent=value;task.title=value;element.setAttribute('aria-label',value);}
 };
 windows.add(win);win.focus();
 element.addEventListener('pointerdown',()=>win.focus());
 task.onclick=()=>{if(!element.hidden && task.classList.contains('active')){element.hidden=true;task.classList.remove('active');scheduleWorkspace();}else win.focus();};
 element.querySelector('[data-control=min]').onclick=()=>{element.hidden=true;task.classList.remove('active');scheduleWorkspace();};
 const maximize=()=>{element.classList.toggle('maximized');win.onresize?.();scheduleWorkspace();};
 element.querySelector('[data-control=max]').onclick=maximize;
 element.querySelector('[data-control=close]').onclick=()=>win.close();
 const header=element.querySelector('header');header.ondblclick=e=>{if(!e.target.closest('button'))maximize();};
 header.onpointerdown=e=>{if(e.target.closest('button')||element.classList.contains('maximized'))return;e.preventDefault();const rect=element.getBoundingClientRect(),dx=e.clientX-rect.left,dy=e.clientY-rect.top;header.setPointerCapture(e.pointerId);header.onpointermove=m=>{element.style.left=`${Math.max(0,Math.min(innerWidth-element.offsetWidth,m.clientX-dx))}px`;element.style.top=`${Math.max(0,Math.min(innerHeight-80,m.clientY-dy))}px`;};header.onpointerup=()=>{header.onpointermove=null;scheduleWorkspace();};};
 const observer=new ResizeObserver(()=>{win.onresize?.();scheduleWorkspace();});observer.observe(win.body);
 window.Win2kUI?.attach(win);return win;
}
async function refresh(){const user=account;const result=await api('/items');if(account!==user)return;items=result.items;if(folder&&!items.some(x=>x.id===folder))folder=null;renderExplorer();}
function currentPath(id){const names=[];let cursor=items.find(x=>x.id===id);while(cursor){names.unshift(cursor.name);cursor=items.find(x=>x.id===cursor.parent);}return ['My Devices',...names].join(' / ');}
function renderExplorer(){
 if(!explorer)return;
 scheduleWorkspace();
 explorer.title(currentPath(folder));selected=null;
 explorer.body.innerHTML=`<div class="explorer-toolbar"><button class="win2k-button" id="folder-up" ${folder?'':'disabled'}>Up</button><button class="win2k-button" id="new-folder">New Folder</button><button class="win2k-button" id="new-profile">New Connection</button><button class="win2k-button" id="item-open" disabled>Open</button><button class="win2k-button" id="item-edit" disabled>Properties</button><button class="win2k-button" id="item-delete" disabled>Delete</button></div><div class="explorer-address">Address: <span>${escape(currentPath(folder))}</span></div><div class="device-grid" tabindex="0" aria-label="Folders and SSH Profiles"></div><div class="device-context frame" hidden></div>`;
 const grid=explorer.body.querySelector('.device-grid');
 const visible=items.filter(x=>x.parent===folder).sort((a,b)=>(a.kind==='folder'?0:1)-(b.kind==='folder'?0:1)||a.name.localeCompare(b.name,'en'));
 for(const item of visible){
  const entry=document.createElement('button');entry.className='device-entry';entry.innerHTML=`<span class="win2k-pixel-icon win2k-icon-${item.kind==='folder'?'folder':'computer'}" aria-hidden="true"><i></i></span><span>${escape(item.name)}</span><small>${item.kind==='folder'?'Folder':escape(item.username+'@'+item.host)}</small>`;
  entry.onclick=()=>select(item,entry);entry.ondblclick=()=>open(item);entry.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();open(item);}};
  entry.oncontextmenu=e=>{e.preventDefault();e.stopPropagation();select(item,entry);context(e,item);};grid.append(entry);
 }
 if(!visible.length){const text=document.createElement('p');text.className='folder-empty';text.textContent='The folder is empty. Select New Connection or New Folder to get started.';grid.append(text);}
 explorer.status.textContent=`${visible.length} items · Double-click to open`;
 explorer.body.querySelector('#folder-up').onclick=()=>{folder=items.find(x=>x.id===folder)?.parent||null;renderExplorer();};
 explorer.body.querySelector('#new-folder').onclick=()=>edit(null,'folder');explorer.body.querySelector('#new-profile').onclick=()=>edit(null,'profile');
 explorer.body.querySelector('#item-open').onclick=()=>selected&&open(selected);explorer.body.querySelector('#item-edit').onclick=()=>selected&&edit(selected,selected.kind);explorer.body.querySelector('#item-delete').onclick=()=>selected&&remove(selected);
 grid.oncontextmenu=e=>{e.preventDefault();context(e,null);};
}
function select(item,entry){selected=item;explorer.body.querySelectorAll('.device-entry').forEach(x=>x.classList.toggle('selected',x===entry));['item-open','item-edit','item-delete'].forEach(id=>explorer.body.querySelector('#'+id).disabled=false);}
function context(event,item){const menu=explorer.body.querySelector('.device-context');menu.replaceChildren();const commands=item?[['Open',()=>open(item)],['Properties',()=>edit(item,item.kind)],['Delete',()=>remove(item)]]:[['New Folder',()=>edit(null,'folder')],['New Connection',()=>edit(null,'profile')]];for(const [label,fn] of commands){const b=document.createElement('button');b.textContent=label;b.onclick=()=>{menu.hidden=true;fn();};menu.append(b);}menu.hidden=false;menu.style.left=`${Math.min(event.clientX,innerWidth-menu.offsetWidth-5)}px`;menu.style.top=`${Math.min(event.clientY,innerHeight-menu.offsetHeight-45)}px`;menu.querySelector('button').focus();}
document.addEventListener('click',e=>{if(!e.target.closest('.device-context'))document.querySelectorAll('.device-context').forEach(x=>x.hidden=true);});
function open(item){if(item.kind==='folder'){folder=item.id;renderExplorer();}else connectDialog(item);}
function descendant(id,ancestor){let node=items.find(x=>x.id===id);while(node){if(node.id===ancestor)return true;node=items.find(x=>x.id===node.parent);}return false;}
function edit(item,kind){
 const parent=item?.parent||folder||'';
 const options=items.filter(x=>x.kind==='folder'&&(!item||!descendant(x.id,item.id))).map(x=>`<option value="${x.id}" ${x.id===parent?'selected':''}>${escape(currentPath(x.id))}</option>`).join('');
 shell.show(item?'Properties – '+item.name:kind==='folder'?'New Folder':'New SSH Connection',`<form id="device-form"><label class="form-row">Name:<input name="name" required maxlength="80" value="${escape(item?.name||'')}"></label><label class="form-row">Folder:<select name="parent"><option value="">My Devices</option>${options}</select></label>${kind==='profile'?`<label class="form-row">Hostname / IP:<input name="host" required value="${escape(item?.host||'')}" placeholder="192.168.1.10"></label><label class="form-row">SSH Port:<input name="port" type="number" min="1" max="65535" required value="${item?.port||22}"></label><label class="form-row">Username:<input name="username" required maxlength="128" value="${escape(item?.username||'')}"></label><p class="muted">Enter the SSH password when connecting. It is not stored in the profile.</p>`:''}<p class="error" id="device-error" role="alert"></p><div class="actions"><button type="button" class="win2k-button" data-action="close">Cancel</button><button class="win2k-button default">Save</button></div></form>`);
 $('#device-form').onsubmit=async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(e.target));data.kind=kind;data.parent=data.parent||null;try{await api('/items'+(item?'/'+item.id:''),item?'PUT':'POST',data);$('#window').close();await refresh();}catch(error){const el=$('#device-error');if(el)el.textContent=error.message;}};
}
function remove(item){shell.show('Delete '+item.name,`<p>Do you want to ta bort ${escape(item.name)}?</p><p class="error" id="delete-error" role="alert"></p><div class="actions"><button class="win2k-button" data-action="close">Cancel</button><button class="win2k-button" id="confirm-delete">Delete</button></div>`);$('#confirm-delete').onclick=async()=>{try{await api('/items/'+item.id,'DELETE');$('#window').close();await refresh();}catch(error){$('#delete-error').textContent=error.message;}};}
shell.actions.devices=async()=>{shell.closeStart();if(explorer){explorer.focus();try{await refresh();}catch(error){shell.notify(error.message);}return;}explorer=makeWindow('My Devices','explorer-window');explorer.onclose=()=>{explorer=null;};explorer.status.textContent='Loading devices…';try{await refresh();}catch(error){shell.notify(error.message);}};
shell.actions.localterminal=async()=>{shell.closeStart();if(account?.role!=='admin')return;const user=account;try{const profile=await api('/local-terminal');if(account===user)connectDialog(profile);}catch(error){shell.notify(error.message);}};
function connectDialog(profile){
 shell.show('Connect to '+profile.name,`<form id="ssh-form"><p>${escape(profile.username)}@${escape(profile.host)}:${profile.port}</p><label class="form-row">SSH Password:<input name="password" type="password" autocomplete="off"></label><p class="muted">The password is used only for this connection.</p><div class="actions"><button type="button" class="win2k-button" data-action="close">Cancel</button><button class="win2k-button default">Connect</button></div></form>`);
 $('#ssh-form input').focus();$('#ssh-form').onsubmit=e=>{e.preventDefault();const password=e.target.elements.password.value;e.target.reset();$('#window').close();startTerminal(profile,password);};
}
function startTerminal(profile,password,terminalId=null){
 const win=makeWindow(profile.local?'Local Terminal':profile.name+' – SSH','terminal-window'); win.terminalId=terminalId;
 win.body.innerHTML='<div class="terminal-toolbar"><button class="win2k-button reconnect" disabled>Reconnect</button><span>The job continues when you disconnect or log off.</span></div><div class="host-confirm" hidden></div><div class="terminal-surface"></div>';
 const terminal=new Terminal({cursorBlink:true,fontFamily:'Consolas, "Liberation Mono", monospace',fontSize:14,scrollback:5000,theme:{background:'#000000',foreground:'#d8d8d8',cursor:'#ffffff'},convertEol:false});
 const fit=new FitAddon.FitAddon();terminal.loadAddon(fit);terminal.open(win.body.querySelector('.terminal-surface'));
 let ready=false,disposed=false,ended=false,replaying=false,socket=null,retry=null;
 const send=message=>{if(socket?.readyState===WebSocket.OPEN)socket.send(JSON.stringify(message));};
 win.onresize=()=>{if(!win.element.hidden&&!disposed){fit.fit();if(ready)send({type:'resize',cols:terminal.cols,rows:terminal.rows});}};
 requestAnimationFrame(()=>{win.onresize();if(!win.element.hidden)terminal.focus();});
 terminal.onData(data=>{if(ready&&socket?.readyState===WebSocket.OPEN)socket.send(new TextEncoder().encode(data));});
 terminal.onBinary(data=>{if(ready&&socket?.readyState===WebSocket.OPEN)socket.send(Uint8Array.from(data,c=>c.charCodeAt(0)));});
 function attach(){
  if(disposed)return; clearTimeout(retry); ready=false;
  win.status.textContent=win.terminalId?'Reconnecting to your terminal…':`Connecting to ${profile.username}@${profile.host}:${profile.port}…`;
  win.body.querySelector('.reconnect').disabled=true;
  socket=new WebSocket(`${location.protocol==='https:'?'wss:':'ws:'}//${location.host}/api/terminal`);socket.binaryType='arraybuffer';
  socket.onopen=()=>{send(win.terminalId?{terminal:win.terminalId}:{profile:profile.id,local:profile.local===true,password,cols:terminal.cols,rows:terminal.rows});password=null;};
  socket.onmessage=e=>{
   if(disposed)return;
   if(e.data instanceof ArrayBuffer){const replay=replaying;replaying=false;terminal.write(new Uint8Array(e.data),()=>{if(replay&&!disposed&&!ended){ready=true;win.onresize();}});return;}
   const data=JSON.parse(e.data);
   if(data.type==='connected'){
    win.terminalId=data.id; ended=data.state==='ended'; replaying=data.replay_bytes>0;ready=!ended&&!replaying; terminal.reset();
    terminal.resize(data.cols,data.rows);
    win.status.textContent=`Ansluten · ${profile.username}@${profile.host}:${profile.port}${data.truncated?' · Older terminal output has been trimmed':''}`;
    scheduleWorkspace(); win.onresize();
   }
   if(data.type==='reset'){ready=false;replaying=true;terminal.reset();win.status.textContent='Reconnected · Older terminal output has been trimmed';}
   if(data.type==='ended'){ended=true;ready=false;win.status.textContent='The SSH session has ended. Terminal output is preserved.';}
   if(data.type==='error'){win.status.textContent=data.message;terminal.writeln('\r\n'+data.message);ended=true;}
   if(data.type==='hostkey'){
    const panel=win.body.querySelector('.host-confirm');panel.hidden=false;panel.innerHTML=`<p>New device: <b>${escape(data.host)}:${data.port}</b></p><p>Verify the SSH fingerprint against the device before accepting:</p><code>${escape(data.fingerprint)}</code><div class="actions"><button class="win2k-button reject">Cancel</button><button class="win2k-button trust">Trust Device and Connect</button></div>`;
    panel.querySelector('.trust').onclick=()=>{send({type:'trust',accept:true});panel.hidden=true;win.onresize();};panel.querySelector('.reject').onclick=()=>{send({type:'trust',accept:false});panel.hidden=true;ended=true;};win.onresize();
   }
  };
  socket.onerror=()=>{};
  socket.onclose=()=>{
   password=null;ready=false;if(disposed)return;
   win.body.querySelector('.host-confirm').hidden=true;win.body.querySelector('.reconnect').disabled=false;
   if(win.terminalId&&!ended){
    win.status.textContent='Disconnected from the browser · Reconnecting to the job…';
    retry=setTimeout(async()=>{try{await api('/session');if(!disposed)attach();}catch{if(!disposed)retry=setTimeout(attach,5000);}},3000);
   }else if(!ended){win.status.textContent='The connection could not be started. Please try again.';}
  };
 }
 win.body.querySelector('.reconnect').onclick=async()=>{
  if(win.terminalId&&!ended){attach();return;}
  if(win.terminalId){try{await api('/terminals/'+win.terminalId,'DELETE');}catch(error){shell.notify(error.message);return;}}
  win.beforeclose=null;await win.close();connectDialog(profile);
 };
 win.beforeclose=async()=>{
  if(!win.terminalId)return true;
  if(!ended&&!window.confirm('End the SSH session and close the terminal? Running jobs may stop. Log off or close your browser to keep the job running.'))return false;
  try{await api('/terminals/'+win.terminalId,'DELETE');return true;}catch(error){if(error.status===404)return true;shell.notify(error.message);return false;}
 };
 win.onclose=()=>{disposed=true;password=null;clearTimeout(retry);socket?.close();terminal.dispose();};
 attach();scheduleWorkspace();return win;
}
let statusWindow=null;
shell.actions.status=async()=>{
 shell.closeStart();
 if(statusWindow){statusWindow.focus();return;}
 const win=makeWindow('System Status','status-window');statusWindow=win;
 let disposed=false,timer;
 win.body.innerHTML='<div class="system-status"><p>Checking services…</p></div>';
 async function refreshStatus(){
  try{
   const [health,runtime]=await Promise.all([api('/health'),api('/runtime')]);
   if(disposed)return;
   const rows=runtime.users.map(row=>`<tr><td>${account.is_owner?'Account '+row.id:'Your Account'}</td><td>${row.terminals}</td><td>${row.browsers}</td><td>${row.memory_bytes===undefined?'—':Math.round(row.memory_bytes/1048576)+' MB'}</td></tr>`).join('');
   const backup=health.backup;
   win.body.querySelector('.system-status').innerHTML=`<p>Web Server: <b>OK</b> · Session Service: <b>${health.sessions==='ok'?'OK':'Temporarily unavailable'}</b></p><table><thead><tr><th>Account</th><th>Terminals</th><th>Browser</th><th>Memory</th></tr></thead><tbody>${rows||'<tr><td colspan="4">No running sessions.</td></tr>'}</tbody></table><p>Maximum 8 terminals per account and 3 browsers in total. Each browser can use up to 1.5 GB of memory and 1.5 CPU cores.</p><p>A browser with no connected user is stopped after 24 hours. Running SSH jobs continue.</p>${account.is_owner?`<p>Backup: <b>${backup?.state==='ok'?'Restore verified '+escape(new Date(backup.created).toLocaleString('en-GB')):backup?.state==='failed'?'Last attempt failed':'No verified backup yet'}</b></p><p>Backups are stored locally on the server.</p><p>Free diskutrymme: ${(health.disk_free_bytes/1073741824).toFixed(1)} GB</p>`:''}`;
   win.status.textContent='Updated '+new Date().toLocaleTimeString('en-GB');
  }catch(error){if(!disposed){win.status.textContent=error.message;win.body.querySelector('.system-status').textContent=error.message;}}
  finally{if(!disposed)timer=setTimeout(refreshStatus,10000);}
 }
 win.onclose=()=>{disposed=true;clearTimeout(timer);statusWindow=null;};
 await refreshStatus();
};
window.Win2kApps.register({type:'explorer-window',restore:async entry=>{folder=entry.folder;await shell.actions.devices();return explorer;}});
window.Win2kApps.register({type:'browser-window',singleton:true,restore:async()=>{await shell.actions.browser();return browserWindow;}});
window.Win2kApps.register({type:'users-window',singleton:true,allowed:user=>user?.role==='admin',restore:async()=>{await shell.actions.users();return usersWindow;}});
window.Win2kApps.register({type:'terminal-window',restore:(entry,{remaining})=>{const term=remaining.get(entry.terminal);if(!term){shell.notify('A previous terminal ended or was lost when the session service restarted.');return null;}remaining.delete(entry.terminal);return startTerminal(term.profile,null,term.id);}});
window.Win2kApps.register({type:'status-window',singleton:true,restore:async()=>{await shell.actions.status();return statusWindow;}});
window.addEventListener('resize',()=>windows.forEach(win=>{if(!win.element.classList.contains('maximized')){const r=win.element.getBoundingClientRect();win.element.style.left=`${Math.max(0,Math.min(r.left,innerWidth-win.element.offsetWidth))}px`;win.element.style.top=`${Math.max(0,Math.min(r.top,innerHeight-100))}px`;}win.onresize?.();}));
window.Win2kDesktop=Object.freeze({api,makeWindow,getUser:()=>account,scheduleWorkspace,listWindows:()=>[...windows],openConnection:profile=>connectDialog(profile),resumeTerminal:term=>startTerminal(term.profile,null,term.id)});
api('/session').then(unlocked).catch(()=>{});
})();
