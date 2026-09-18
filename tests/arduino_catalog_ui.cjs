// Opt-in live network regression. Run with tests/run_classic_suite.py against
// its empty disposable runtime, never WIN2K_TEST_ARDUINO_RUNTIME.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 assert.ok(!process.env.WIN2K_TEST_ARDUINO_RUNTIME,'This regression needs an empty runtime');
 const browser=await chromium.launch({executablePath:process.env.WIN2K_TEST_CHROMIUM||'/usr/bin/chromium',headless:true});
 try {
  const page=await browser.newPage({viewport:{width:1280,height:950}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));page.setDefaultTimeout(125000);
  await page.goto((process.env.WIN2K_TEST_URL||'http://127.0.0.1:18765'));
  await page.locator('#login-form [name=password]').fill('browser-test-password');
  await page.locator('#login-form [type=submit]').click();await page.locator('#session').waitFor({state:'visible'});
  await page.locator('#desktop-icons [data-action=arduino]').dblclick();const w=page.locator('.arduino-window');
  async function menu(label){await w.getByRole('menuitem',{name:'Tools',exact:true}).click();await page.getByRole('menuitem',{name:label,exact:true}).click();}
  const d=page.locator('dialog.arduino-dialog');
  await menu('Library Manager');
  for(let i=0;i<2;i++){
   await d.locator('[name=query]').fill('Adafruit GC9A01A');
   const response=page.waitForResponse(r=>r.url().endsWith('/api/development/arduino')&&r.request().postDataJSON()?.action==='library_search');
   await d.getByRole('button',{name:'Search Libraries',exact:true}).click();
   const r=await response;assert.equal(r.status(),200,await r.text());
   await d.locator('.library-list option').filter({hasText:/^Adafruit GC9A01A$/}).waitFor();
   await d.locator('.library-list').selectOption('Adafruit GC9A01A');
   assert.ok(await d.locator('.library-version option').count()>1);
   assert.equal(await d.locator('.arduino-dialog-error').textContent(),'');
  }
  await page.screenshot({path:require('node:path').join(process.env.WIN2K_TEST_ARTIFACTS||'/tmp','pi2000-arduino-catalog-cold.png')});
  await d.getByRole('button',{name:'Install Library',exact:true}).click();
  await d.waitFor({state:'detached'});
  await w.locator('.arduino-job').filter({hasText:'lib install · succeeded'}).waitFor();
  await menu('Library Manager');await d.getByRole('button',{name:'Installed Libraries',exact:true}).click();
  await d.locator('.library-list option').filter({hasText:/^Adafruit GC9A01A$/}).waitFor();
  const installed=await d.locator('.library-list option').allTextContents();
  assert.ok(installed.includes('Adafruit GFX Library'));assert.ok(installed.includes('Adafruit BusIO'));
  await d.getByRole('button',{name:'Close',exact:true}).click();await menu('Boards Manager');
  await d.locator('.core-info').filter({hasText:/ESP32.*installed: none.*available: [0-9]/}).waitFor();
  assert.ok(await d.locator('.core-version option').count()>2);assert.deepEqual(errors,[]);
  console.log('PASS fresh account: automatic catalogs, Adafruit GC9A01A search twice, version selection, real install with GFX/BusIO dependencies, ESP32 platform catalog');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
