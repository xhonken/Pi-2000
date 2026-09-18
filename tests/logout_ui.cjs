/* Exercise the real Start menu, including a stale workspace in a second tab. */
const {chromium}=require('playwright'),assert=require('node:assert/strict');
(async()=>{
 let cfg={origin:process.env.WIN2K_TEST_URL,username:'admin',password:'browser-test-password'};
 if(process.argv.includes('--installed')){let raw='';for await(const chunk of process.stdin)raw+=chunk;cfg=JSON.parse(raw);}
 const browser=await chromium.launch({executablePath:process.env.WIN2K_TEST_CHROMIUM||'/usr/bin/chromium',headless:true});
 try{
  const context=await browser.newContext({ignoreHTTPSErrors:process.argv.includes('--installed')}),page=await context.newPage(),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  const origin=cfg.origin;
  async function login(){await page.goto(origin);await page.locator('#login-form [name=username]').fill(cfg.username);await page.locator('#login-form [name=password]').fill(cfg.password);await page.locator('#login-form [type=submit]').click();await page.waitForFunction(()=>document.querySelector('#workspace-status').dataset.state==='saved');}
  async function logout(p=page){await p.locator('#start-button').click();await p.locator('#start-menu [data-action=logout]').click();}
  const sessionStatus=p=>p.evaluate(async()=>(await fetch('/api/session')).status);
  async function loggedOut(p=page){await p.locator('#logon').waitFor({state:'visible',timeout:5000});assert.equal(await sessionStatus(p),401);}
  const checkpoint=()=>page.evaluate(()=>Win2kDesktop.api('/workspace'));
  async function confirmLogout(p,accept){let message;const dialog=new Promise(resolve=>p.once('dialog',async d=>{message=d.message();await (accept?d.accept():d.dismiss());resolve();}));await logout(p);await dialog;assert.match(message,/Log off anyway\?/);}
  await login();await logout();await loggedOut();console.log('PASS: Start menu Log Off revokes server authentication');
  await login();await page.evaluate(async()=>{Win2kShell.actions.calculator();await Win2kDesktop.saveWorkspace();});
  const second=await context.newPage();await second.goto(origin);await second.waitForFunction(()=>document.querySelector('#workspace-status').dataset.state==='saved');
  await page.locator('.calculator-form input').fill('first tab wins');await page.evaluate(()=>Win2kDesktop.saveWorkspace());
  await second.locator('.calculator-form input').fill('stale tab');await second.waitForFunction(()=>document.querySelector('#workspace-status').textContent==='Save conflict');
  await confirmLogout(second,false);assert.equal(await second.locator('#session').isVisible(),true);
  assert.equal((await checkpoint()).windows[0].state.expression,'first tab wins');
  await confirmLogout(second,true);await loggedOut(second);await second.close();
  await login();assert.equal((await checkpoint()).windows[0].state.expression,'first tab wins');console.log('PASS: conflicting tab supports cancel/logout without replacing the saved workspace');
  // A failed restoration must permit logout without erasing the checkpoint.
  await page.route('**/api/workspace',r=>r.request().method()==='GET'?r.fulfill({status:503,json:{error:'Recovery fixture outage'}}):r.continue());
  await page.reload();await page.waitForFunction(()=>document.querySelector('#workspace-status').textContent==='Recovery paused');
  await confirmLogout(page,true);await loggedOut();await page.unroute('**/api/workspace');
  await login();assert.equal((await checkpoint()).windows[0].state.expression,'first tab wins');console.log('PASS: failed recovery retains the previous checkpoint on logout');
  // A slow/hung save times out, then offers logout instead of trapping the user.
  await page.route('**/api/workspace',r=>r.request().method()==='PUT'?undefined:r.continue());
  await page.locator('.calculator-form input').fill('unsaved slow request');
  await confirmLogout(page,true);await loggedOut();await page.unroute('**/api/workspace');
  await login();assert.equal((await checkpoint()).windows[0].state.expression,'first tab wins');console.log('PASS: stalled workspace save permits logout after the request timeout');
  // Notes and editor drafts still flush and recover when logout succeeds.
  await page.evaluate(()=>{Win2kShell.actions.notes();Win2kShell.actions.editor();});
  await page.locator('.notes-text:not([disabled])').fill('logout notes');
  await page.waitForFunction(()=>document.querySelector('.editor-code')?.env?.editor);
  await page.evaluate(()=>ace.edit(document.querySelector('.editor-code')).setValue('logout draft',-1));
  await logout();await loggedOut();await login();
  await page.waitForFunction(()=>document.querySelector('.notes-text')?.value==='logout notes'&&document.querySelector('.editor-code')?.env?.editor.getValue()==='logout draft');
  await page.screenshot({path:require('node:path').join(cfg.artifacts||process.env.WIN2K_TEST_ARTIFACTS,'logout-recovered.png')});
  console.log('PASS: editor drafts and notes survive logout and fresh login');
  // A rejected server logout is not presented as success. Repeated clicks use one request.
  let calls=0,release;const held=new Promise(resolve=>release=resolve);
  await page.route('**/api/logout',async r=>{calls++;await held;await r.fulfill({status:503,json:{error:'Logout fixture outage'}});});
  await logout();await page.waitForFunction(()=>document.querySelector('#notice').textContent==='Logging off…');
  await logout();assert.equal(calls,1);release();
  await page.waitForFunction(()=>document.querySelector('#notice').textContent.startsWith('Log off could not finish:'));
  assert.equal(await page.locator('#session').isVisible(),true);assert.equal(await sessionStatus(page),200);
  await page.unroute('**/api/logout');await logout();await loggedOut();
  await page.reload();await page.locator('#logon').waitFor({state:'visible'});
  assert.deepEqual(errors,[]);console.log('PASS: duplicate clicks, failed logout retry, and reload remains signed out');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
