/* Account-owned desktop objects and Windows-style interaction. */
(() => {
'use strict';
const shell=Win2kShell,root=document.querySelector('#desktop-icons'),desktop=document.querySelector('#desktop');
const defaults={sort:'manual',direction:'asc',autoArrange:false,snap:false,showIcons:true,openMode:'double'};
const catalog=new Map(),selected=new Set();
// Resolve former default labels at display time; retain personal names and stored IDs.
const formerNames={iptv:'IPTV Player',vault:'Vault',about:'About Pi-2000Web',arduino:'Arduino Workshop',calculator:'Calculator',database:'MariaDB Manager',apitester:'API Tester',git:'Git Projects'};
let menu=null,anchor=null,cancelSelection=null,suppressClick=false;
const key=icon=>icon.dataset.fileId?'file:'+icon.dataset.fileId:icon.dataset.shortcutId?'link:'+icon.dataset.shortcutId:'app:'+icon.dataset.action;
const options=()=>({...defaults,...shell.getView()});
const visible=()=>[...root.querySelectorAll('.desktop-icon')].filter(el=>!el.hidden&&options().showIcons);
const run=fn=>Promise.resolve().then(fn).catch(e=>shell.notify(e.message));
for(const el of root.querySelectorAll(':scope > .desktop-icon'))catalog.set(el.dataset.action,{name:el.querySelector('.icon-label').textContent,initial:true,element:el});
for(const [action,name] of Object.entries({notes:'Notes',database:'Pi-DB Manager',apitester:'Pi-API',git:'Pi-Git Projects',sftp:'SFTP – File Transfer',taskmanager:'Task Manager',activities:'My Activities',status:'System Status',about:'About Pi-2000',preferences:'My Settings',settings:'Control Panel',help:'Desktop Help',localterminal:'Local Terminal'})){
 if(!catalog.has(action))catalog.set(action,{name,initial:action==='localterminal'});
}
function allowed(action){return action!=='localterminal'||shell.getUser()?.role==='admin';}
function closeMenu(focus=false){menu?.remove();menu=null;if(focus&&anchor?.isConnected)anchor.focus();}
function paint(){for(const el of root.querySelectorAll('.desktop-icon')){const yes=selected.has(key(el));el.classList.toggle('desktop-selected',yes);el.setAttribute('aria-pressed',String(yes));}}
function select(el,add=false,toggle=false){if(!add)selected.clear();if(el){const id=key(el);if(toggle&&selected.has(id))selected.delete(id);else selected.add(id);el.focus({preventScroll:true});}paint();}
function sync(){
 const state=shell.getDesktop();
 for(const [action,entry] of catalog){
  let el=root.querySelector(':scope > [data-action="'+action+'"]');
  if(!el&&allowed(action)&&(entry.initial||state.icons[action]?.visible)){
   el=document.createElement('button');el.type='button';el.className='desktop-icon';el.dataset.action=action;
   const image=document.createElement('span');image.className='win2k-pixel-icon win2k-icon-forms';image.setAttribute('aria-hidden','true');const label=document.createElement('span');label.className='icon-label';el.append(image,label);root.append(el);
  }
  if(!el)continue;
  el.hidden=!allowed(action)||!(state.icons[action]?.visible??entry.initial);
  const label=el.querySelector('.icon-label'),stored=state.icons[action]?.name,name=stored&&stored!==formerNames[action]?stored:entry.name;if(label.textContent!==name)label.textContent=name;
  el.title=name;
 }
 root.classList.toggle('desktop-icons-hidden',!options().showIcons);
 for(const id of selected)if(!visible().some(el=>key(el)===id))selected.delete(id);
 paint();window.Win2kUI?.decorate(root);window.dispatchEvent(new Event('win2k-icons-changed'));
}
function info(el){
 if(el.dataset.fileId){const item=Win2kFiles.getItem(el.dataset.fileId);return {key:key(el),name:item?.name||el.textContent,type:item?.kind==='folder'?'Folder':item?.name.includes('.')?item.name.split('.').at(-1).toUpperCase()+' file':'File',item};}
 if(el.dataset.shortcutId){const item=shell.getShortcut(el.dataset.shortcutId);return {key:key(el),name:item?.name||el.textContent,type:'Web shortcut',item};}
 return {key:key(el),name:el.querySelector('.icon-label').textContent,type:'Application',action:el.dataset.action};
}
function open(el){const d=info(el);if(d.action)return shell.actions[d.action]?.();if(d.type==='Web shortcut')return shell.actions.browser(d.item.url);if(d.item)return Win2kFiles.openDesktopItem(d.item.id);}
function form(title,content,submit){
 closeMenu();shell.show(title,content);const f=document.querySelector('#window-content form'),owner=shell.getUser();
 f.addEventListener('submit',async event=>{event.preventDefault();if(owner!==shell.getUser())return;const buttons=[...f.querySelectorAll('button')];buttons.forEach(b=>b.disabled=true);try{await submit(f);if(owner===shell.getUser()&&f.isConnected)document.querySelector('#window').close();}catch(e){if(f.isConnected){f.querySelector('.error').textContent=e.message;buttons.forEach(b=>b.disabled=false);}}});
 f.querySelector('input,select')?.focus();return f;
}
function rename(el){const d=info(el);if(d.item&&d.type!=='Web shortcut')return Win2kFiles.renameDesktopItem(d.item.id);
 const f=form('Rename Desktop Icon','<form><label class="form-row">Name:<input name="name" maxlength="80" required autocomplete="off"></label><p class="error" role="alert"></p><div class="actions"><button type="button" class="win2k-button" data-action="close">Cancel</button><button class="win2k-button">Save</button></div></form>',async f=>{
  const name=f.elements.name.value.trim();if(!name)throw Error('Enter a name.');
  await shell.updateDesktop(state=>{if(d.action)state.icons[d.action]={name,visible:true};else{const item=state.shortcuts.find(x=>x.id===d.item.id);if(item)item.name=name;}});
 });f.elements.name.value=d.name;f.elements.name.select();
}
async function remove(elements){
 const objects=elements.map(info);if(!objects.length)return;
 if(!confirm('Remove '+objects.length+' selected desktop item'+(objects.length===1?'':'s')+'? Files and web shortcuts go to the Recycle Bin. Applications remain available in Start.'))return;
 await shell.updateDesktop(state=>{for(const d of objects){if(d.action)state.icons[d.action]={name:d.name,visible:false};else if(d.type==='Web shortcut'){const item=state.shortcuts.find(x=>x.id===d.item.id);if(item)item.deleted=true;}}});
 for(const d of objects)if(d.item&&d.type!=='Web shortcut')await Win2kFiles.trashDesktopItem(d.item.id);
 selected.clear();paint();await Win2kFiles.refresh();
}
function properties(el){
 const d=info(el);closeMenu();shell.show('Properties – '+d.name,'<dl class="desktop-properties"></dl><div class="actions"><button class="win2k-button" data-action="close">Close</button></div>');
 const rows=[['Name',d.name],['Type',d.type],['Location','Your desktop']];
 if(d.action)rows.push(['Application',catalog.get(d.action)?.name||d.action],['Removing this icon','Only the desktop shortcut is removed.']);
 else if(d.type==='Web shortcut')rows.push(['Address',d.item.url]);
 else if(d.item)rows.push(['Size',d.item.kind==='folder'?'Folder':d.item.size+' bytes'],['Modified',new Date(d.item.modified*1000).toLocaleString()]);
 const dl=document.querySelector('.desktop-properties');for(const [label,value] of rows){const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=label;dd.textContent=value;dl.append(dt,dd);}
}
function editLink(el){const d=info(el),f=form('Shortcut Properties','<form><label class="form-row">Name:<input name="name" required maxlength="80"></label><label class="form-row">Web Address:<input name="url" type="url" required maxlength="4096"></label><label class="check-row"><input name="desktop" type="checkbox">Desktop</label><label class="check-row"><input name="start" type="checkbox">Start → Programs</label><p class="error" role="alert"></p><div class="actions"><button type="button" class="win2k-button" data-action="close">Cancel</button><button class="win2k-button">Save</button></div></form>',async f=>{
 const url=new URL(f.elements.url.value);if(!['http:','https:'].includes(url.protocol))throw Error('Use an HTTP or HTTPS address.');
 if(!f.elements.name.value.trim()||(!f.elements.desktop.checked&&!f.elements.start.checked))throw Error('Enter a name and select at least one location.');
 await shell.updateDesktop(state=>{const item=state.shortcuts.find(x=>x.id===d.item.id);if(item)Object.assign(item,{name:f.elements.name.value.trim(),url:url.href,desktop:f.elements.desktop.checked,start:f.elements.start.checked});});
 });for(const k of ['name','url'])f.elements[k].value=d.item[k];for(const k of ['desktop','start'])f.elements[k].checked=d.item[k];}
function manage(){
 const state=shell.getDesktop();const f=form('Desktop Icons','<form><p>Choose the applications shown on your desktop. Removing an icon does not uninstall the application.</p><div class="desktop-app-picker"></div><div class="actions"><button type="button" class="win2k-button" data-restore>Restore Defaults</button><button type="button" class="win2k-button" data-action="close">Cancel</button><button class="win2k-button">Save</button></div><p class="error" role="alert"></p></form>',async f=>shell.updateDesktop(next=>{for(const input of f.querySelectorAll('[data-app]'))next.icons[input.dataset.app]={name:f.dataset.restoreNames?catalog.get(input.dataset.app).name:next.icons[input.dataset.app]?.name||catalog.get(input.dataset.app).name,visible:input.checked};}));
 const box=f.querySelector('.desktop-app-picker');for(const [action,entry] of [...catalog].filter(([id])=>allowed(id)).sort((a,b)=>a[1].name.localeCompare(b[1].name))){const label=document.createElement('label');label.className='check-row';const c=document.createElement('input');c.type='checkbox';c.dataset.app=action;c.checked=state.icons[action]?.visible??entry.initial;label.append(c,document.createTextNode(entry.name));box.append(label);}
 f.querySelector('[data-restore]').onclick=()=>{f.dataset.restoreNames='true';for(const input of box.querySelectorAll('input'))input.checked=catalog.get(input.dataset.app).initial;};
}
function settings(){
 const o=options(),f=form('Desktop Options','<form><fieldset><legend>Opening icons</legend><label class="form-row">Open with:<select name="openMode"><option value="double">Double-click (single-click selects)</option><option value="single">Single-click</option></select></label></fieldset><fieldset><legend>Arrangement</legend><label class="check-row"><input type="checkbox" name="autoArrange">Auto arrange icons</label><label class="check-row"><input type="checkbox" name="snap">Align dragged icons to grid</label><label class="check-row"><input type="checkbox" name="showIcons">Show desktop icons</label></fieldset><p class="error" role="alert"></p><div class="actions"><button type="button" class="win2k-button" data-action="close">Cancel</button><button class="win2k-button">Save</button></div></form>',async f=>shell.updateDesktop(state=>{state.view={...options(),openMode:f.elements.openMode.value};for(const k of ['autoArrange','snap','showIcons'])state.view[k]=f.elements[k].checked;}));
 f.elements.openMode.value=o.openMode;for(const k of ['autoArrange','snap','showIcons'])f.elements[k].checked=o[k];
}
function showMenu(event,entries,from){
 event.preventDefault();event.stopImmediatePropagation();closeMenu();shell.closeStart();document.querySelector('#desktop-menu').hidden=true;document.querySelector('.file-context')?.remove();anchor=from||desktop;
 menu=document.createElement('div');menu.className='frame context-menu desktop-context file-context';menu.setAttribute('role','menu');
 for(const entry of entries){if(!entry){const line=document.createElement('hr');menu.append(line);continue;}const b=document.createElement('button');b.type='button';b.textContent=entry.label;b.setAttribute('aria-label',entry.label);b.disabled=!!entry.disabled;if(entry.checked!==undefined){b.setAttribute('role','menuitemcheckbox');b.setAttribute('aria-checked',String(entry.checked));b.textContent=(entry.checked?'✓ ':'   ')+entry.label;}b.onclick=()=>{closeMenu();run(entry.run);};menu.append(b);}
 document.body.append(menu);const point=from?.getBoundingClientRect();menu.style.left=Math.max(4,Math.min(event.clientX||point?.left||4,innerWidth-menu.offsetWidth-4))+'px';menu.style.top=Math.max(4,Math.min(event.clientY||point?.bottom||4,innerHeight-menu.offsetHeight-42))+'px';menu.querySelector('button:not(:disabled)')?.focus();
 menu.onkeydown=e=>{const nodes=[...menu.querySelectorAll('button:not(:disabled)')],i=nodes.indexOf(document.activeElement);if(['ArrowDown','ArrowUp','Home','End'].includes(e.key)){e.preventDefault();e.stopPropagation();nodes[e.key==='Home'?0:e.key==='End'?nodes.length-1:(i+(e.key==='ArrowDown'?1:-1)+nodes.length)%nodes.length]?.focus();}if(e.key==='Escape'||e.key==='Tab'){e.preventDefault();e.stopPropagation();closeMenu(true);}};
}
function context(event,el){
 if(el){if(!selected.has(key(el)))select(el);const d=info(el),many=selected.size>1;
 const fileIds=visible().filter(e=>selected.has(key(e))).map(e=>e.dataset.fileId),onlyFiles=fileIds.length>0&&fileIds.every(Boolean);
 const entries=[{label:'Open',disabled:many,run:()=>open(el)},...(!many&&el.dataset.fileId?Win2kFiles.desktopActions(el.dataset.fileId):[]),{label:'Rename…',disabled:many,run:()=>rename(el)},null,{label:'Cut',disabled:!onlyFiles,run:()=>Win2kFiles.copyDesktopItems(fileIds,true)},{label:'Copy',disabled:!onlyFiles,run:()=>Win2kFiles.copyDesktopItems(fileIds)},{label:'Paste into Folder',disabled:many||d.type!=='Folder'||!Win2kFiles.canPaste(),run:()=>Win2kFiles.pasteDesktopItems(d.item.id)},null,{label:many?'Remove Selected…':d.action?'Remove from Desktop…':'Move to Recycle Bin',run:()=>{if(!many&&!d.action)return d.type==='Web shortcut'?shell.trashShortcut(d.item.id):Win2kFiles.trashDesktopItem(d.item.id);return remove(visible().filter(e=>selected.has(key(e))));}},null,{label:'Properties',disabled:many,run:()=>d.type==='Web shortcut'?editLink(el):properties(el)}];
 showMenu(event,entries,el);return;
 }
 selected.clear();paint();const o=options();showMenu(event,[
 {label:'Paste',disabled:!Win2kFiles.canPaste(),run:()=>Win2kFiles.pasteDesktopItems()},null,{label:'Desktop Icons…',run:manage},{label:'New Shortcut…',run:()=>shell.actions.add()},{label:'New Folder…',run:()=>shell.actions['new-folder']()},{label:'Upload Files…',run:()=>shell.actions['upload-desktop']()},null,
 {label:'Sort by Name',run:()=>Win2kIconLayout.arrange('name')},{label:'Sort by Type',run:()=>Win2kIconLayout.arrange('type')},{label:'Sort by Size',run:()=>Win2kIconLayout.arrange('size')},{label:'Sort by Modified',run:()=>Win2kIconLayout.arrange('modified')},{label:'Reverse Sort Order',checked:o.direction==='desc',run:()=>Win2kIconLayout.arrange(o.sort==='manual'?'name':o.sort,o.direction==='asc'?'desc':'asc')},
 {label:'Auto Arrange',checked:o.autoArrange,run:()=>shell.updateDesktop(s=>{s.view={...o,autoArrange:!o.autoArrange};})},{label:'Align to Grid',run:()=>Win2kIconLayout.align()},null,
 {label:'Show Desktop Icons',checked:o.showIcons,run:()=>shell.updateDesktop(s=>{s.view={...o,showIcons:!o.showIcons};})},{label:'Refresh Desktop',run:async()=>{await shell.reloadDesktop();await Win2kFiles.refresh();}},
 {label:'Desktop Options…',run:settings},{label:'Properties',run:()=>shell.actions.settings()}
 ]);
}
root.addEventListener('click',event=>{const el=event.target.closest('.desktop-icon');if(!el)return;event.preventDefault();event.stopImmediatePropagation();if(suppressClick){suppressClick=false;return;}select(el,event.ctrlKey||event.metaKey||event.shiftKey,event.ctrlKey||event.metaKey);if(event.detail===0||options().openMode==='single'&&!(event.ctrlKey||event.metaKey||event.shiftKey))run(()=>open(el));},true);
root.addEventListener('dblclick',event=>{const el=event.target.closest('.desktop-icon');if(!el)return;event.preventDefault();event.stopImmediatePropagation();if(options().openMode==='double')run(()=>open(el));},true);
desktop.addEventListener('contextmenu',event=>{if(event.target.closest('.app-window'))return;context(event,event.target.closest('.desktop-icon'));},true);
desktop.tabIndex=0;
desktop.addEventListener('keydown',event=>{
 if(event.target.closest('.app-window')||document.querySelector('#window').open)return;
 const el=event.target.closest('.desktop-icon'),nodes=visible().sort((a,b)=>(parseInt(a.style.left)-parseInt(b.style.left))||(parseInt(a.style.top)-parseInt(b.style.top)));let handled=true;
 if(event.key==='F2'&&el)run(()=>rename(el));
 else if(event.key==='Delete'&&el){if(!selected.has(key(el)))select(el);run(()=>remove(nodes.filter(e=>selected.has(key(e)))));}
 else if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='a'){nodes.forEach(e=>selected.add(key(e)));paint();}
 else if(event.key==='ContextMenu'||event.shiftKey&&event.key==='F10'){context(event,el);}
 else if((event.ctrlKey||event.metaKey)&&['c','x','v'].includes(event.key.toLowerCase())){
  const command=event.key.toLowerCase(),ids=nodes.filter(e=>selected.has(key(e))).map(e=>e.dataset.fileId);
  if(command==='v')run(()=>Win2kFiles.pasteDesktopItems());else if(ids.length&&ids.every(Boolean))Win2kFiles.copyDesktopItems(ids,command==='x');
 }
 else if(event.key===' '&&el)select(el,event.ctrlKey,event.ctrlKey);
 else if(event.key==='Enter'&&el)run(()=>open(el));
 else if(['ArrowUp','ArrowDown','ArrowLeft','ArrowRight','Home','End'].includes(event.key)){
  let next;if(event.key==='Home'||!el)next=nodes[0];else if(event.key==='End')next=nodes.at(-1);else{
   const r=el.getBoundingClientRect(),horizontal=['ArrowLeft','ArrowRight'].includes(event.key),sign=['ArrowLeft','ArrowUp'].includes(event.key)?-1:1;
   next=nodes.filter(n=>n!==el).map(n=>{const q=n.getBoundingClientRect(),dx=q.x-r.x,dy=q.y-r.y;return {n,main:(horizontal?dx:dy)*sign,side:Math.abs(horizontal?dy:dx)};}).filter(x=>x.main>1).sort((a,b)=>(a.main+a.side*4)-(b.main+b.side*4))[0]?.n;
  }if(next){select(next,event.shiftKey);next.scrollIntoView({block:'nearest',inline:'nearest'});}
 }else if(event.key==='Escape'){selected.clear();paint();}else handled=false;
 if(handled){event.preventDefault();event.stopImmediatePropagation();}
},true);
// Native HTML drag retains file/folder drop semantics; background pointer selection is separate.
desktop.addEventListener('pointerdown',event=>{
 if(event.button!==0||event.target.closest('.desktop-icon,.app-window')||document.querySelector('#window').open)return;
 closeMenu();cancelSelection?.();desktop.focus({preventScroll:true});const start={x:event.clientX,y:event.clientY},before=new Set(event.ctrlKey||event.shiftKey?selected:[]);
 selected.clear();for(const id of before)selected.add(id);paint();
 const box=document.createElement('div');box.className='desktop-selection-box';document.body.append(box);
 function move(e){const x=Math.min(start.x,e.clientX),y=Math.min(start.y,e.clientY),w=Math.abs(start.x-e.clientX),h=Math.abs(start.y-e.clientY);Object.assign(box.style,{left:x+'px',top:y+'px',width:w+'px',height:h+'px'});selected.clear();for(const id of before)selected.add(id);if(w+h>5)for(const icon of visible()){const r=icon.getBoundingClientRect();if(r.left<x+w&&r.right>x&&r.top<y+h&&r.bottom>y)selected.add(key(icon));}paint();}
 function end(){box.remove();cancelSelection=null;window.removeEventListener('pointermove',move);window.removeEventListener('pointerup',end);window.removeEventListener('pointercancel',end);}
 cancelSelection=end;window.addEventListener('pointermove',move);window.addEventListener('pointerup',end);window.addEventListener('pointercancel',end);
});

document.querySelector('#programs').addEventListener('contextmenu',event=>{
 const el=event.target.closest('[data-action],[data-shortcut-id]');if(!el)return;
 const action=el.dataset.action,link=el.dataset.shortcutId;
 if(!(action&&catalog.has(action)&&allowed(action))&&!link)return;
 showMenu(event,[{label:'Open',run:()=>action?shell.actions[action]?.():shell.actions.browser(shell.getDesktop().shortcuts.find(x=>x.id===link).url)},
 {label:'Send to Desktop',run:async()=>{await shell.updateDesktop(state=>{if(action)state.icons[action]={name:state.icons[action]?.name||catalog.get(action).name,visible:true};else{const item=state.shortcuts.find(x=>x.id===link);if(item)item.desktop=true;}});shell.notify('Shortcut added to your desktop.');}}],el);
},true);

document.addEventListener('pointerdown',e=>{if(menu&&!menu.contains(e.target))closeMenu();});
window.addEventListener('win2k-user',()=>{closeMenu();cancelSelection?.();selected.clear();sync();});
window.addEventListener('win2k-desktop-render',sync);
window.addEventListener('win2k-files-render',()=>{paint();window.dispatchEvent(new Event('win2k-icons-changed'));});
// Existing background menu remains an accessible fallback for earlier clients.
shell.actions['desktop-icons']=manage;shell.actions['desktop-options']=settings;
window.Win2kDesktopManager={key,options,visible,info,selected,select,sync,remove,afterDrag(){suppressClick=true;setTimeout(()=>suppressClick=false,100);},context};
sync();
})();
