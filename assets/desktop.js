(() => {
'use strict';
const $ = (s) => document.querySelector(s);
let desktopUser = null, desktopApi = null, saveQueue = Promise.resolve();
let shortcuts = [], positions = {};
function safeUrl(value) {
 try { const url = new URL(value); return ['https:', 'http:'].includes(url.protocol) ? url.href : null; } catch { return null; }
}
function notify(message) { $('#notice').textContent = message; $('#notice').hidden = false; clearTimeout(notify.timer); notify.timer = setTimeout(() => $('#notice').hidden = true, 5000); }
function save() {
 const user = desktopUser, data = {shortcuts: structuredClone(shortcuts), color: currentColor, positions:structuredClone(positions)};
 if (!user) return;
 saveQueue = saveQueue.then(async () => {
  if (desktopUser !== user) return;
  try { await desktopApi('/desktop', 'PUT', data); }
  catch (error) { if (desktopUser === user) notify('Could not save: '+error.message); }
 });
 render();
}
async function setUser(user, api) {
 desktopUser = user; desktopApi = api; shortcuts = []; positions = {}; currentColor = '#3a6ea5';
 document.body.style.backgroundColor = currentColor; $('#notice').hidden = true; render();
 if (!user) return;
 let data = await api('/desktop');
 if (desktopUser !== user) return;
 // Previous browser-wide settings belong only to the original owner.
 if (data === null && user.is_owner) {
  try {
   const legacy = JSON.parse(localStorage.getItem('win2k.shortcuts.v1') || '[]');
   const color = localStorage.getItem('win2k.background');
   data = {shortcuts: Array.isArray(legacy) ? legacy.filter(x => x && typeof x.id === 'string' && typeof x.name === 'string' && safeUrl(x.url)).map(x => ({id:x.id, name:x.name, url:safeUrl(x.url), desktop:!!x.desktop, start:!!x.start, deleted:!!x.deleted})) : [], color: ['#3a6ea5','#008080','#2d4739'].includes(color) ? color : '#3a6ea5'};
  } catch { data = {shortcuts:[], color:'#3a6ea5'}; }
  await api('/desktop', 'PUT', data);
  if (desktopUser !== user) return;
  try { localStorage.removeItem('win2k.shortcuts.v1'); localStorage.removeItem('win2k.background'); } catch {}
 }
 if (data) { shortcuts = data.shortcuts; currentColor = data.color; positions = data.positions || {}; }
 document.body.style.backgroundColor = currentColor; render();
}
function button(label, action) { const el = document.createElement('button'); el.textContent = label; el.dataset.action = action; return el; }
function link(item, desktop = false) { const el = document.createElement('a'); el.href = item.url; el.target = '_blank'; el.rel = 'noopener noreferrer'; if (desktop) { el.className = 'desktop-icon'; el.dataset.shortcutId=item.id; const icon = document.createElement('span'); icon.className = 'win2k-pixel-icon win2k-icon-forms'; icon.append(document.createElement('i')); icon.setAttribute('aria-hidden','true'); el.append(icon); } const label = document.createElement('span'); label.className = desktop ? 'icon-label' : 'link-label'; label.textContent = item.name; el.append(label); return el; }
function render() {
 $('#custom-icons').replaceChildren(...shortcuts.filter(x => x.desktop && !x.deleted).map(x => link(x, true)));
 const programs = $('#programs'); programs.replaceChildren();
 function category(label,entries,icon='folder') {
  const details=document.createElement('details'),summary=document.createElement('summary'),panel=document.createElement('div');
  summary.innerHTML='<span class="win2k-pixel-icon win2k-icon-'+icon+'" aria-hidden="true"></span><span class="menu-label"></span><span class="menu-arrow" aria-hidden="true">▸</span>';
  summary.querySelector('.menu-label').textContent=label;panel.className='submenu';panel.append(...entries);details.append(summary,panel);programs.append(details);
 }
 category('Accessories',[button('My Files','files'),button('Notes','notes'),button('Calculator','calculator'),button('Search and Favourites','search')]);
 category('Development and Drawing',[button('Code Editor','editor'),button('Dimension Drawing','cad')],'editor');
 category('Internet and Connections',[button('Browser','browser'),button('My Devices','devices'),button('SFTP – File Transfer','sftp')],'browser');
 category('System Tools',[button('Task Manager','taskmanager'),button('My Activities','activities'),button('System Status','status'),button('My Settings','preferences')],'settings');
 category('My Shortcuts',[...shortcuts.filter(x=>x.start&&!x.deleted).map(x=>link(x)),button('Manage Shortcuts…','links'),button('New Shortcut…','add')]);
 bindStartMenus();window.Win2kUI?.decorate(document.querySelector('#start-menu'));

}
// Fixed positioning lets cascades extend beyond the scrollable Start list.
function positionSubmenu(details) {
 if (!details.open || $('#start-menu').hidden) return;
 const panel = details.querySelector(':scope > .submenu');
 const menu = (details.parentElement.closest('.submenu')||$('#start-menu')).getBoundingClientRect();
 const row = details.querySelector('summary').getBoundingClientRect();
 const bottom = document.querySelector('.taskbar').getBoundingClientRect().top - 4;
 panel.style.maxHeight = `${Math.max(0, bottom - 4)}px`;
 const width = panel.offsetWidth;
 let left = menu.right - 3;
 if (left + width > innerWidth - 4) {
  left = menu.left - width + 3;
  if (left < 4) left = Math.max(4, innerWidth - width - 4);
 }
 panel.style.left = `${left}px`;
 panel.style.top = `${Math.max(4, Math.min(row.top - 2, bottom - panel.offsetHeight))}px`;
}
function openSubmenu(details, focus = false) {
 $('#start-menu').querySelectorAll('details').forEach(d => { if(!d.contains(details))d.open=false; }); details.open=true;
 positionSubmenu(details);
 if (focus) details.querySelector(':scope > .submenu summary,:scope > .submenu a,:scope > .submenu button')?.focus();
}
function positionOpenSubmenus() {
 $('#start-menu').querySelectorAll('details[open]').forEach(positionSubmenu);
}
function closeStart() { $('#start-menu').hidden = true; $('#start-button').setAttribute('aria-expanded', 'false'); $('#start-menu').querySelectorAll('details').forEach(x => x.open = false); }
function toggleStart() { const open = $('#start-menu').hidden; closeStart(); $('#start-menu').hidden = !open; $('#start-button').setAttribute('aria-expanded', String(open)); if (open) $('#start-menu summary').focus(); }
function show(title, html) { closeStart(); $('#desktop-menu').hidden = true; $('#window-title').textContent = title; $('#window-content').innerHTML = html; if (!$('#window').open) $('#window').showModal(); }
function listing(items, trash = false) {
 const list = document.createElement('ul'); list.className = 'link-list';
 if (!items.length) { const p = document.createElement('p'); p.className = 'empty'; p.textContent = trash ? 'The Recycle Bin is empty.' : 'No shortcuts to display.'; return p; }
 items.forEach(item => { const row = document.createElement('li'); const a = link(item); const meta = document.createElement('small'); meta.textContent = item.url; a.append(meta); row.append(a); const remove = button(trash ? 'Restore' : 'Delete', ''); remove.className = 'win2k-button'; remove.removeAttribute('data-action'); remove.setAttribute('aria-label', `${remove.textContent} ${item.name}`); remove.onclick = () => { item.deleted = !trash; save(); actions[trash ? 'trash' : 'links'](); }; row.append(remove); list.append(row); }); return list;
}
const actions = {
 add() {
  show('Create Shortcut', '<form id="shortcut-form"><label class="form-row">Name:<input name="name" required maxlength="80"></label><label class="form-row">Web Address:<input name="url" type="url" placeholder="https://" required></label><fieldset><legend>Show shortcut on</legend><label class="check-row"><input type="checkbox" name="desktop" checked> Desktop</label><label class="check-row"><input type="checkbox" name="start" checked> Start → Programs</label></fieldset><p id="form-error" class="error" role="alert"></p><div class="actions"><button type="button" class="win2k-button" data-action="close">Cancel</button><button class="win2k-button default">Create</button></div></form>');
  $('#shortcut-form').onsubmit = event => { event.preventDefault(); const f = event.target.elements; const url = safeUrl(f.url.value); if (!f.name.value.trim() || !url || (!f.desktop.checked && !f.start.checked)) { $('#form-error').textContent = 'Enter a name, an HTTP or HTTPS address and at least one location.'; return; } shortcuts.push({id: `${Date.now()}-${Math.random().toString(36).slice(2)}`, name:f.name.value.trim(), url, desktop:f.desktop.checked, start:f.start.checked, deleted:false}); save(); $('#window').close(); };
 },
 links() { show('My Shortcuts', '<p>Your links on this desktop.</p><button class="win2k-button" data-action="add">New Shortcut…</button>'); $('#window-content').append(listing(shortcuts.filter(x => !x.deleted))); },
 computer() { show('My Computer', '<p>Find your shortcuts and desktop settings here.</p><div class="actions"><button class="win2k-button" data-action="links">My Shortcuts</button><button class="win2k-button" data-action="settings">Control Panel</button></div>'); },
 trash() { show('Recycle Bin', '<p>Restore deleted shortcuts here.</p>'); $('#window-content').append(listing(shortcuts.filter(x => x.deleted), true)); },
 search() { show('Search', '<label class="form-row">Search shortcuts:<input id="search-input" type="search" placeholder="Name or web address"></label><p id="search-count" role="status"></p><div id="search-results"></div>'); const search = () => { const q = $('#search-input').value.toLocaleLowerCase('en'); const found = shortcuts.filter(x => !x.deleted && `${x.name} ${x.url}`.toLocaleLowerCase('en').includes(q)); $('#search-count').textContent = `${found.length} shortcuts`; $('#search-results').replaceChildren(listing(found)); }; $('#search-input').oninput = search; search(); $('#search-input').focus(); },
 settings() { show('Control Panel – Display', '<form id="settings-form"><fieldset><legend>Desktop</legend><label class="form-row">Background:<select name="color"><option value="#3a6ea5">Windows 2000 Blue</option><option value="#008080">Classic Teal</option><option value="#2d4739">Dark Green</option></select></label></fieldset><p>Shortcuts and background are saved for your account.</p><button type="button" class="win2k-button" data-action="links">Manage Shortcuts…</button><div class="actions"><button class="win2k-button default">OK</button></div></form>'); $('#settings-form').elements.color.value = document.body.style.backgroundColor ? currentColor : '#3a6ea5'; $('#settings-form').onsubmit = e => { e.preventDefault(); currentColor = e.target.elements.color.value; document.body.style.backgroundColor = currentColor; save(); $('#window').close(); }; },
 help() { show('Desktop Help', '<p><b>Start and Applications</b></p><p>Start → Programs contains Accessories, Development and Drawing, Internet and Connections, and System Tools. Your links are in My Shortcuts. Search finds your files, folders, applications and connections.</p><p><b>Application Menus</b></p><p>File contains commands to open, create and save. Edit contains actions for the content. View controls the display. Help explains the current application. Common actions are also available in the toolbar.</p><p><b>Files and Devices</b></p><p>Drag files from your computer to My Files or the desktop. Click Actions next to a file for more commands. Restore deleted items using the Recycle Bin. Create SSH profiles in My Devices and double-click to connect. The Connection menu in Code Editor opens remote files via SFTP.</p><p><b>Appearance and Keyboard</b></p><p>Change text size and background under Start → Settings. Icon positions are saved for your account. Ctrl+Esc opens Start. F10 focuses the application menu. Alt+F opens File, Alt+E Edit and Alt+V View. Use the arrow keys, Enter and Escape in menus.</p><p><b>Private Desktop</b></p><p>Files, connections and settings belong to your account. SSH jobs continue when the window is closed. Enter passwords when connecting; they are not stored permanently.</p>'); },
 run() { show('Run', '<form id="run-form"><p>Enter the web address you want to open.</p><label class="form-row">Open:<input name="url" type="url" required placeholder="https://"></label><p class="error" id="run-error" role="alert"></p><div class="actions"><button type="button" class="win2k-button" data-action="close">Cancel</button><button class="win2k-button default">OK</button></div></form>'); $('#run-form').onsubmit = e => { e.preventDefault(); const url = safeUrl(e.target.elements.url.value); if (!url) { $('#run-error').textContent = 'Enter an HTTP or HTTPS address.'; return; } window.open(url, '_blank', 'noopener,noreferrer'); $('#window').close(); }; },
 logout() { /* Server logout is installed by devices.js. */ },
 shutdown() { show('Log off Pi-2000Web', '<p>Log off? Your SSH jobs will continue on the server and your windows will be restored when you log in again.</p><div class="actions"><button class="win2k-button" data-action="close">Cancel</button><button class="win2k-button" data-action="logout">Log Off</button></div>'); },
 close() { $('#window').close(); }
};
let currentColor = '#3a6ea5';
document.body.style.backgroundColor = currentColor;
// Server authentication is installed by devices.js.
$('#start-button').onclick = toggleStart;
$('#close-window').onclick = actions.close;
document.addEventListener('click', e => { const action = e.target.closest('[data-action]'); if (action && !$('#session').hidden) Promise.resolve().then(()=>actions[action.dataset.action]?.()).catch(error=>notify(error.message)); if (!e.target.closest('#start-menu,#start-button')) closeStart(); if (!e.target.closest('#desktop-menu')) $('#desktop-menu').hidden = true; });
$('#desktop').addEventListener('contextmenu', e => { if (e.target.closest('a,button')) return; e.preventDefault(); closeStart(); const menu = $('#desktop-menu'); menu.hidden = false; menu.style.left = `${Math.max(0,Math.min(e.clientX,innerWidth-menu.offsetWidth-4))}px`; menu.style.top = `${Math.max(0,Math.min(e.clientY,innerHeight-menu.offsetHeight-40))}px`; menu.querySelector('button').focus(); });
document.addEventListener('keydown', e => {
 if ($('#session').hidden) return;
 if (e.key === 'Escape') {
  const expanded = [...$('#start-menu').querySelectorAll('details[open]')].at(-1);
  if (expanded && !$('#start-menu').hidden) { e.preventDefault(); expanded.open = false; expanded.querySelector('summary').focus(); return; }
  closeStart(); $('#desktop-menu').hidden = true;
 }
 if (!$('#start-menu').hidden && e.key === 'ArrowRight') {
  const summary = document.activeElement.closest('#start-menu summary');
  if (summary) { e.preventDefault(); openSubmenu(summary.parentElement, true); }
 }
 if (!$('#start-menu').hidden && e.key === 'ArrowLeft') {
  const details = document.activeElement.closest('#start-menu details[open]');
  if (details) { e.preventDefault(); details.open = false; details.querySelector('summary').focus(); }
 }
 if (e.key === 'F1') { e.preventDefault(); actions.help(); }
 if (e.ctrlKey && e.key === 'Escape' && !$('#window').open) { e.preventDefault(); toggleStart(); }
 if (!$('#start-menu').hidden && ['ArrowDown','ArrowUp'].includes(e.key)) { e.preventDefault(); const panel=document.activeElement.closest('.submenu,.start-items')||$('#start-menu .start-items');const nodes = [...panel.querySelectorAll('summary,button,a')].filter(x => x.getClientRects().length&&x.closest('.submenu,.start-items')===panel&&!x.hidden); const i = nodes.indexOf(document.activeElement); nodes[(i + (e.key === 'ArrowDown' ? 1 : -1) + nodes.length) % nodes.length]?.focus(); }
});
function bindStartMenus(){
 $('#start-menu').querySelectorAll('details').forEach(details=>{
  if(details.dataset.bound)return;details.dataset.bound='true';const summary=details.querySelector(':scope > summary');summary.setAttribute('aria-haspopup','menu');
  summary.addEventListener('click',event=>{event.preventDefault();event.stopPropagation();if(details.open&&!matchMedia('(hover: hover)').matches)details.open=false;else openSubmenu(details);});
  summary.addEventListener('mouseenter',()=>{if(matchMedia('(hover: hover)').matches)openSubmenu(details);});
  details.addEventListener('toggle',()=>{summary.setAttribute('aria-expanded',String(details.open));positionOpenSubmenus();});
 });
 $('#start-menu').querySelectorAll('.start-items > button,.submenu > button,.submenu > a').forEach(button=>{
  if(button.dataset.startBound)return;button.dataset.startBound='true';button.addEventListener('mouseenter',()=>{if(matchMedia('(hover: hover)').matches)button.parentElement.querySelectorAll('details').forEach(d=>d.open=false);});
 });
}
bindStartMenus();
window.addEventListener('resize', positionOpenSubmenus);
$('#start-menu .start-items').addEventListener('scroll', positionOpenSubmenus);
function clock() { const now = new Date(); $('#clock').textContent = now.toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit'}); $('#clock').title = now.toLocaleDateString('en-GB',{dateStyle:'full'}); $('#clock').dateTime = now.toISOString(); }
window.Win2kShell = {getPositions:()=>positions, setPosition(key,point){positions[key]=point;save();}, actions, show, notify, closeStart, setUser,
 trashShortcuts:()=>shortcuts.filter(item=>item.deleted).map(item=>({...item})),
 async changeTrashShortcut(id,permanent=false){
  const user=desktopUser;
  saveQueue=saveQueue.catch(()=>{}).then(async()=>{
   if(desktopUser!==user)return;
   const next=permanent?shortcuts.filter(item=>item.id!==id):shortcuts.map(item=>item.id===id?{...item,deleted:false}:item);
   await desktopApi('/desktop','PUT',{shortcuts:next,color:currentColor,positions:structuredClone(positions)});
   if(desktopUser===user){shortcuts=next;render();}
  });
  return saveQueue;
 }

};
render(); clock(); setInterval(clock, 30000);
})();
