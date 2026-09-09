const {chromium,firefox}=require('playwright');const assert=require('node:assert/strict');
(async()=>{const browser=await(process.env.PI_TEST_BROWSER==='firefox'?firefox.launch({headless:true}):chromium.launch({executablePath:'/usr/bin/chromium',headless:true}));try{
 const page=await browser.newPage({viewport:{width:1400,height:950},ignoreHTTPSErrors:!!process.env.PI_TEST_ORIGIN}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(process.env.PI_TEST_ORIGIN||'http://127.0.0.1:18765');
 if(process.env.PI_TEST_USERNAME)await page.locator('#login-form [name=username]').fill(process.env.PI_TEST_USERNAME);
 await page.locator('#login-form [name=password]').fill(process.env.PI_TEST_PASSWORD||'browser-test-password');await page.locator('#login-form [type=submit]').click();await page.locator('#session').waitFor({state:'visible'});
 await page.evaluate(()=>{
  window.pickerChecks=[];
  const original=HTMLInputElement.prototype.showPicker;
  HTMLInputElement.prototype.showPicker=function(){if(this.type==='file')pickerChecks.push({connected:this.isConnected,active:navigator.userActivation.isActive});return original.call(this);};
 });
 await page.locator('#desktop').click({button:'right',position:{x:1250,y:30}});
 let chooser=page.waitForEvent('filechooser');await page.locator('#desktop-menu [data-action=upload-desktop]').click();await(await chooser).setFiles({name:'picker-desktop.txt',mimeType:'text/plain',buffer:Buffer.from('desktop upload')});
 await page.locator('#file-icons .desktop-icon').filter({hasText:'picker-desktop.txt'}).waitFor();
 await page.evaluate(()=>Win2kFiles.openFolder('files'));let w=page.locator('.files-window').last();
 chooser=page.waitForEvent('filechooser');await w.getByRole('button',{name:'Upload…',exact:true}).click();await(await chooser).setFiles({name:'picker-files.txt',mimeType:'text/plain',buffer:Buffer.from('files upload')});await w.getByRole('row').filter({hasText:'picker-files.txt'}).waitFor();
 await w.getByRole('menuitem',{name:'File',exact:true}).click();chooser=page.waitForEvent('filechooser');await page.getByRole('menuitem',{name:'Upload…',exact:true}).click();await(await chooser).setFiles({name:'picker-menu.txt',mimeType:'text/plain',buffer:Buffer.from('menu upload')});await w.getByRole('row').filter({hasText:'picker-menu.txt'}).waitFor();
 const checks=await page.evaluate(()=>pickerChecks);assert.equal(checks.length,3);assert(checks.every(x=>x.connected&&x.active),JSON.stringify(checks));assert.equal(await page.locator('input[type=file]').count(),0);
 const data=await page.evaluate(async()=>{const items=(await(await fetch('/api/files')).json()).items;const result=[];for(const name of ['picker-desktop.txt','picker-files.txt','picker-menu.txt']){const item=items.find(i=>i.name===name);result.push([item.name,item.parent,await(await fetch('/api/files/'+item.id+'/download')).text()]);}return result;});
 assert.deepEqual(data,[['picker-desktop.txt','desktop','desktop upload'],['picker-files.txt','files','files upload'],['picker-menu.txt','files','menu upload']]);assert.deepEqual(errors,[]);
 console.log('PASS: desktop context/Files toolbar/File menu native chooser activation, connected input cleanup, uploaded destinations and downloaded bytes');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exit(1)});
