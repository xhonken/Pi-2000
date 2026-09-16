const {chromium}=require('playwright');const assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch({executablePath:process.env.WIN2K_TEST_CHROMIUM||'/usr/bin/chromium',headless:true});
 try{const page=await browser.newPage({viewport:{width:1280,height:950}}),errors=[];page.on('pageerror',e=>errors.push(e.message));page.setDefaultTimeout(25000);
 await page.goto((process.env.WIN2K_TEST_URL||'http://127.0.0.1:18765'));await page.locator('#login-form [name=password]').fill('browser-test-password');await page.locator('#login-form [type=submit]').click();await page.locator('#session').waitFor({state:'visible'});
 await page.locator('#desktop-icons [data-action=arduino]').click();const w=page.locator('.arduino-window');await w.waitFor();
 async function menu(group,label){await w.getByRole('menuitem',{name:group,exact:true}).click();await page.getByRole('menuitem',{name:label,exact:true}).click();}
 let dialog=()=>page.locator('dialog.arduino-dialog');
 await menu('File','New Project');await dialog().locator('[name=projectName]').fill('WorkshopUITest');await dialog().getByRole('button',{name:'Create Project',exact:true}).click();await dialog().waitFor({state:'detached'});
 await menu('File','New File');await dialog().locator('[name=filename]').fill('helpers.h');await dialog().getByRole('button',{name:'Add File',exact:true}).click();await dialog().waitFor({state:'detached'});
 await page.evaluate(()=>ace.edit(document.querySelector('.arduino-editor')).setValue('// private helpers\n',-1));await w.getByRole('button',{name:'Save Project',exact:true}).click();await w.locator('.app-status').filter({hasText:/^Saved/}).waitFor();
 await w.getByRole('tab',{name:'WorkshopUITest.ino',exact:true}).click();
 const real=!!process.env.WIN2K_TEST_ARDUINO_RUNTIME;
 if(real){
  await menu('Tools','Select Board');await dialog().locator('.board-search').fill('ESP32 Dev Module');await dialog().locator('.board-list').selectOption('esp32:esp32:esp32');await dialog().locator('.board-options select').first().waitFor();await dialog().getByRole('button',{name:'Use Board',exact:true}).click();await dialog().waitFor({state:'detached'});assert.match(await w.locator('.arduino-board').textContent(),/ESP32 Dev Module/);
  await menu('Tools','Boards Manager');await dialog().locator('.core-info').filter({hasText:/installed: 3/}).waitFor();assert.ok(await dialog().locator('.core-version option').count()>2);await dialog().getByRole('button',{name:'Close',exact:true}).click();
  await menu('Tools','Library Manager');await dialog().locator('[name=query]').fill('ArduinoJson');await dialog().getByRole('button',{name:'Search Libraries',exact:true}).click();await dialog().locator('.library-info').filter({hasText:/JSON/}).waitFor();assert.ok(await dialog().locator('.library-version option').count()>2);
  await page.screenshot({path:require('node:path').join(process.env.WIN2K_TEST_ARTIFACTS||'/tmp','pi2000-arduino-library-manager.png')});
  await dialog().getByRole('button',{name:'Install Library',exact:true}).click();await dialog().waitFor({state:'detached'});await w.locator('.arduino-job').filter({hasText:'lib install · succeeded'}).waitFor({timeout:60000});await menu('Tools','Library Manager');
  await dialog().getByRole('button',{name:'Installed Libraries',exact:true}).click();await dialog().locator('.library-list option').filter({hasText:/^ArduinoJson$/}).waitFor();await dialog().locator('.library-list').selectOption('ArduinoJson');await dialog().getByRole('button',{name:'Include Library',exact:true}).click();await dialog().waitFor({state:'detached'});
  assert.match(await page.evaluate(()=>ace.edit(document.querySelector('.arduino-editor')).getValue()),/#include <ArduinoJson.h>/);
  await w.getByRole('button',{name:'Verify',exact:true}).click();await w.locator('.arduino-job').filter({hasText:'compile · succeeded'}).waitFor({timeout:180000});assert.match(await w.locator('.arduino-output').textContent(),/Sketch uses/);
 }
 await menu('Tools','Select Port');await dialog().locator('.arduino-dialog-error').filter({hasText:'No USB serial device detected'}).waitFor();await dialog().getByRole('button',{name:'Close',exact:true}).click();
 const downloading=page.waitForEvent('download');await menu('File','Export Project');const exported=await downloading;assert.equal(exported.suggestedFilename(),'WorkshopUITest.arduino.json');
 await w.getByRole('button',{name:'Save Project',exact:true}).click();await w.locator('.app-status').filter({hasText:/^Saved/}).waitFor();
 await page.screenshot({path:require('node:path').join(process.env.WIN2K_TEST_ARTIFACTS||'/tmp','pi2000-arduino-workshop.png')});
 await w.locator('[data-control=close]').click();await page.evaluate(()=>Win2kShell.actions.arduino());await page.locator('.arduino-projects option').filter({hasText:'WorkshopUITest'}).waitFor();await page.locator('.arduino-projects').selectOption({label:'WorkshopUITest'});await page.getByRole('tab',{name:'helpers.h',exact:true}).waitFor();
 await page.setViewportSize({width:650,height:800});await page.evaluate(()=>document.documentElement.style.setProperty('--personal-font-size','18px'));await page.screenshot({path:require('node:path').join(process.env.WIN2K_TEST_ARTIFACTS||'/tmp','pi2000-arduino-narrow.png')});
 const box=await page.locator('.arduino-editor').boundingBox();assert.ok(box.width>100&&box.height>80);assert.deepEqual(errors,[]);
 console.log('PASS Arduino menus, project files/save/reopen/export, no-device message'+(real?', real board/options and library versions/includes, successful ESP32 Verify':''));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
