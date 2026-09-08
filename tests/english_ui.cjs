const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:18765');
  assert.equal(await page.locator('html').getAttribute('lang'),'en');
  assert.equal(await page.title(),'Pi-2000Web – Desktop');
  assert.match(await page.locator('.login-wordmark').innerText(),/Pi-2000\s*Web/);
  assert.doesNotMatch(await page.locator('#logon').innerText(),/Microsoft|Professional/);
  await page.screenshot({path:'/tmp/pi2000-english-login.png'});
  await page.locator('#login-form [name=password]').fill('browser-test-password');
  await page.locator('#login-form [type=submit]').click();
  await page.locator('#session').waitFor({state:'visible'});
  const forbidden=/[åäöÅÄÖ]|\b(?:Spara|Arkiv|Redigera|Anslut|Storlek|Rambredd|Lagringsutrymme|Minne|Ditt|Inga|sparad|utkast|sidor|grader|filer|mappar|anslutningar|inloggningar)\b/;
  async function check(root){
   const content=await root.evaluate(el=>[el.innerText,...[...el.querySelectorAll('[aria-label],[title],[placeholder]')].flatMap(x=>['aria-label','title','placeholder'].map(k=>x.getAttribute(k)||''))].join('\n'));
   assert.doesNotMatch(content,forbidden);
  }
  await check(page.locator('#desktop'));
  await page.locator('#start-button').click();
  await page.locator('#start-menu summary').filter({hasText:'Programs'}).first().hover();
  await page.locator('#programs summary').filter({hasText:'System Tools'}).hover();
  await check(page.locator('#start-menu'));
  await page.screenshot({path:'/tmp/pi2000-english-start.png'});
  await page.keyboard.press('Escape');await page.keyboard.press('Escape');await page.keyboard.press('Escape');
  for(const [action,type] of [['files','files'],['trash','trash'],['devices','explorer'],['notes','notes'],['preferences','preferences'],['sftp','sftp'],['calculator','calculator'],['cad','cad'],['editor','editor'],['users','users'],['taskmanager','taskmanager']]){
   await page.evaluate(action=>Win2kShell.actions[action](),action);
   const win=page.locator('.'+type+'-window');await win.locator('.classic-menubar').waitFor();
   if(action==='cad')await win.locator('.cad-controls:not([inert])').waitFor();
   if(action==='taskmanager')await win.locator('.taskmgr-statboxes dl').first().waitFor();
   await check(win);
   if(action==='taskmanager')for(const tab of ['Programs','Processes','Storage']){await win.getByRole('tab',{name:tab,exact:true}).click();await check(win);}
   for(const menu of await win.locator('.classic-menubar > button').all()){
    await menu.evaluate(el=>el.click());await check(page.locator('.classic-popup'));await page.keyboard.press('Escape');
   }
   if(action==='editor'){
    await page.keyboard.press('Alt+f');assert.equal(await page.locator('.classic-popup').getAttribute('aria-label'),'File');await page.keyboard.press('Escape');
    await page.keyboard.press('Alt+e');assert.equal(await page.locator('.classic-popup').getAttribute('aria-label'),'Edit');await page.keyboard.press('Escape');
   }
   await win.locator('[data-control=close]').click();
  }
  for(const action of ['help','settings','add','password','run','shutdown']){
   await page.evaluate(action=>Win2kShell.actions[action](),action);await check(page.locator('#window'));await page.locator('#close-window').click();
  }
  // User-authored Unicode names and content remain untouched by UI language changes.
  const expected={name:'Mina mått åäö.txt',content:'Anteckningar: blå ram, Ø 8 mm.'};
  const id=await page.evaluate(async expected=>{const response=await fetch('/api/files/upload?'+new URLSearchParams({name:expected.name,parent:'desktop'}),{method:'POST',body:expected.content});if(!response.ok)throw Error(await response.text());return (await response.json()).id;},expected);
  await page.reload();await page.locator('#session').waitFor({state:'visible'});
  const result=await page.evaluate(async id=>({files:await Win2kDesktop.api('/files'),text:await Win2kDesktop.api('/files/'+id+'/content')}),id);
  assert.equal(result.files.items.find(f=>f.id===id).name,expected.name);assert.equal(result.text.text,expected.content);
  assert.deepEqual(errors,[]);
  console.log('PASS: English branding, menus, application labels and dialogs, English mnemonics, unchanged Unicode user files across reload');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
