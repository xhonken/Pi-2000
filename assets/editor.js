(() => {
 'use strict';
 const desktop=window.Win2kDesktop,shell=window.Win2kShell,api=desktop.api;
 let recovery=Promise.resolve();let win=null,editor=null,tabs=[],active=null,items=[],parent='files',owner=null;
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const run=fn=>Promise.resolve().then(fn).catch(e=>shell.notify(e.message));
 const dirty=tab=>tab.session.getValue()!==tab.saved;
 const mode=name=>ace.require('ace/ext/modelist').getModeForPath(name).mode;
 async function request(path,options={}){const response=await fetch('/api'+path,options);const data=await response.json();if(!response.ok)throw new Error(data.error||'Could not read or save the file.');return data;}
 async function refresh(){if(window.Win2kRemoteEditor?.visible())return window.Win2kRemoteEditor.refresh();const current=owner;const data=await api('/files');if(current!==owner||!win)return;items=data.items.filter(x=>x.state==='live');if(!['files','desktop'].includes(parent)&&!items.some(x=>x.id===parent))parent='files';tree();}
 function tree(){
  if(window.Win2kRemoteEditor?.visible())return;
  const area=win.body.querySelector('.editor-tree');area.replaceChildren();
  function entry(item,depth){const b=document.createElement('button');b.className='editor-tree-entry';b.dataset.kind=item.kind;b.style.paddingLeft=(8+depth*14)+'px';b.textContent=(item.kind==='folder'?'▸ ':'')+item.name;b.title=item.name;b.classList.toggle('selected',item.id===parent);b.onclick=()=>item.kind==='folder'?selectParent(item.id):run(()=>openFile(item.id));area.append(b);}
  function children(id,depth,seen=new Set()){if(seen.has(id)||depth>40)return;seen.add(id);for(const item of items.filter(x=>x.parent===id).sort((a,b)=>(a.kind==='file')-(b.kind==='file')||a.name.localeCompare(b.name))){entry(item,depth);if(item.kind==='folder')children(item.id,depth+1,seen);}}
  for(const [id,name] of [['files','My Files'],['desktop','Desktop']]){entry({id,name,kind:'folder'},0);children(id,1);}
  const folder=items.find(x=>x.id===parent)?.name||(parent==='desktop'?'Desktop':'My Files');win.body.querySelector('.editor-location').textContent='Working Folder: '+folder;
 }
 function selectParent(id){parent=id;win.fileParent=id;desktop.scheduleWorkspace();tree();}
 function renderTabs(){
  if(!win)return;win.editorFiles=tabs.filter(t=>t.id).map(t=>t.id);desktop.scheduleWorkspace();const bar=win.body.querySelector('.editor-tabs');bar.replaceChildren();
  for(const tab of tabs){const group=document.createElement('span');group.className='editor-tab'+(tab===active?' active':'');const b=document.createElement('button');b.textContent=(dirty(tab)?'● ':'')+tab.name+(tab.remote?' [SFTP]':'');b.title=tab.remote?tab.remote.label+' · '+tab.remote.path:tab.name;b.onclick=()=>select(tab);const close=document.createElement('button');close.textContent='×';close.setAttribute('aria-label','Close '+tab.name);close.onclick=()=>closeTab(tab);group.append(b,close);bar.append(group);}
  win.title((active?active.name+(dirty(active)?' *':'')+' – ':'')+'Code Editor');
 }
 function status(){if(!win||!active)return;const pos=editor.getCursorPosition();win.status.textContent=`Line ${pos.row+1}, column ${pos.column+1} · UTF-8 · ${new TextEncoder().encode(active.session.getValue()).length} byte · ${dirty(active)?'Unsaved Changes':'Saved'} · Ctrl+S Save · Ctrl+F Search · Ctrl+H Replace`+(active.remote?' · SFTP: '+active.remote.label+' '+active.remote.path:' · My Files');}
 function select(tab){active=tab;editor.setSession(tab.session);renderTabs();status();editor.focus();}
 function addTab(name,text='',id=null,version=null,fileParent=parent,remote=null){
  if(tabs.length>=100)throw new Error('Maximum 100 file tabs. Close a tab first.');
  const session=ace.createEditSession(text);session.setUseWorker(false);session.setMode(mode(name));session.setTabSize(4);session.setUseSoftTabs(true);
  const tab={name,id,version,remote,parent:fileParent,session,saved:text,draftKey:'draft-'+crypto.randomUUID(),draftVersion:'',draftTimer:null,draftQueue:Promise.resolve(),draftReady:false};tabs.push(tab);
  session.on('change',()=>{scheduleDraft(tab);renderTabs();status();});session.selection.on('changeCursor',status);select(tab);return tab;
 }
 function scheduleDraft(tab){clearTimeout(tab.draftTimer);tab.draftReady=false;tab.draftTimer=setTimeout(()=>persistDraft(tab).catch(e=>{if(win)win.status.textContent='Draft not saved: '+e.message;}),800);}
 function persistDraft(tab){
  const current=owner,snapshot={name:tab.name,text:tab.session.getValue(),file:tab.id,version:tab.version,parent:tab.parent,remote:tab.remote};
  tab.draftQueue=tab.draftQueue.catch(()=>{}).then(async()=>{if(owner!==current||!tabs.includes(tab))return;const response=await window.Win2kTools.req('/documents/'+tab.draftKey,'PUT',snapshot,tab.draftVersion);if(owner!==current)return;tab.draftVersion=response.version;tab.draftReady=tab.session.getValue()===snapshot.text;if(win)win.status.textContent='Recovery draft saved on the server · Ctrl+S saves the file itself.';});return tab.draftQueue;
 }
 function removeDraft(tab){clearTimeout(tab.draftTimer);const current=owner;const promise=tab.draftQueue.catch(()=>{}).then(()=>owner===current?api('/documents/'+tab.draftKey,'DELETE'):undefined);promise.catch(e=>shell.notify(e.message));return promise;}
 async function recoverDrafts(){
  const current=owner;const listing=await api('/documents');
  for(const entry of listing.documents.filter(x=>x.key.startsWith('draft-'))){const result=await window.Win2kTools.req('/documents/'+entry.key);if(current!==owner||!win)return;const doc=result.data;if(!doc||typeof doc.text!=='string'||typeof doc.name!=='string')continue;
   if(tabs.length===1&&!tabs[0].id&&!tabs[0].remote&&!dirty(tabs[0])){tabs[0].session.destroy();tabs=[];}
   const tab=addTab(doc.name,doc.text,doc.file||null,doc.version||null,doc.parent||'files',doc.remote||null);tab.saved=null;tab.draftKey=entry.key;tab.draftVersion=result.version;tab.draftReady=true;
  }
  renderTabs();if(listing.documents.some(x=>x.key.startsWith('draft-'))&&win)win.status.textContent='Your unsaved drafts have been recovered. Ctrl+S saves the files.';
 }
 function closeTab(tab){if(dirty(tab)&&!confirm('Close ”'+tab.name+'” without saving changes?'))return;removeDraft(tab);tabs=tabs.filter(t=>t!==tab);tab.session.destroy();if(active===tab){if(tabs.length)select(tabs[tabs.length-1]);else addTab('untitled.txt');}renderTabs();}
 async function openFile(id){
  if(!win)open();await recovery;window.Win2kTools?.recent(id).catch(e=>shell.notify(e.message));const existing=tabs.find(t=>t.id===id);if(existing){select(existing);return;}
  const current=owner,result=await request('/files/'+id+'/content');if(owner!==current||!win)return;
  if(tabs.length===1&&!tabs[0].id&&!tabs[0].remote&&!dirty(tabs[0])){tabs[0].session.destroy();tabs=[];}
  addTab(result.name,result.text,id,result.version,result.parent);
 }
 function destination(title,initial,submit){
  shell.show(title,`<form id="editor-save-form"><label class="form-row">File name:<input name="name" required maxlength="180" value="${esc(initial)}"></label><label class="form-row">Folder:<select name="parent">${[['files','My Files'],['desktop','Desktop'],...items.filter(x=>x.kind==='folder').map(x=>[x.id,folderPath(x)])].map(([id,name])=>`<option value="${id}" ${id===parent?'selected':''}>${esc(name)}</option>`).join('')}</select></label><p class="error" role="alert"></p><button class="win2k-button">Save</button></form>`);
  const form=document.querySelector('#editor-save-form');form.elements.name.select();form.onsubmit=async e=>{e.preventDefault();const button=form.querySelector('button');button.disabled=true;try{await submit(form.elements.name.value,form.elements.parent.value);document.querySelector('#window').close();}catch(error){form.querySelector('.error').textContent=error.message;}finally{button.disabled=false;}};
 }
 function folderPath(item){const names=[item.name],seen=new Set([item.id]);let p=item.parent;while(!['files','desktop'].includes(p)&&!seen.has(p)){seen.add(p);const row=items.find(x=>x.id===p);if(!row)break;names.unshift(row.name);p=row.parent;}return (p==='desktop'?'Desktop':'My Files')+' / '+names.join(' / ');}
 async function save(as=false){
  const tab=active;if(!tab||tab.saving)return;
  if(tab.remote&&!as){tab.saving=true;try{const current=owner,text=tab.session.getValue();const result=await window.Win2kRemoteEditor.save(tab,text);if(current!==owner||!win)return;tab.version=result.version;tab.remote.path=result.path;tab.saved=text;await removeDraft(tab);tab.draftVersion='';tab.draftReady=false;if(dirty(tab))scheduleDraft(tab);renderTabs();status();}finally{tab.saving=false;}return;}
  if(as||!tab.id){const data=await api('/files');items=data.items.filter(x=>x.state==='live');destination(tab.remote?'Save Copy in My Files':'Save As',tab.name,async(name,target)=>{
   const current=owner,text=tab.session.getValue(),body=new Blob([text],{type:'application/octet-stream'});if(body.size>1048576)throw new Error('Code Editor supports up to 1 MB per file.');
   const result=await request('/files/upload?'+new URLSearchParams({parent:target,name}),{method:'POST',body});
   if(current!==owner||!win)return;
   tab.remote=null;tab.id=result.id;tab.name=name;tab.parent=target;tab.saved=text;await removeDraft(tab);tab.draftVersion='';tab.draftReady=false;if(dirty(tab))scheduleDraft(tab);
   tab.version=await digest(text);tab.session.setMode(mode(name));renderTabs();status();await refresh();window.dispatchEvent(new Event('win2k-files-refresh'));
  });return;}
  tab.saving=true;
  try{const current=owner,text=tab.session.getValue();const result=await request('/files/'+tab.id+'/content',{method:'PUT',headers:{'Content-Type':'text/plain;charset=utf-8','If-Match':tab.version},body:text});if(current!==owner||!win)return;tab.version=result.version;tab.saved=text;await removeDraft(tab);tab.draftVersion='';tab.draftReady=false;if(dirty(tab))scheduleDraft(tab);renderTabs();status();await refresh();window.dispatchEvent(new Event('win2k-files-refresh'));}
  finally{tab.saving=false;}
 }
 async function digest(text){return [...new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text)))].map(x=>x.toString(16).padStart(2,'0')).join('');}
 async function clipboardAction(action){
  if(!active)return;const tab=active,current=owner;
  if(action==='paste'){const text=await navigator.clipboard.readText();if(owner!==current||active!==tab||!editor)throw Error('The active file changed. Paste again.');editor.insert(text);return;}
  const range=editor.getSelectionRange(),text=tab.session.getTextRange(range),snapshot=tab.session.getValue();await navigator.clipboard.writeText(text);
  if(action==='cut'&&owner===current&&tabs.includes(tab)){if(tab.session.getValue()!==snapshot)throw Error('The text was copied but not cut because the file changed.');tab.session.remove(range);}
 }
 function exportFile(){if(!active)return;const url=URL.createObjectURL(new Blob([active.session.getValue()],{type:'text/plain;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download=active.name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
 function open(){
  shell.closeStart();if(win){win.focus();return win;}owner=desktop.getUser();win=desktop.makeWindow('Code Editor','editor-window');win.fileParent=parent;
  win.body.innerHTML='<div class="editor-toolbar explorer-toolbar"></div><div class="editor-location"></div><div class="editor-layout"><aside class="editor-tree" aria-label="Files and Folders"></aside><div class="editor-main"><div class="editor-tabs"></div><div class="editor-code" aria-label="Code"></div></div></div>';
  ace.config.set('basePath','/assets/vendor/ace');editor=ace.edit(win.body.querySelector('.editor-code'));editor.setTheme('ace/theme/textmate');editor.setOptions({fontSize:14,showPrintMargin:false,enableBasicAutocompletion:true,enableLiveAutocompletion:true});
  const commands=[['SFTP – Open Device…',()=>window.Win2kRemoteEditor.connect()],['My Files',()=>{window.Win2kRemoteEditor.local();return refresh();}],['New Local File',()=>addTab('untitled.txt')],['New Local Folder',()=>destination('New Working Folder','New Folder',async(name,target)=>{const result=await api('/files/folders','POST',{name,parent:target});await refresh();selectParent(result.id);window.dispatchEvent(new Event('win2k-files-refresh'));})],['Save',()=>save()],['Save As…',()=>save(true)],['Save Copy on Device…',()=>window.Win2kRemoteEditor.saveCopy(active)],['Open Device Version',()=>window.Win2kRemoteEditor.readDisk(active)],['Download',exportFile],['Send to Device…',()=>{if(!active?.id||dirty(active))throw Error('Save the file before sending it to the device.');window.Win2kTools.sftp(active.id);}],['Search',()=>editor.execCommand('find')],['Find/Replace',()=>editor.execCommand('replace')],['Cut',()=>clipboardAction('cut')],['Copy',()=>clipboardAction('copy')],['Paste',()=>clipboardAction('paste')],['Select All',()=>editor.selectAll()],['Undo',()=>editor.undo()],['Redo',()=>editor.redo()],['Word Wrap',()=>active.session.setUseWrapMode(!active.session.getUseWrapMode())],['Theme',()=>editor.setTheme(editor.getTheme().includes('monokai')?'ace/theme/textmate':'ace/theme/monokai')],['Refresh Files',refresh]];
  for(const [label,fn] of commands){const b=document.createElement('button');b.className='win2k-button';b.textContent=label;b.onclick=()=>run(fn);win.body.querySelector('.editor-toolbar').append(b);}
  editor.commands.addCommand({name:'savePrivateFile',bindKey:{win:'Ctrl-S',mac:'Command-S'},exec:()=>run(()=>save())});
  editor.commands.addCommand({name:'savePrivateFileAs',bindKey:{win:'Ctrl-Shift-S',mac:'Command-Shift-S'},exec:()=>run(()=>save(true))});
  win.onresize=()=>editor?.resize();win.beforeclose=async()=>{try{await Promise.all(tabs.filter(dirty).map(persistDraft));return true;}catch(error){return confirm('Drafts could not be saved. Close anyway and lose unsaved changes?');}};
  win.onclose=()=>{window.Win2kRemoteEditor?.close();for(const tab of tabs){clearTimeout(tab.draftTimer);tab.session.destroy();}editor.destroy();win=null;editor=null;tabs=[];active=null;owner=null;items=[];parent='files';};
  addTab('untitled.txt');recovery=recoverDrafts().catch(e=>shell.notify('Could not recover drafts: '+e.message));run(refresh);return win;
 }
 window.Win2kEditor={remoteContext:()=>({win,owner,active,tabs,addTab,select,refresh,status,renderTabs}),openFile:id=>run(()=>openFile(id)),openFolder:id=>{open();window.Win2kRemoteEditor?.local();selectParent(id);run(refresh);}};
 const logout=shell.actions.logout;shell.actions.logout=async()=>{try{await Promise.all(tabs.filter(dirty).map(persistDraft));}catch(error){if(!confirm('Drafts could not be saved. Log off anyway?'))return;}return logout();};
 shell.actions.editor=open;
 window.Win2kApps.register({type:'editor-window',singleton:true,restore:async entry=>{const w=open();parent=entry.folder||'files';w.fileParent=parent;for(const id of entry.editorFiles||[]){try{await openFile(id);}catch(e){shell.notify(e.message);}}return w;}});
 window.addEventListener('win2k-files-refresh',()=>{if(win)run(refresh);});
 window.addEventListener('beforeunload',e=>{if(tabs.some(tab=>dirty(tab)&&!tab.draftReady)){e.preventDefault();e.returnValue='';}});
})();
