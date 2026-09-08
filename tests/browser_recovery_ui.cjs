const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true});
 try{
  const page=await browser.newPage();const errors=[];let reason='memory_limit',starts=0;
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/api/browser/start',route=>{starts++;return route.fulfill({json:{url:'/browser-test'}});});
  await page.route('**/browser-test',route=>route.fulfill({body:'Private browser',contentType:'text/html'}));
  await page.route('**/api/browser/status',route=>route.fulfill({json:{state:'stopped',reason,warning:null}}));
  await page.goto('http://127.0.0.1:18765');
  await page.locator('#login-form [name=password]').fill('browser-test-password');
  await page.locator('#login-form [type=submit]').click();await page.locator('#session').waitFor({state:'visible'});
  await page.evaluate(()=>Win2kShell.actions.browser());
  await page.locator('.browser-window iframe').waitFor();
  await page.locator('.browser-content').filter({hasText:'reaching its memory limit'}).waitFor({timeout:15000});
  assert.equal(await page.locator('.browser-window iframe').count(),0);
  reason='crashed';await page.locator('.browser-reconnect').click();await page.locator('.browser-window iframe').waitFor();
  assert.equal(starts,2);
  await page.locator('.browser-content').filter({hasText:'stopped unexpectedly'}).waitFor({timeout:15000});
  assert.deepEqual(errors,[]);
  console.log('PASS: memory stop and crash have distinct messages, stale stream removed, explicit reconnect works');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
