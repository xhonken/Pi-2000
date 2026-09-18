/* Personal Pi-Vault: list and content keys have separate, explicit lifetimes. */
(() => {
 'use strict';
 const d=Pi2000Desktop,s=Pi2000Shell,c=PiVaultCrypto,esc=Pi2000Development.esc;
 const categories=['Password','API key','Text','Link'];let current=null;
 const channel=typeof BroadcastChannel==='function'?new BroadcastChannel('pi2000-vault-session'):null;
 window.addEventListener('pi2000-user',()=>channel?.postMessage('session-changed'));
 if(channel)channel.onmessage=()=>current?.close(true);
 const password=(name,label)=>`<label>${label}<input name="${name}" type="password" autocomplete="off" required maxlength="512" spellcheck="false"></label>`;
 const newPasswords=()=>password('newA','New password A (at least 14 characters)')+password('repeatA','Repeat password A')+password('newB','New password B (different, at least 14 characters)')+password('repeatB','Repeat password B');
 function pair(f){const a=f.elements.newA.value,b=f.elements.newB.value;if(a!==f.elements.repeatA.value||b!==f.elements.repeatB.value)throw Error('The repeated passwords do not match.');c.strong(a,b);return [a,b];}
 function download(name,text,type='application/json'){const url=URL.createObjectURL(new Blob([text],{type})),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
 function open(){
  s.closeStart();if(current){current.focus();return current;}
  const owner=d.getUser()?.id;if(!owner)return;
  const w=d.makeWindow('Pi-Vault','vault-window');current=w;
  let closed=false,epoch=0,busy=false,operation=null,revision=0,vault=null,listKey=null,index=null,selected=null,contentKey=null,entry=null;
  let listDeadline=0,entryDeadline=0,formSensitive=false,lastPoll=0,polling=false;
  const $=q=>w.body.querySelector(q),alive=()=>!closed&&d.getUser()?.id===owner;
  w.body.innerHTML='<div class="tool-toolbar vault-toolbar"></div><div class="vault-message" role="alert" hidden></div><div class="vault-content"></div>';
  const commands={};
  function status(text){if(alive())w.status.textContent=text;}
  function message(text){if(!alive())return;$('.vault-message').hidden=!text;$('.vault-message').textContent=text;}
  function clearDOM(){w.uiLastFocus=null;for(const el of w.body.querySelectorAll('input,textarea'))el.value='';$('.vault-content').replaceChildren();}
  function abort(){epoch++;operation?.abort();operation=null;busy=false;}
  function clearEntry(){contentKey=null;entry=null;entryDeadline=0;formSensitive=false;}
  function touch(){if(entryDeadline&&Date.now()>=entryDeadline){closeEntry('Entry locked after inactivity. Unsaved edits were discarded.');return false;}if(listKey&&listDeadline&&Date.now()>=listDeadline){lock('Pi-Vault locked after inactivity.');return false;}if(listKey)listDeadline=Date.now()+300000;if(contentKey||formSensitive)entryDeadline=Date.now()+30000;return true;}
  function updateCommands(){for(const [name,b] of Object.entries(commands))b.disabled=busy||((['New Entry','Open Entry','Delete Entry','Export Encrypted'].includes(name))&&!listKey)||(name==='Open Entry'||name==='Delete Entry')&&!selected;commands['Lock Pi-Vault'].disabled=false;commands['Close Entry'].disabled=!contentKey&&!formSensitive;}
  function lock(reason='Pi-Vault locked.'){
   abort();clearEntry();listKey=null;index=null;selected=null;listDeadline=0;clearDOM();renderLocked();message(reason);
  }
  function closeEntry(reason='Entry locked. Password B is required to open any entry.'){
   abort();clearEntry();clearDOM();if(listKey)renderList();else renderLocked();message(reason);
  }
  function check(ticket){if(!alive()||ticket!==epoch)throw Error('Pi-Vault locked or account changed.');if(listKey&&listDeadline&&Date.now()>=listDeadline){lock('Pi-Vault locked after inactivity.');throw Error('Pi-Vault locked.');}if(entryDeadline&&Date.now()>=entryDeadline){closeEntry('Entry locked after 30 seconds of inactivity. Unsaved edits were discarded.');throw Error('Entry locked.');}}
  async function request(path='',method='GET',payload,signal){
   const r=await fetch('/api/vault'+path,{method,cache:'no-store',headers:{'Content-Type':'application/json','X-Vault-Owner':String(owner),'If-Match':String(revision)},body:payload===undefined?undefined:JSON.stringify(payload),signal});
   const result=await r.json();if(!alive())throw Error('The account changed.');
   if(!r.ok){if([401,403].includes(r.status))lock('Account changed or session ended.');const error=Error(result.error||'Pi-Vault request failed.');error.status=r.status;throw error;}
   if(result.owner!==owner){lock('Account mismatch.');throw Error('Account mismatch.');}return result;
  }
  async function run(fn){
   if(busy||!alive()||!touch())return;busy=true;message('');updateCommands();const ticket=epoch,controller=new AbortController();operation=controller;status('Working locally…');
   const controls=[...w.body.querySelectorAll('.vault-form input,.vault-form select,.vault-form textarea,.vault-form button:not([data-cancel])')];controls.forEach(el=>el.disabled=true);
   try{await fn({ticket,signal:controller.signal,check:()=>check(ticket)});}catch(e){if(alive()&&ticket===epoch){if(e.status===409)lock(e.message);else message(e.name==='AbortError'?'Operation cancelled.':e.message);}}
   finally{controls.forEach(el=>el.disabled=false);if(ticket===epoch){busy=false;operation=null;updateCommands();}}
  }
  async function persist(next,ctx){ctx.check();const result=await request('','PUT',next,ctx.signal);ctx.check();vault=next;revision=result.revision;}
  function command(name,fn){const b=document.createElement('button');b.className='pi2000-button';b.type='button';b.textContent=name;b.onclick=fn;$('.vault-toolbar').append(b);commands[name]=b;}
  function form(title,html,submitLabel,onSubmit,{sensitive=true,cancel=()=>closeEntry()}={}){
   clearDOM();formSensitive=sensitive;entryDeadline=sensitive?Date.now()+30000:0;
   $('.vault-content').innerHTML=`<form class="vault-form" autocomplete="off"><h2>${esc(title)}</h2>${html}<div class="vault-form-actions"><button type="button" class="pi2000-button" data-cancel>Cancel</button><button class="pi2000-button" type="submit">${esc(submitLabel)}</button></div></form>`;
   const f=$('.vault-form');f.querySelector('[data-cancel]').onclick=cancel;
   f.onsubmit=e=>{e.preventDefault();run(async ctx=>{try{await onSubmit(f,ctx);}finally{for(const el of f.querySelectorAll('input[type=password]'))el.value='';}});};
   f.querySelector('input,textarea,select')?.focus();updateCommands();return f;
  }
  async function load(ctx){const result=await request('','GET',undefined,ctx.signal);ctx.check();vault=result.vault?c.validate(result.vault):null;revision=result.revision;renderLocked();}
  function renderLocked(){
   if(!alive())return;
   if(!crypto.subtle||!window.Worker){$('.vault-content').textContent='Pi-Vault requires HTTPS, Web Crypto and Web Workers.';return;}
   if(!vault){form('Create your private Pi-Vault','<p>Passwords A and B are separate from your Pi-2000 login. Only A opens the list; B is required for each secret. Save the recovery key outside this server.</p>'+newPasswords(),'Create Pi-Vault',async(f,ctx)=>{const [a,b]=pair(f),result=await c.create(a,b,ctx.signal);ctx.check();await persist(result.vault,ctx);showRecovery(result.recovery);},{sensitive:true,cancel:()=>w.close()});status('No Pi-Vault created for this account.');}
   else{form('Unlock your Pi-Vault',`<p>Signed in as <b>${esc(d.getUser().username)}</b>. Password A opens titles, categories and dates. Secrets stay encrypted.</p>`+password('a','Password A'),'Unlock List',async(f,ctx)=>{const key=await c.unlock(vault,'a',f.elements.a.value,ctx.signal);ctx.check();const data=await c.readIndex(vault,key);ctx.check();listKey=key;index=data;clearEntry();touch();renderList();},{sensitive:false,cancel:()=>w.close()});status('Locked · private to your account');}
   updateCommands();
  }
  function showRecovery(code){
   clearEntry();listKey=null;index=null;selected=null;clearDOM();formSensitive=true;entryDeadline=Date.now()+30000;
   $('.vault-content').innerHTML='<section class="vault-recovery"><h2>Save your recovery key</h2><p>This key unlocks both levels. Keep it outside the Pi and never share it. It is not sent to the server. Locking this window hides it.</p><textarea aria-label="Recovery key" readonly spellcheck="false"></textarea><p><button class="pi2000-button" data-download>Download Recovery Key</button> <button class="pi2000-button" data-done>I Have Saved My Key</button></p></section>';
   $('textarea').value=code;code='';$('[data-download]').onclick=()=>{check(epoch);download('pi2000-vault-recovery.txt',$('textarea').value+'\n','text/plain');touch();};$('[data-done]').onclick=()=>lock('Recovery key hidden. Unlock with password A.');updateCommands();
  }
  function renderList(){
   clearDOM();formSensitive=false;$('.vault-content').innerHTML='<div class="vault-filters"><label>Search titles<input type="search" name="search" autocomplete="off"></label><label>Category<select name="category"><option value="">All categories</option>'+categories.map(x=>`<option>${x}</option>`).join('')+'</select></label></div><div class="vault-table"><table><thead><tr><th>Title</th><th>Category</th><th>Created</th><th>Last changed</th></tr></thead><tbody></tbody></table></div><p class="vault-hint">List unlocked. Secrets remain encrypted. Select an entry and choose Open Entry; password B is required every time.</p>';
   function rows(){const query=$('[name=search]').value.toLocaleLowerCase(),category=$('[name=category]').value,body=$('tbody');body.replaceChildren();for(const item of index.items.filter(i=>i.title.toLocaleLowerCase().includes(query)&&(!category||i.category===category)).sort((a,b)=>a.title.localeCompare(b.title))){const row=document.createElement('tr');row.innerHTML=`<td><button type="button" class="vault-title">${esc(item.title)}</button></td><td>${esc(item.category)}</td><td title="${esc(new Date(item.created).toISOString())}">${esc(new Date(item.created).toLocaleDateString('en-GB'))}<br><small>${Math.max(0,Math.floor((Date.now()-item.created)/86400000))} days ago</small></td><td>${esc(new Date(item.updated).toLocaleString('en-GB'))}</td>`;row.classList.toggle('selected',selected===item.id);row.querySelector('button').onclick=()=>{selected=item.id;rows();updateCommands();};row.querySelector('button').ondblclick=()=>openEntry(item.id);body.append(row);}if(!body.children.length)body.innerHTML='<tr><td colspan="4">No matching entries.</td></tr>';}
   $('[name=search]').oninput=rows;$('[name=category]').onchange=rows;rows();status(index.items.length+' entries · list unlocked · secrets locked');updateCommands();
  }
  function requireList(){if(!listKey||!index)throw Error('Unlock the list with password A first.');check(epoch);}
  function askB(title,action){requireList();closeEntry('');form(title,password('b','Password B')+'<p>This unlocks only this operation. Password B is requested again after closing an entry.</p>','Unlock Content',async(f,ctx)=>{const key=await c.unlock(vault,'b',f.elements.b.value,ctx.signal);ctx.check();await action(key,ctx);});}
  function openEntry(id=null){
   if(busy)return;askB(id?'Open Entry':'New Entry',async(key,ctx)=>{const value=id?await c.readEntry(vault,key,id):{username:'',url:'',secret:'',notes:''};ctx.check();entry={id:id||c.id(),isNew:!id};contentKey=key;touch();renderEntry(value);});
  }
  function renderEntry(value){
   const item=index.items.find(i=>i.id===entry.id)||{title:'',category:'Password'},id=entry.id;
   const f=form(entry.isNew?'New Entry':'Private Entry',`<p>Content locks after 30 seconds without activity. Closing locks it immediately. Save edits before leaving.</p><label>Title<input name="title" required maxlength="200"></label><label>Category<select name="category">${categories.map(x=>`<option>${x}</option>`).join('')}</select></label><label>Username<input name="username" maxlength="32768" autocomplete="off"></label><label>URL<input name="url" maxlength="32768" autocomplete="off" spellcheck="false"></label><label>Secret<textarea name="secret" rows="4" maxlength="32768" spellcheck="false" hidden autocomplete="off"></textarea><input type="password" value="********" readonly aria-label="Hidden secret" data-mask></label><div class="vault-entry-actions"><button type="button" class="pi2000-button" data-reveal>Show Secret</button><button type="button" class="pi2000-button" data-copy>Copy Secret</button><button type="button" class="pi2000-button" data-generate>Generate Password</button><button type="button" class="pi2000-button" data-export>Export This Entry</button></div><label>Notes<textarea name="notes" rows="3" maxlength="32768" spellcheck="false"></textarea></label>`,'Save and Close',async(f,ctx)=>{
    if(!contentKey||entry?.id!==id)throw Error('Entry locked.');const next=structuredClone(vault),nextIndex=structuredClone(index),now=Date.now(),title=f.elements.title.value.trim();if(!title)throw Error('Enter a title.');
    const data={username:f.elements.username.value,url:f.elements.url.value,secret:f.elements.secret.value,notes:f.elements.notes.value};await c.writeEntry(next,contentKey,id,data);ctx.check();const previous=nextIndex.items.find(i=>i.id===id),metadata={id,title,category:f.elements.category.value,created:previous?.created||now,updated:now};if(previous)Object.assign(previous,metadata);else nextIndex.items.push(metadata);await c.writeIndex(next,listKey,nextIndex);ctx.check();await persist(next,ctx);index=nextIndex;selected=id;clearEntry();renderList();message('Entry saved and locked.');
   });
   f.elements.title.value=item.title;f.elements.category.value=item.category;for(const k of ['username','url','secret','notes'])f.elements[k].value=value[k];value=null;
   f.querySelector('[data-reveal]').onclick=()=>{check(epoch);const hidden=!f.elements.secret.hidden;f.elements.secret.hidden=hidden;f.querySelector('[data-mask]').hidden=!hidden;f.querySelector('[data-reveal]').textContent=hidden?'Show Secret':'Hide Secret';touch();};
   f.querySelector('[data-copy]').onclick=()=>run(async ctx=>{ctx.check();await navigator.clipboard.writeText(f.elements.secret.value);ctx.check();message('Secret copied. Your system clipboard/history may retain it.');});
   f.querySelector('[data-generate]').onclick=()=>{check(epoch);const raw=crypto.getRandomValues(new Uint8Array(24)),alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_';f.elements.secret.value=Array.from(raw,v=>alphabet[v&63]).join('');touch();};
   f.querySelector('[data-export]').onclick=()=>{check(epoch);if(!confirm('Download this entry as readable text? The file will contain its secret.'))return;check(epoch);download('vault-entry.json',JSON.stringify({title:f.elements.title.value,category:f.elements.category.value,username:f.elements.username.value,url:f.elements.url.value,secret:f.elements.secret.value,notes:f.elements.notes.value},null,2));closeEntry('Entry exported as readable text and locked.');};
   status('One entry unlocked · closes after 30 seconds of inactivity');updateCommands();
  }
  function deleteEntry(){const id=selected;askB('Delete Entry',async(key,ctx)=>{await c.readEntry(vault,key,id);ctx.check();if(!confirm('Permanently delete this encrypted entry? Existing backups retain their copy.')){clearEntry();renderList();return;}ctx.check();const next=structuredClone(vault),nextIndex={items:index.items.filter(i=>i.id!==id)};delete next.entries[id];await c.writeIndex(next,listKey,nextIndex);await persist(next,ctx);index=nextIndex;selected=null;clearEntry();renderList();message('Entry deleted.');});}
  function changePasswords(){if(!vault)return;lock('');form('Change Pi-Vault Passwords',password('a','Current password A')+password('b','Current password B')+newPasswords()+'<p>Old encrypted exports still need their old passwords. A new recovery key will replace the current one.</p>','Change Passwords',async(f,ctx)=>{const [a,b]=pair(f),result=await c.rekey(vault,f.elements.a.value,f.elements.b.value,a,b,ctx.signal);ctx.check();await persist(result.vault,ctx);showRecovery(result.recovery);});}
  function recover(){if(!vault)return;lock('');form('Recover Your Pi-Vault',password('code','Recovery key')+newPasswords()+'<p>Only your recovery key can unlock both levels. Administrators cannot recover it for you.</p>','Recover Pi-Vault',async(f,ctx)=>{const [a,b]=pair(f),result=await c.recover(vault,f.elements.code.value.trim(),a,b,ctx.signal);ctx.check();await persist(result.vault,ctx);showRecovery(result.recovery);});}
  function importVault(){lock('');form('Import Encrypted Pi-Vault','<p>Import replaces your current encrypted Pi-Vault. Keep an encrypted export first.</p><label>Encrypted Pi-Vault file<input name="file" type="file" accept=".json,application/json" required></label>'+password('a','Imported Pi-Vault password A')+password('b','Imported Pi-Vault password B')+'<label><input name="confirm" type="checkbox" required>Replace my current Pi-Vault</label>','Import Pi-Vault',async(f,ctx)=>{const file=f.elements.file.files[0];if(!file||file.size>4*1024*1024)throw Error('Select a Pi-Vault export no larger than 4 MB.');const next=c.validate(JSON.parse(await file.text()));ctx.check();const a=await c.unlock(next,'a',f.elements.a.value,ctx.signal),b=await c.unlock(next,'b',f.elements.b.value,ctx.signal);const data=await c.readIndex(next,a);for(const item of data.items){await c.readEntry(next,b,item.id);ctx.check();}await persist(next,ctx);clearEntry();renderLocked();message('Encrypted Pi-Vault imported. Unlock the list with password A.');});}
  command('New Entry',()=>openEntry());command('Open Entry',()=>openEntry(selected));command('Close Entry',()=>closeEntry());command('Lock Pi-Vault',()=>lock());
  command('Delete Entry',deleteEntry);command('Export Encrypted',()=>askB('Export Encrypted Pi-Vault',async(key,ctx)=>{ctx.check();download('pi2000-vault-encrypted.json',JSON.stringify(vault));clearEntry();renderList();message('Encrypted export downloaded. Keep its passwords or recovery key separately.');}));
  command('Import Encrypted',importVault);command('Change Passwords',changePasswords);command('Recovery',recover);command('Reload Pi-Vault',()=>{lock('');run(load);});
  w.body.addEventListener('input',e=>{if(e.isTrusted)touch();});w.body.addEventListener('keydown',e=>{if(e.isTrusted)touch();if(e.key==='Escape'){e.preventDefault();contentKey||formSensitive?closeEntry():lock();}});w.body.addEventListener('pointerdown',e=>{if(e.isTrusted)touch();});
  const userChanged=()=>{lock('Account changed.');w.close(true);};window.addEventListener('pi2000-user',userChanged);
  const hide=()=>{if(document.hidden)lock('Pi-Vault locked because the page was hidden.');};document.addEventListener('visibilitychange',hide);
  const blur=()=>{if(contentKey)closeEntry('Entry locked when the browser lost focus. Unsaved edits were discarded.');};window.addEventListener('blur',blur);
  const observer=new MutationObserver(()=>{if(w.element.hidden)lock('Pi-Vault locked when minimised.');});observer.observe(w.element,{attributes:true,attributeFilter:['hidden']});
  const timer=setInterval(()=>{
   if(!alive())return;if(entryDeadline&&Date.now()>=entryDeadline)closeEntry('Entry locked after 30 seconds of inactivity. Unsaved edits were discarded.');else if(listKey&&listDeadline&&Date.now()>=listDeadline)lock('Pi-Vault locked after five minutes of inactivity.');
   if(entryDeadline)status((contentKey?'Entry unlocked':'Private operation')+' · locks in '+Math.max(0,Math.ceil((entryDeadline-Date.now())/1000))+'s');
   if(!busy&&!polling&&Date.now()-lastPoll>=5000){polling=true;lastPoll=Date.now();const t=epoch,expectedRevision=revision;request('/status').then(r=>{if(t===epoch&&expectedRevision===revision&&r.revision!==revision){lock('Pi-Vault changed elsewhere. Reload before opening it.');vault=null;run(load);}}).catch(()=>{if(t===epoch)lock('Session could not be verified. Reconnect and reload Pi-Vault.');}).finally(()=>{polling=false;});}
  },250);
  w.beforelogout=()=>{lock();return true;};w.onclose=()=>{abort();clearEntry();listKey=null;index=null;vault=null;clearDOM();closed=true;clearInterval(timer);observer.disconnect();window.removeEventListener('pi2000-user',userChanged);document.removeEventListener('visibilitychange',hide);window.removeEventListener('blur',blur);current=null;};
  w.beforeclose=()=>{lock();return true;};run(load);return w;
 }
 s.actions.vault=open;Pi2000Apps.register({type:'vault-window',singleton:true,restore:open});
})();
