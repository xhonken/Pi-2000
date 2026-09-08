const {rowCommand}=require('./classic_helpers.cjs');
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
(async()=>{
 const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1400,height:950}}),errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.goto('http://127.0.0.1:18765');
  await page.locator('#login-form [name=password]').fill('browser-test-password');
  await page.locator('#login-form [type=submit]').click();await page.locator('#session').waitFor({state:'visible'});
  await page.locator('#desktop').click({button:'right',position:{x:1250,y:30}});
  await page.locator('#desktop-menu [data-action=new-folder]').click();
  await page.locator('#file-name-form [name=name]').fill('Skrivbordsmapp');await page.locator('#file-name-form button').click();
  await page.locator('#file-icons .desktop-icon').filter({hasText:'Skrivbordsmapp'}).waitFor();
  await page.locator('#desktop [data-action=files]').click();
  let win=page.locator('.files-window').first();await win.waitFor();
  const chooser=page.waitForEvent('filechooser');await win.getByRole('button',{name:'Upload…',exact:true}).click();
  await (await chooser).setFiles([{name:'Test med å.txt',mimeType:'text/plain',buffer:Buffer.from('Privat innehåll')},{name:'stor.bin',mimeType:'application/octet-stream',buffer:Buffer.alloc(100000,7)}]);
  await win.getByRole('row').filter({hasText:'Test med å.txt'}).waitFor();
  await win.getByRole('row').filter({hasText:'stor.bin'}).waitFor();
  await win.getByRole('button',{name:'New Folder…',exact:true}).click();
  await page.locator('#file-name-form [name=name]').fill('File');await page.locator('#file-name-form button').click();
  await win.getByRole('row').filter({hasText:'File'}).waitFor();
  await rowCommand(page,win.getByRole('row').filter({hasText:'Test med å.txt'}),'Move…');
  await page.locator('#file-move-form select').selectOption({label:'My Files / File'});await page.locator('#file-move-form button').click();
  await rowCommand(page,win.getByRole('row').filter({hasText:'File'}),'Open');
  const folder=page.locator('.files-window').filter({has:page.locator('.win2k-titlebar strong').filter({hasText:'My Files / File'})});
  const row=folder.getByRole('row').filter({hasText:'Test med å.txt'});await row.waitFor();
  const downloading=page.waitForEvent('download');await rowCommand(page,row,'Download');
  const download=await downloading;assert.equal(download.suggestedFilename(),'Test med å.txt');assert.equal(await fs.readFile(await download.path(),'utf8'),'Privat innehåll');
  await rowCommand(page,row,'Delete');await row.waitFor({state:'detached'});
  await page.locator('#desktop [data-action=trash]').click();const trash=page.locator('.trash-window');
  await trash.getByRole('row').filter({hasText:'Test med å.txt'}).getByRole('button',{name:'Restore',exact:true}).click();
  await folder.getByRole('row').filter({hasText:'Test med å.txt'}).waitFor();
  const dt=await page.evaluateHandle(()=>{const dt=new DataTransfer();dt.items.add(new File(['Skrivbordsfil'],'skrivbord.txt',{type:'text/plain'}));return dt;});
  await page.locator('#desktop').dispatchEvent('drop',{dataTransfer:dt});
  await page.locator('#file-icons .desktop-icon').filter({hasText:'skrivbord.txt'}).waitFor();
  // Dropping on the built-in folder must not bubble to the desktop upload target.
  const fileDrop=await page.evaluateHandle(()=>{const dt=new DataTransfer();dt.items.add(new File(['I My Files'],'mappdrop.txt',{type:'text/plain'}));return dt;});
  await page.locator('#desktop [data-action=files]').dispatchEvent('drop',{dataTransfer:fileDrop});
  await win.getByRole('row').filter({hasText:'mappdrop.txt'}).waitFor();
  const uploaded=await page.evaluate(async()=>{const data=await (await fetch('/api/files')).json();return data.items.find(item=>item.name==='mappdrop.txt');});
  assert.equal(uploaded.parent,'files');
  assert.equal(await page.locator('#file-icons .desktop-icon').filter({hasText:'mappdrop.txt'}).count(),0);
  // Move that actual desktop file into the trash using the drag/drop path.
  const icon=page.locator('#file-icons .desktop-icon').filter({hasText:'skrivbord.txt'});
  const move=await page.evaluateHandle(()=>new DataTransfer());await icon.dispatchEvent('dragstart',{dataTransfer:move});
  await page.locator('#desktop [data-action=trash]').dispatchEvent('drop',{dataTransfer:move});
  await icon.waitFor({state:'detached'});const deleted=trash.getByRole('row').filter({hasText:'skrivbord.txt'});await deleted.waitFor();
  await page.locator('#desktop [data-action=trash]').click();page.once('dialog',dialog=>dialog.accept());await deleted.getByRole('button',{name:'Delete Permanently…'}).click();await deleted.waitFor({state:'detached'});
  await page.waitForTimeout(300);await page.reload();
  await page.locator('.files-window').filter({has:page.locator('.win2k-titlebar strong').filter({hasText:'My Files / File'})}).getByRole('row').filter({hasText:'Test med å.txt'}).waitFor();
  assert.deepEqual(errors,[]);await page.screenshot({path:process.env.WIN2K_UI_SCREENSHOT||'/tmp/win2k-files-ui.png'});
  // Exercise the quota dialog as a promoted administrator, using disposable accounts.
  await page.evaluate(async()=>{
   async function api(path,method,body){const response=await fetch('/api'+path,{method,headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});if(!response.ok)throw new Error(await response.text());return response.json();}
   const admin=await api('/users','POST',{username:'extra-admin',password:'test-admin-password'});
   await api('/users','POST',{username:'quota-user',password:'test-user-password'});
   await api('/users/'+admin.id,'PATCH',{role:'admin'});
   await api('/logout','POST',{});
   await api('/login','POST',{username:'extra-admin',password:'test-admin-password'});
  });
  await page.reload();await page.locator('#session').waitFor({state:'visible'});
  await page.evaluate(()=>window.Win2kShell.actions.users());
  const users=page.locator('.users-window');
  await users.getByRole('row').filter({hasText:'extra-admin'}).waitFor();
  await rowCommand(page,users.getByRole('row').filter({hasText:'quota-user'}),'Storage Quota…');
  await page.locator('#quota-form [name=quota]').fill('150');await page.locator('#quota-form button').click();
  await page.locator('#quota-form').waitFor({state:'hidden'});
  const quota=await page.evaluate(async()=>{const data=await (await fetch('/api/users')).json();return data.users.find(user=>user.username==='quota-user').storage_quota;});
  assert.equal(quota,150*1024**2);assert.deepEqual(errors,[]);
  console.log('PASS: upload, quota display, folders, move, Unicode download, trash/restore/purge, desktop drop, built-in folder drop, desktop-to-trash drag, saved folder window, added admin quota dialog, no JS errors');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exit(1)});
