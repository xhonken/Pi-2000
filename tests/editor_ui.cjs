const {chromium}=require('playwright');
const {command}=require('./classic_helpers.cjs');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1400,height:950}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:18765');await page.locator('#login-form [name=password]').fill('browser-test-password');await page.locator('#login-form button[type=submit]').click();await page.locator('#session').waitFor({state:'visible'});
  const icon=page.locator('#desktop [data-action=files]');const before=await icon.boundingBox();
  await page.mouse.move(before.x+40,before.y+20);await page.mouse.down();await page.mouse.move(640,320,{steps:20});await page.mouse.up();
  await page.waitForFunction(async()=>{const data=await (await fetch('/api/desktop')).json();return data?.positions?.['app:files']?.[0]>400;});
  const moved=await icon.boundingBox();assert.ok(moved.x>400);await page.reload();await page.locator('#session').waitFor({state:'visible'});await page.waitForFunction(()=>parseInt(document.querySelector('#desktop [data-action=files]').style.left)>400);assert.equal(Math.round((await icon.boundingBox()).x),Math.round(moved.x));
  await page.locator('#desktop [data-action=editor]').click();const win=page.locator('.editor-window');await win.waitFor();
  await command(page,win,'File','New Local Folder');await page.locator('#editor-save-form [name=name]').fill('Kodprojekt');await page.locator('#editor-save-form button').click();await page.locator('#editor-save-form').waitFor({state:'hidden'});
  await win.locator('.editor-location').filter({hasText:'Kodprojekt'}).waitFor();
  await page.evaluate(()=>ace.edit(document.querySelector('.editor-code')).setValue('function hello() {\n    return "hej";\n}\n',-1));
  await win.getByRole('button',{name:'Save',exact:true}).click();await page.locator('#editor-save-form [name=name]').fill('hello.js');await page.locator('#editor-save-form button').click();await page.locator('#editor-save-form').waitFor({state:'hidden'});
  await win.locator('.editor-tree-entry').filter({hasText:'hello.js'}).waitFor();
  await page.waitForFunction(()=>ace.edit(document.querySelector('.editor-code')).session.getMode().$id==='ace/mode/javascript');
  await page.evaluate(()=>ace.edit(document.querySelector('.editor-code')).setValue('const answer = 42;\n',-1));await win.locator('.ace_text-input').focus();await page.keyboard.press('Control+s');
  await page.waitForFunction(()=>document.querySelector('.editor-window .app-status').textContent.includes('· Saved'));
  const file=await page.evaluate(async()=>{const data=await (await fetch('/api/files')).json();return data.items.find(x=>x.name==='hello.js');});
  const content=await page.evaluate(async id=>(await (await fetch('/api/files/'+id+'/content')).json()).text,file.id);assert.equal(content,'const answer = 42;\n');
  await win.getByRole('button',{name:'Find/Replace',exact:true}).click();await win.locator('.ace_search').waitFor({state:'visible'});await page.keyboard.press('Escape');
  const oldWidth=await win.locator('.editor-code').evaluate(el=>el.clientWidth);await win.getByRole('button',{name:'Maximise',exact:true}).click();assert.ok(await win.locator('.editor-code').evaluate(el=>el.clientWidth)>oldWidth);
  const download=page.waitForEvent('download');await command(page,win,'File','Download');assert.equal((await download).suggestedFilename(),'hello.js');
  await page.waitForTimeout(300);await page.reload();await page.locator('.editor-window .editor-tabs').getByRole('button',{name:'hello.js',exact:true}).waitFor();
  assert.equal(await page.evaluate(()=>ace.edit(document.querySelector('.editor-code')).getValue()),'const answer = 42;\n');
  // A second writer must not be silently overwritten by an older editor tab.
  await page.evaluate(async id=>{const data=await (await fetch('/api/files/'+id+'/content')).json();await fetch('/api/files/'+id+'/content',{method:'PUT',headers:{'If-Match':data.version},body:'external'});},file.id);
  await page.evaluate(()=>ace.edit(document.querySelector('.editor-code')).setValue('local changes',-1));await page.locator('.editor-window').getByRole('button',{name:'Save',exact:true}).click();await page.locator('#notice').filter({hasText:'The file changed'}).waitFor();
  assert.deepEqual(errors,[]);await page.screenshot({path:'/tmp/win2k-editor-ui.png'});console.log('PASS: real icon drag and persistence, project folder, create/save/edit, syntax mode, Ctrl+S, search, resize, export, restored file tabs, conflict protection, no JS errors');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
