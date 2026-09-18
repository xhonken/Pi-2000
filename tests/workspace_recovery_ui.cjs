/* Four isolated accounts, abrupt server death, fresh clients and recovery failures. */
const {chromium}=require('playwright'),assert=require('node:assert/strict');
const fs=require('node:fs/promises'),os=require('node:os'),path=require('node:path'),net=require('node:net');
const {spawn}=require('node:child_process'),{once}=require('node:events');
(async()=>{
 const root=path.resolve(__dirname,'..'),temp=await fs.mkdtemp(path.join(os.tmpdir(),'pi2000-recovery-'));
 const socket=net.createServer();socket.listen(0,'127.0.0.1');await once(socket,'listening');const port=socket.address().port;await new Promise(r=>socket.close(r));
 const origin='http://127.0.0.1:'+port,errors=[];let server,browser;const contexts=[];
 const delay=ms=>new Promise(r=>setTimeout(r,ms));
 async function until(check){for(let n=0;n<150;n++){if(await check())return;await delay(100);}throw Error('Timed out waiting for acknowledged server state');}
 async function start(){const env={...process.env,WIN2K_TEST_STATE:temp,WIN2K_TEST_PORT:String(port),WIN2K_TEST_URL:origin};delete env.WIN2K_TEST_LISTEN_FD;server=spawn(path.join(root,'.venv/bin/python'),['tests/ui_server.py'],{cwd:root,env,stdio:['ignore','ignore','pipe']});server.stderr.on('data',()=>{});for(let i=0;i<100;i++){if(server.exitCode!==null)throw Error('Recovery fixture exited');try{if((await fetch(origin)).ok)return;}catch{}await delay(100);}throw Error('Fixture startup timeout');}
 async function stop(){if(server&&server.exitCode===null){server.kill('SIGKILL');await once(server,'exit');}}
 async function login(i,options={}){const ctx=await browser.newContext({viewport:{width:1280,height:900}});contexts.push(ctx);const p=await ctx.newPage();p.setDefaultTimeout(15000);p.on('pageerror',e=>errors.push(e.message));p.on('dialog',d=>d.dismiss());if(options.terminalsDown)await p.route('**/api/terminals',r=>r.fulfill({status:503,contentType:'application/json',body:'{"error":"temporary outage"}'}));await p.goto(origin);await p.locator('#login-form [name=username]').fill(i?'worker'+i:'admin');await p.locator('#login-form [name=password]').fill(i?'recovery-test-password':'browser-test-password');await p.locator('#login-form [type=submit]').click();await p.locator('#session').waitFor({state:'visible'});await p.waitForFunction(()=>document.querySelector('#workspace-status').dataset.state==='saved');return p;}
 const state=p=>p.evaluate(()=>Win2kDesktop.api('/workspace'));
 try{
  await start();browser=await chromium.launch({executablePath:process.env.WIN2K_TEST_CHROMIUM||'/usr/bin/chromium',headless:true});
  const first=await login(0);for(let i=1;i<4;i++)await first.evaluate(async i=>Win2kDesktop.api('/users','POST',{username:'worker'+i,password:'recovery-test-password'}),i);
  const pages=[first];for(let i=1;i<4;i++)pages.push(await login(i));
  for(let i=0;i<4;i++){
   const p=pages[i];await p.evaluate(i=>{Win2kShell.actions.calculator();document.querySelector('.calculator-form input').value=String(i)+'+42';Win2kShell.actions.editor();ace.edit(document.querySelector('.editor-code')).setValue('unsaved account '+i,-1);Win2kShell.actions.notes();},i);
   await p.locator('.notes-text:not([disabled])').fill('notes account '+i);
   await until(()=>p.evaluate(async()=>{const d=await Win2kDesktop.api('/documents');return d.documents.some(x=>x.key.startsWith('draft-'))&&d.documents.some(x=>x.key==='notes');}));
   await p.evaluate(async i=>{const c=Win2kDesktop.listWindows().find(w=>w.type==='calculator-window');c.element.style.left=(20+i*30)+'px';c.element.style.top='55px';c.element.style.width='420px';c.element.style.height='410px';c.element.querySelector('[data-control=min]').click();if(i===2)Win2kDesktop.listWindows().find(w=>w.type==='editor-window').element.classList.add('maximized');await Win2kDesktop.saveWorkspace();},i);
   await until(()=>p.evaluate(async i=>(await Win2kDesktop.api('/workspace')).windows.find(w=>w.type==='calculator-window')?.state.expression===String(i)+'+42',i));
  }
  // Additional working documents include unsaved source and drawing edits.
  await first.evaluate(async()=>{
   Win2kShell.actions.arduino();const w=Win2kDesktop.listWindows().find(w=>w.type==='arduino-window');await w.ready;
   const r=await fetch('/api/development/arduino',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'create',name:'RecoverySketch'})});if(!r.ok)throw Error(await r.text());const created=await r.json();const project=await Win2kDesktop.api('/development/arduino','POST',{action:'open',project:created.id});await w.restoreState({project});ace.edit(document.querySelector('.arduino-editor')).setValue('// unsaved reboot sketch\n',-1);
   Win2kShell.actions.cad();await Win2kDesktop.listWindows().find(w=>w.type==='cad-window').ready;
   Win2kShell.actions.displaystudio();Win2kShell.actions.vault();
  });
  await first.locator('.cad-window input[name=outerwidth]').fill('444');
  await first.evaluate(()=>{const w=Win2kDesktop.listWindows().find(w=>w.type==='display-window'),s=w.captureState();s.doc.layers.push({type:'text',text:'Recovered drawing',x:5,y:5,w:20,h:20,fontSize:14,lineWidth:1,fill:'#ffffff',stroke:'#ffffff',font:'Arial',filled:true,points:[],image:''});s.dirty=true;return w.restoreState(s);});
  await until(()=>first.evaluate(async()=>{await Win2kDesktop.saveWorkspace();return !!(await Win2kDesktop.api('/workspace')).windows.find(w=>w.type==='arduino-window')?.state.project.files['RecoverySketch.ino']?.includes('unsaved reboot sketch');}));
  // Represent a terminal whose OS process will no longer exist after reboot.
  await first.evaluate(async()=>{const profile=await Win2kDesktop.api('/items','POST',{kind:'profile',name:'Recovery SSH',host:'127.0.0.1',port:22,username:'fixture'});const saved=await Win2kDesktop.api('/workspace');saved.windows.push({type:'terminal-window',profile:profile.id,terminal:'previous-process',left:50,top:80,width:650,height:430,hidden:false,maximized:false});await Win2kDesktop.api('/workspace','PUT',saved);});
  await stop();for(const ctx of contexts.splice(0))await ctx.close();
  await start();const restored=[];
  for(let i=0;i<4;i++){
   const p=await login(i,{terminalsDown:i===0});restored.push(p);
   try{await p.waitForFunction(i=>ace.edit(document.querySelector('.editor-code')).getValue()==='unsaved account '+i,i);}catch(e){console.log('recovery diagnostic',i,await p.evaluate(async()=>({windows:Win2kDesktop.listWindows().map(w=>({type:w.type,status:w.status.textContent})),text:document.querySelector('.editor-code')?ace.edit(document.querySelector('.editor-code')).getValue():null,docs:await Win2kDesktop.api('/documents'),workspace:await Win2kDesktop.api('/workspace')})));throw e;}
   assert.equal(await p.locator('.notes-text').inputValue(),'notes account '+i);if(i===2)assert.equal(await p.locator('.editor-window.maximized').count(),1);
   const calc=p.locator('.calculator-window');assert.equal(await calc.isVisible(),false);
   const saved=await state(p);assert.equal(saved.windows.find(w=>w.type==='calculator-window').state.expression,String(i)+'+42');assert.equal(saved.windows.find(w=>w.type==='calculator-window').left,20+i*30);
   await p.locator('#tasks button').filter({hasText:'Pi-Calt'}).click();assert.equal(await calc.locator('input').inputValue(),String(i)+'+42');
  }
  const p=restored[0];await p.unroute('**/api/terminals');
  assert.match(await p.locator('.terminal-window .app-status').innerText(),/previous terminal process ended/i);assert.equal(await p.locator('.terminal-window button.reconnect').isEnabled(),true);
  assert.equal(await p.locator('.cad-window input[name=outerwidth]').inputValue(),'444');
  assert.equal(await p.evaluate(()=>ace.edit(document.querySelector('.arduino-editor')).getValue()),'// unsaved reboot sketch\n');
  assert.equal(await p.evaluate(()=>Win2kDesktop.listWindows().find(w=>w.type==='display-window').captureState().doc.layers[0].text),'Recovered drawing');
  assert.equal((await state(p)).windows.find(w=>w.type==='vault-window').state,undefined);
  // Failed writes retain visible work and retry after connectivity returns.
  const q=restored[1];await q.route('**/api/workspace',r=>r.request().method()==='PUT'?r.abort():r.continue());
  await q.locator('.calculator-form input').fill('offline recovery');await q.waitForFunction(()=>document.querySelector('#workspace-status').textContent==='Not saved');
  await q.unroute('**/api/workspace');await until(()=>q.evaluate(async()=>(await Win2kDesktop.api('/workspace')).windows.find(w=>w.type==='calculator-window').state.expression==='offline recovery'));
  // A second tab must not silently erase a newer checkpoint.
  const other=await q.context().newPage();await other.goto(origin);await other.waitForFunction(()=>document.querySelector('#workspace-status').dataset.state==='saved');
  await q.locator('.calculator-form input').fill('first tab wins');await until(()=>q.evaluate(async()=>(await Win2kDesktop.api('/workspace')).windows.find(w=>w.type==='calculator-window').state.expression==='first tab wins'));
  await other.locator('.calculator-form input').fill('stale tab');await other.waitForFunction(()=>document.querySelector('#workspace-status').textContent==='Save conflict');assert.equal((await state(q)).windows.find(w=>w.type==='calculator-window').state.expression,'first tab wins');
  // Failure to read a checkpoint cannot replace it with defaults.
  const paused=await restored[2].context().newPage();await paused.route('**/api/workspace',r=>r.request().method()==='GET'?r.abort():r.continue());await paused.goto(origin);await paused.waitForFunction(()=>document.querySelector('#workspace-status').textContent==='Recovery paused');await paused.evaluate(()=>Win2kShell.actions.calculator());await delay(2500);assert.equal((await state(restored[2])).windows.length,3);await paused.close();
  // A broken app must not abort the others or erase its recovery content.
  const broken=await state(restored[2]);broken.windows.unshift({type:'display-window',left:20,top:20,width:600,height:500,hidden:false,maximized:false,state:{doc:{format:'broken'}}});
  await restored[2].evaluate(data=>Win2kDesktop.api('/workspace','PUT',data),broken);
  const recovered=await login(2);assert.equal(await recovered.locator('.editor-window').count(),1);assert.match(await recovered.locator('.display-window .app-status').innerText(),/Recovery could not finish/);await recovered.evaluate(()=>Win2kDesktop.saveWorkspace());assert.equal((await state(recovered)).windows.find(w=>w.type==='display-window').state.doc.format,'broken');
  // Explicit flush includes edits made while the previous save is in flight.
  let release;const held=new Promise(r=>release=r);let intercepted;
  await restored[3].route('**/api/workspace',async route=>{if(route.request().method()==='PUT'&&!intercepted){intercepted=true;await held;}await route.continue();});
  await restored[3].locator('.calculator-form input').fill('before slow save');const initial=restored[3].evaluate(()=>Win2kDesktop.saveWorkspace());await until(()=>intercepted);
  await restored[3].locator('.calculator-form input').fill('after slow save');const final=restored[3].evaluate(()=>Win2kDesktop.saveWorkspace());release();await initial;await final;assert.equal((await state(restored[3])).windows.find(w=>w.type==='calculator-window').state.expression,'after slow save');await restored[3].unroute('**/api/workspace');
  await p.screenshot({path:path.join(process.env.WIN2K_TEST_ARTIFACTS||temp,'workspace-restored.png')});
  assert.deepEqual(errors,[]);console.log('PASS: four accounts survive SIGKILL/server restart and fresh login; drafts, drawings, Arduino, geometry, terminal reconnect, locked Pi-Vault, failed reads/writes and tab conflicts');
 }finally{for(const ctx of contexts)await ctx.close();await browser?.close();await stop();await fs.rm(temp,{recursive:true,force:true});}
})().catch(e=>{console.error(e);process.exit(1)});
