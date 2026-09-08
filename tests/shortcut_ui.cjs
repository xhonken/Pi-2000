const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1400,height:950}}),errors=[],opened=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/api/browser/start',route=>{opened.push(route.request().postDataJSON());return route.fulfill({json:{url:'/browser-test-frame'}});});
  await page.route('**/browser-test-frame',route=>route.fulfill({body:'Browser test frame',contentType:'text/html'}));
  await page.goto('http://127.0.0.1:18765');
  await page.locator('#login-form [name=password]').fill('browser-test-password');
  await page.locator('#login-form [type=submit]').click();await page.locator('#session').waitFor({state:'visible'});
  await page.evaluate(()=>Win2kShell.actions.add());
  await page.locator('#shortcut-form [name=name]').fill('Elektrokit');
  await page.locator('#shortcut-form [name=url]').fill('https://elektrokit.com');
  await page.locator('#shortcut-form button[type=button] + button').click();
  const icon=page.locator('#custom-icons [data-shortcut-id]');await icon.waitFor();
  await icon.click();await page.locator('.browser-window iframe').waitFor();
  assert.equal(opened[0].url,'https://elektrokit.com/');assert.equal(browser.contexts()[0].pages().length,1);
  await page.locator('.browser-window [data-control=close]').click();
  await icon.click({button:'right'});await page.locator('.file-context').getByRole('button',{name:'Move to Recycle Bin'}).click();
  await icon.waitFor({state:'detached'});
  await page.evaluate(()=>Win2kShell.actions.trash());
  let row=page.locator('.trash-window tr').filter({hasText:'Elektrokit'});await row.getByRole('button',{name:'Restore',exact:true}).click();await icon.waitFor();
  await page.reload();await page.locator('#session').waitFor({state:'visible'});await icon.waitFor();
  await page.locator('.trash-window [data-control=close]').click();
  await icon.dragTo(page.locator('#desktop-icons [data-action=trash]'));
  await icon.waitFor({state:'detached'});
  await page.evaluate(()=>Win2kShell.actions.trash());
  row=page.locator('.trash-window tr').filter({hasText:'Elektrokit'});await row.waitFor();
  await row.getByRole('button',{name:'Restore',exact:true}).click();await icon.waitFor();
  await icon.focus();await page.keyboard.press('Delete');await icon.waitFor({state:'detached'});
  await page.reload();await page.locator('#session').waitFor({state:'visible'});
  assert.equal(await icon.count(),0);assert.deepEqual(errors,[]);
  console.log('PASS: shortcut opens private browser without popup; context delete, real drag to trash, restore, Delete key and persistence work');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
