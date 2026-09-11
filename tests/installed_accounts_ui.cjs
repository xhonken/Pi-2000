const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 let input='';for await(const chunk of process.stdin)input+=chunk;
 const cfg=JSON.parse(input);
 const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:900},ignoreHTTPSErrors:true});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(cfg.origin);
  await page.locator('#login-form [name=username]').fill(cfg.username);
  await page.locator('#login-form [name=password]').fill(cfg.password);
  await page.locator('#login-form [type=submit]').click();
  await page.locator('#session').waitFor({state:'visible'});
  await page.locator('#desktop-icons > [data-action=localterminal]').click();
  await page.locator('#ssh-form').waitFor();
  assert.ok((await page.locator('#ssh-form').innerText()).includes(cfg.linux_username+'@127.0.0.1:2222'));
  await page.locator('#ssh-form [name=password]').fill(cfg.password);
  await page.locator('#ssh-form button').filter({hasText:'Connect'}).click();
  await page.locator('.terminal-window .app-status').filter({hasText:cfg.linux_username+'@127.0.0.1:2222'}).waitFor({timeout:30000});
  await page.locator('.terminal-window .xterm-helper-textarea').fill('');
  await page.locator('.terminal-window .xterm-helper-textarea').pressSequentially('id -un');
  await page.locator('.terminal-window .xterm-helper-textarea').press('Enter');
  await page.waitForTimeout(500);
  await page.screenshot({path:'/tmp/pi2000-system-accounts-installed.png'});
  assert.deepEqual(errors,[]);
  console.log('PASS: installed desktop icon, individual Linux identity in dialog and connected Local Terminal UI.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exit(1)});
