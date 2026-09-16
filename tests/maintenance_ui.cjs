const {chromium}=require('playwright'),assert=require('node:assert/strict'),path=require('node:path');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.WIN2K_TEST_CHROMIUM||'/usr/bin/chromium',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1100,height:800}}),errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.goto(process.env.WIN2K_TEST_URL||'http://127.0.0.1:18765');
  await page.locator('#login-form [name=password]').fill('browser-test-password');
  await page.locator('#login-form [type=submit]').click();await page.locator('#session').waitFor({state:'visible'});
  await page.route('**/api/version',async route=>route.fulfill({json:{version:'fixture-new',build:'new',revision:'new',modified:false,components:{
   web:{state:'current',loaded:{version:'fixture-new',revision:'new'}},
   sessions:{state:'pending',loaded:{version:'fixture-old',revision:'old'}},
   arduino:{state:'draining',loaded:{version:'fixture-old',revision:'old'}}
  }}}));
  await page.evaluate(()=>Win2kShell.actions.about());
  await page.locator('[data-components]').waitFor();
  assert.match(await page.locator('[data-components]').textContent(),/Update pending.*old/);
  assert.match(await page.locator('[data-components]').textContent(),/Waiting for existing jobs/);
  await page.keyboard.press('Escape');await page.evaluate(()=>Win2kShell.actions.status());
  const status=page.locator('.status-window');await status.locator('h3').filter({hasText:'Installed and running services'}).waitFor();
  assert.match(await status.textContent(),/Update pending/);assert.match(await status.textContent(),/Waiting for jobs/);
  await page.screenshot({path:path.join(process.env.WIN2K_TEST_ARTIFACTS||'/tmp','maintenance-status.png')});
  await page.setViewportSize({width:650,height:800});await page.evaluate(()=>document.documentElement.style.setProperty('--personal-font-size','18px'));
  assert.ok(await status.locator('[data-control=close]').isVisible());assert.deepEqual(errors,[]);
  console.log('PASS About and System Status distinguish installed/current/pending/draining revisions; narrow layout');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exit(1)});
