(() => {
 'use strict';
 const shell=window.Win2kShell,desktop=window.Win2kDesktop,api=desktop.api;
 const windows=new Set(),uploads=new Set();
 let clipboard=null;let loaded=false;let user=null,data={items:[],used:0,reserved:0,quota:52428800},revision=0,refreshing;
 const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const mb=bytes=>(bytes/1048576).toLocaleString('en-GB',{maximumFractionDigits:2})+' MB';
 const find=id=>data.items.find(item=>item.id===id);
 const run=fn=>Promise.resolve().then(fn).catch(error=>shell.notify(error.message));
 function path(id){const parts=[],seen=new Set();while(id!=='files'&&id!=='desktop'){if(seen.has(id))break;seen.add(id);const item=find(id);if(!item)break;parts.unshift(item.name);id=item.parent;}parts.unshift(id==='desktop'?'Desktop':'My Files');return parts.join(' / ');}
 async function refresh(){
  const current=user,ticket=++revision;if(!current)return;
  const next=await api('/files');if(user!==current||ticket!==revision)return;
  data=next;loaded=true;renderDesktop();for(const win of windows)render(win);
 }
 function queueRefresh(){clearTimeout(refreshing);refreshing=setTimeout(()=>run(refresh),100);}
 function quotaHTML(){return `<div class="file-quota"><progress max="${data.quota}" value="${data.used+data.reserved}"></progress><span>${mb(data.used)} of ${mb(data.quota)} used${data.reserved?' · '+mb(data.reserved)+' uploading':''}. The Recycle Bin is included.</span></div>`;}
 function openItem(item){return window.Win2kTools?window.Win2kTools.openItem(item):download(item);}
 function download(item){const a=document.createElement('a');a.href='/api/files/'+item.id+'/download';a.download=item.name;document.body.append(a);a.click();a.remove();}
 async function downloadZip(ids){
  if(!ids.length)throw Error('Select files or folders first.');const response=await fetch('/api/files/archive?'+new URLSearchParams({ids:ids.join(',')}));if(!response.ok){const result=await response.json();throw Error(result.error||'Could not create ZIP archive.');}const url=URL.createObjectURL(await response.blob());const a=document.createElement('a');a.href=url;a.download='my-files.zip';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
 }
 async function newFolder(parent){
  shell.show('New Folder',`<form id="file-name-form"><label class="form-row">Name:<input name="name" required maxlength="180" autocomplete="off" value="New Folder"></label><p class="error"></p><button class="win2k-button">Create</button></form>`);
  const form=document.querySelector('#file-name-form');form.elements.name.select();form.onsubmit=async e=>{e.preventDefault();try{await api('/files/folders','POST',{name:form.elements.name.value,parent});document.querySelector('#window').close();await refresh();}catch(error){form.querySelector('.error').textContent=error.message;}};
 }
 async function rename(item){
  shell.show('Rename',`<form id="file-name-form"><label class="form-row">Name:<input name="name" required maxlength="180" autocomplete="off" value="${esc(item.name)}"></label><p class="error"></p><button class="win2k-button">Save</button></form>`);
  const form=document.querySelector('#file-name-form');form.elements.name.select();form.onsubmit=async e=>{e.preventDefault();try{await api('/files/'+item.id,'PATCH',{name:form.elements.name.value});document.querySelector('#window').close();await refresh();}catch(error){form.querySelector('.error').textContent=error.message;}};
 }
 async function move(item,parent){await api('/files/'+item.id,'PATCH',{parent});await refresh();}
 function chooseMove(item){
  const choices=[{id:'files',label:'My Files'},{id:'desktop',label:'Desktop'},...data.items.filter(row=>row.kind==='folder'&&row.state==='live'&&row.id!==item.id).map(row=>({id:row.id,label:path(row.id)}))];
  shell.show('Move '+item.name,`<form id="file-move-form"><label class="form-row">Destination folder:<select name="parent">${choices.map(row=>`<option value="${row.id}">${esc(row.label)}</option>`).join('')}</select></label><p class="error"></p><button class="win2k-button">Move</button></form>`);
  const form=document.querySelector('#file-move-form');form.onsubmit=async e=>{e.preventDefault();try{await move(item,form.elements.parent.value);document.querySelector('#window').close();}catch(error){form.querySelector('.error').textContent=error.message;}};
 }
 async function trash(item){await api('/files/'+item.id+'/trash','POST',{});await refresh();shell.notify(item.name+' was moved to the Recycle Bin.');}
 async function restore(item){const result=await api('/files/'+item.id+'/restore','POST',{});await refresh();shell.notify('Restored to '+path(result.parent)+(result.name!==item.name?' as '+result.name:''));}
 async function purge(item){if(!confirm('Delete ”'+item.name+'” permanently? This cannot be undone.'))return;await api('/files/'+item.id,'DELETE');await refresh();}
 async function emptyTrash(){
  if(!confirm('Permanently empty your entire Recycle Bin, including files, folders and shortcuts? This cannot be undone.'))return;
  await api('/files/trash','DELETE');
  for(const item of shell.trashShortcuts())await shell.changeTrashShortcut(item.id,true);
  await refresh();
 }
 function pickFiles(parent){const input=document.createElement('input');input.type='file';input.multiple=true;input.onchange=()=>run(()=>uploadFiles([...input.files],parent));input.click();}
 async function uploadFiles(files,parent,displayWindow){
  const owner=user;if(!files.length||!owner)return;
  const win=displayWindow||openFolder(parent);let cancelled=false;
  const progress=document.createElement('div');progress.className='file-upload-progress';
  const label=document.createElement('span'),bar=document.createElement('progress'),cancel=document.createElement('button');
  bar.max=100;cancel.className='win2k-button';cancel.textContent='Cancel';progress.append(label,bar,cancel);win.body.prepend(progress);
  let current;cancel.onclick=()=>{cancelled=true;current?.abort();};
  let success=0;const errors=[];
  try{
   for(let index=0;index<files.length;index++){
    if(cancelled||user!==owner)break;
    const file=files[index],transfer=crypto.randomUUID();window.Win2kTools?.track(transfer,file.name,0,'Uploading',()=>current?.abort());label.textContent=`${index+1}/${files.length}: ${file.name}`;bar.value=0;
    try{
     await new Promise((resolve,reject)=>{
      current=new XMLHttpRequest();uploads.add(current);current.open('POST','/api/files/upload?'+new URLSearchParams({parent,name:file.name}));current.setRequestHeader('Content-Type','application/octet-stream');
      current.upload.onprogress=e=>{if(e.lengthComputable)bar.value=100*e.loaded/e.total;window.Win2kTools?.track(transfer,file.name,Math.round(bar.value),'Uploading',()=>current?.abort());};
      current.onload=()=>{uploads.delete(current);if(current.status>=200&&current.status<300)resolve();else{let message='The upload failed.';try{message=JSON.parse(current.responseText).error||message;}catch{}reject(new Error(message));}};
      current.onerror=()=>{uploads.delete(current);reject(new Error('Network error. The file was not uploaded.'));};
      current.onabort=()=>{uploads.delete(current);reject(new Error('The upload was cancelled.'));};current.send(file);
     });success++;window.Win2kTools?.track(transfer,file.name,100,'Done');
    }catch(error){errors.push(file.name+': '+error.message);window.Win2kTools?.track(transfer,file.name,null,'Failed');}
   }
  }finally{
   progress.remove();if(user===owner){await refresh();win.status.textContent=`${success} filer uppladdade.`+(errors.length?' '+errors.join(' · '):'');if(errors.length)shell.notify(errors[0]);}
  }
 }
 async function uploadPaths(files,parent){
  if(files.length>5000)throw Error('Maximum 5,000 files per upload.');const owner=user,win=openFolder(parent),mapping=new Map([['',parent]]),groups=new Map();
  for(const file of files){if(owner!==user)return;const parts=(file.webkitRelativePath||file.relativePath||file.name).split('/');parts.pop();let path='';
   for(const name of parts){const before=path;path=path?path+'/'+name:name;if(!mapping.has(path)){const target=mapping.get(before),existing=data.items.find(x=>x.parent===target&&x.kind==='folder'&&x.state==='live'&&x.name===name);const result=existing||await api('/files/folders','POST',{name,parent:target});mapping.set(path,result.id);}}
   const target=mapping.get(path);if(!groups.has(target))groups.set(target,[]);groups.get(target).push(file);
  }
  for(const [target,group] of groups){if(owner!==user)return;await uploadFiles(group,target,win);}await refresh();
 }
 async function uploadEntries(entries,parent){
  const files=[],empty=[];let count=0;
  async function walk(entry,prefix=''){
   if(++count>5000)throw Error('Maximum 5,000 items per upload.');
   if(entry.isFile){const file=await new Promise((resolve,reject)=>entry.file(resolve,reject));Object.defineProperty(file,'relativePath',{value:prefix+file.name});files.push(file);return;}
   const path=prefix+entry.name+'/';const reader=entry.createReader();let children=[];while(true){const batch=await new Promise((resolve,reject)=>reader.readEntries(resolve,reject));if(!batch.length)break;children.push(...batch);}if(!children.length)empty.push(path);for(const child of children)await walk(child,path);
  }
  for(const entry of entries)await walk(entry);
  await uploadPaths(files,parent);
  for(const folder of empty){let target=parent;for(const name of folder.split('/').filter(Boolean)){await refresh();const existing=data.items.find(x=>x.parent===target&&x.name===name&&x.kind==='folder'&&x.state==='live');target=existing?.id||(await api('/files/folders','POST',{name,parent:target})).id;}}await refresh();
 }
 function pickFolder(parent){const input=document.createElement('input');input.type='file';input.multiple=true;input.webkitdirectory=true;input.onchange=()=>run(()=>uploadPaths([...input.files],parent));input.click();}
 function acceptDrop(element,parent){
  element.addEventListener('dragover',event=>{if(!user)return;event.preventDefault();event.stopPropagation();if(element.id!=='desktop')element.classList.add('file-drop-target');event.dataTransfer.dropEffect=event.dataTransfer.types.some(type=>['application/x-win2k-file','application/x-win2k-shortcut'].includes(type))?'move':'copy';});
  element.addEventListener('dragleave',()=>element.classList.remove('file-drop-target'));
  element.addEventListener('drop',event=>{event.preventDefault();event.stopPropagation();element.classList.remove('file-drop-target');if(!user)return;const key=event.dataTransfer.getData('application/x-win2k-file'),target=typeof parent==='function'?parent():parent;
   const shortcut=event.dataTransfer.getData('application/x-win2k-shortcut');
   if(shortcut){if(target==='trash')run(()=>shell.trashShortcut(shortcut));return;}
   if(key){const item=find(key);if(item)run(()=>target==='trash'?trash(item):move(item,target));}
   else if(target!=='trash'){
    const entries=[...event.dataTransfer.items].map(item=>item.webkitGetAsEntry?.()).filter(Boolean);if(entries.some(item=>item.isDirectory)){run(()=>uploadEntries(entries,target));return;}
    run(()=>uploadFiles([...event.dataTransfer.files],target));
   }
  });
 }
 function draggable(element,item){element.draggable=true;element.ondragstart=event=>{event.dataTransfer.setData('application/x-win2k-file',item.id);event.dataTransfer.effectAllowed='move';};}
 function context(item,event){
  event.preventDefault();event.stopPropagation();
  document.querySelector('.file-context')?.remove();const menu=document.createElement('div');menu.className='frame context-menu file-context';
  for(const [label,action] of [['Open',()=>item.kind==='folder'?openFolder(item.id):openItem(item)],[item.kind==='folder'?'Download ZIP':'Download',()=>item.kind==='folder'?downloadZip([item.id]):download(item)],['Edit',()=>item.kind==='folder'?window.Win2kEditor.openFolder(item.id):window.Win2kEditor.openFile(item.id)],['Rename…',()=>rename(item)],['Move…',()=>chooseMove(item)],['Move to Recycle Bin',()=>trash(item)]]){
   const b=document.createElement('button');b.textContent=label;b.onclick=()=>{menu.remove();run(action);};menu.append(b);
  }
  document.body.append(menu);menu.style.left=Math.max(0,Math.min(event.clientX,innerWidth-menu.offsetWidth-4))+'px';menu.style.top=Math.max(0,Math.min(event.clientY,innerHeight-menu.offsetHeight-40))+'px';
 }
 function renderDesktop(){
  const root=document.querySelector('#file-icons');root.replaceChildren();
  for(const item of data.items.filter(row=>row.state==='live'&&row.parent==='desktop')){
   const button=document.createElement('button');button.className='desktop-icon';button.dataset.fileId=item.id;button.title=item.name;
   button.innerHTML=`<span class="win2k-pixel-icon win2k-icon-${item.kind==='folder'?'folder':'forms'}" aria-hidden="true"><i></i></span><span class="icon-label">${esc(item.name)}</span>`;
   button.ondblclick=()=>item.kind==='folder'?openFolder(item.id):openItem(item);button.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();button.ondblclick();}if(e.key==='Delete')run(()=>trash(item));};button.oncontextmenu=e=>context(item,e);draggable(button,item);if(item.kind==='folder')acceptDrop(button,item.id);root.append(button);
  }
 }
 function openFolder(parent='files',inTrash=false){
  if(!inTrash&&parent!=='files'&&parent!=='desktop')window.Win2kTools?.recent(parent).catch(e=>shell.notify(e.message));
  shell.closeStart();
  const existing=[...windows].find(win=>win.fileParent===parent&&win.inTrash===inTrash);if(existing){existing.focus();run(refresh);return existing;}
  const win=desktop.makeWindow(inTrash?'Recycle Bin':path(parent),inTrash?'trash-window':'files-window');win.fileParent=parent;win.inTrash=inTrash;win.selected=new Set();windows.add(win);acceptDrop(win.element,()=>win.inTrash?'trash':win.fileParent);
  win.onclose=()=>{windows.delete(win);};render(win);run(refresh);desktop.scheduleWorkspace();return win;
 }
 function render(win){
  let parent=win.fileParent;
  if(win.selectionParent!==parent){win.selected.clear();win.selectionParent=parent;}
  for(const id of win.selected){const item=find(id);if(!item||item.state!=='live'||item.parent!==parent)win.selected.delete(id);}
  if(loaded&&!win.inTrash&&!['files','desktop'].includes(parent)&&(!find(parent)||find(parent).state!=='live')){parent='files';win.fileParent=parent;desktop.scheduleWorkspace();}
  win.title(win.inTrash?'Recycle Bin':path(parent));
  const progress=win.body.querySelector('.file-upload-progress');
  win.body.innerHTML=`<div class="explorer-toolbar file-toolbar">${win.inTrash?'<button class="win2k-button" data-file-action="empty">Empty Recycle Bin…</button>':'<button class="win2k-button" data-file-action="root">My Files</button><button class="win2k-button" data-file-action="desktop">Desktop</button><button class="win2k-button" data-file-action="up">Up</button><button class="win2k-button" data-file-action="folder">New Folder…</button><button class="win2k-button" data-file-action="upload">Upload…</button>'}<button class="win2k-button" data-file-action="refresh">Refresh</button></div><div class="explorer-address">${esc(win.inTrash?'Recycle Bin':path(parent))}</div>${quotaHTML()}<div class="file-list" tabindex="0"><table><thead><tr><th>Name</th><th>Size</th><th>Actions</th></tr></thead><tbody></tbody></table></div>`;
  if(progress)win.body.prepend(progress);
  if(!win.inTrash){
   const toolbar=win.body.querySelector('.file-toolbar');
   for(const [label,fn] of [['Upload Folder…',()=>pickFolder(parent)],['Select All',()=>{win.selected=new Set(data.items.filter(x=>x.parent===parent&&x.state==='live').map(x=>x.id));render(win);}],['Copy',()=>{clipboard={ids:[...win.selected],cut:false};win.status.textContent=clipboard.ids.length+' items copied. Select Paste in the destination folder.';}],['Cut',()=>{clipboard={ids:[...win.selected],cut:true};win.status.textContent=clipboard.ids.length+' items selected for moving.';}],['Paste',async()=>{if(!clipboard?.ids.length)throw Error('Select and copy files first.');if(clipboard.cut){for(const id of clipboard.ids)await api('/files/'+id,'PATCH',{parent});clipboard=null;}else await api('/files/copy','POST',{ids:clipboard.ids,parent});await refresh();}],['Download ZIP',()=>downloadZip([...win.selected])],['Delete Selected',async()=>{if(!win.selected.size)return;if(!confirm('Move '+win.selected.size+' selected items to the Recycle Bin?'))return;for(const id of [...win.selected]){const item=find(id);if(item?.state==='live')await api('/files/'+id+'/trash','POST',{});}win.selected.clear();await refresh();}]]){const b=document.createElement('button');b.className='win2k-button';b.textContent=label;b.onclick=()=>run(fn);toolbar.append(b);}
  }
  const tbody=win.body.querySelector('tbody');const rows=data.items.filter(item=>win.inTrash?item.state==='trash'&&item.trash_root===item.id:item.state==='live'&&item.parent===parent);
  for(const item of rows){
   const row=document.createElement('tr');row.dataset.fileId=item.id;
   row.innerHTML=`<td><span class="file-row-name"><span class="win2k-pixel-icon win2k-icon-${item.kind==='folder'?'folder':'forms'}" aria-hidden="true"><i></i></span><span>${esc(item.name)}</span></span></td><td>${item.kind==='folder'?'Folder':mb(item.size)}</td><td></td>`;
   if(!win.inTrash){const check=document.createElement('input');check.type='checkbox';check.checked=win.selected.has(item.id);check.setAttribute('aria-label','Select '+item.name);check.onclick=e=>e.stopPropagation();check.onchange=()=>{check.checked?win.selected.add(item.id):win.selected.delete(item.id);win.status.textContent=win.selected.size+' selected';};row.firstElementChild.prepend(check);}
   const actions=win.inTrash?[['Restore',()=>restore(item)],['Delete Permanently…',()=>purge(item)]]:[['Open',()=>item.kind==='folder'?openFolder(item.id):openItem(item)],[item.kind==='folder'?'Download ZIP':'Download',()=>item.kind==='folder'?downloadZip([item.id]):download(item)],['Edit',()=>item.kind==='folder'?window.Win2kEditor.openFolder(item.id):window.Win2kEditor.openFile(item.id)],['Rename…',()=>rename(item)],['Move…',()=>chooseMove(item)],['Delete',()=>trash(item)]];
   for(const [label,action] of actions){const button=document.createElement('button');button.className='win2k-button';button.textContent=label;button.onclick=e=>{e.stopPropagation();run(action);};row.lastElementChild.append(button);}
   if(!win.inTrash){row.ondblclick=()=>item.kind==='folder'?openFolder(item.id):openItem(item);row.oncontextmenu=e=>context(item,e);draggable(row,item);if(item.kind==='folder')acceptDrop(row,item.id);}
   tbody.append(row);
  }
  if(win.inTrash){
   for(const item of shell.trashShortcuts()){
    const row=document.createElement('tr');row.innerHTML=`<td>${esc(item.name)}</td><td>Shortcut</td><td></td>`;
    for(const [label,permanent] of [['Restore',false],['Delete Permanently…',true]]){const b=document.createElement('button');b.className='win2k-button';b.textContent=label;b.onclick=()=>run(async()=>{if(permanent&&!confirm('Permanently delete the shortcut?'))return;await shell.changeTrashShortcut(item.id,permanent);await refresh();});row.lastElementChild.append(b);}tbody.append(row);
   }
  }
  if(!tbody.children.length){const row=document.createElement('tr');row.innerHTML=`<td colspan="3">${win.inTrash?'The Recycle Bin is empty.':'The folder is empty. Drop files here to upload them.'}</td>`;tbody.append(row);}
  const actions={empty:emptyTrash,root:()=>{win.fileParent='files';render(win);desktop.scheduleWorkspace();},desktop:()=>{win.fileParent='desktop';render(win);desktop.scheduleWorkspace();},up:()=>{win.fileParent=find(parent)?.parent||'files';render(win);desktop.scheduleWorkspace();},folder:()=>newFolder(parent),upload:()=>pickFiles(parent),refresh};
  win.body.querySelectorAll('[data-file-action]').forEach(button=>button.onclick=()=>run(actions[button.dataset.fileAction]));
  if(!win.inTrash)acceptDrop(win.body.querySelector('.file-list'),()=>win.fileParent);
  win.status.textContent=win.inTrash?'Files in the Recycle Bin use storage until permanently deleted.':'Drag files here from your computer. Drag a file to a folder, the desktop or the Recycle Bin to move it.';
 }
 shell.actions.files=()=>openFolder('files');shell.actions.trash=()=>openFolder('files',true);
 shell.actions['new-folder']=()=>newFolder('desktop');shell.actions['upload-desktop']=()=>pickFiles('desktop');
 window.Win2kApps.register({type:'files-window',restore:entry=>openFolder(entry.folder||'files')});
 window.Win2kApps.register({type:'trash-window',singleton:true,restore:()=>openFolder('files',true)});
 acceptDrop(document.querySelector('#desktop [data-action=files]'),'files');acceptDrop(document.querySelector('#desktop'),'desktop');acceptDrop(document.querySelector('[data-action=trash]'),'trash');
 // A desktop icon drop can be consumed before the file drop handler runs.
 // Clear hover feedback at the document boundary, including cancelled drags.
 function clearDropTargets(){document.querySelectorAll('.file-drop-target').forEach(element=>element.classList.remove('file-drop-target'));}
 document.addEventListener('drop',clearDropTargets,true);
 document.addEventListener('dragend',clearDropTargets,true);
 window.addEventListener('blur',clearDropTargets);
 document.addEventListener('click',event=>{if(!event.target.closest('.file-context'))document.querySelector('.file-context')?.remove();});
 document.addEventListener('dragover',event=>{if(user&&event.dataTransfer.types.includes('Files'))event.preventDefault();});
 document.addEventListener('drop',event=>{if(user&&event.dataTransfer.types.includes('Files')){event.preventDefault();run(()=>uploadFiles([...event.dataTransfer.files],'files'));}});
 window.Win2kFiles={openFolder,refresh,uploadFiles,path};
 function changeUser(next){clipboard=null;for(const xhr of uploads)xhr.abort();uploads.clear();user=next;loaded=false;revision++;data={items:[],used:0,reserved:0,quota:next?.storage_quota||52428800};document.querySelector('.file-context')?.remove();renderDesktop();if(user)run(refresh);}
 window.addEventListener('win2k-user',event=>changeUser(event.detail));window.addEventListener('win2k-files-refresh',queueRefresh);
 window.addEventListener('focus',()=>{if(user)queueRefresh();});changeUser(desktop.getUser());
})();
