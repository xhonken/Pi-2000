const {chromium}=require('playwright');const assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true});try{
const origin=process.env.PI_TEST_ORIGIN||'http://127.0.0.1:18765';const page=await browser.newPage({ignoreHTTPSErrors:!!process.env.PI_TEST_ORIGIN,viewport:{width:1280,height:900}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.goto(origin);if(process.env.PI_TEST_USERNAME)await page.locator('#login-form [name=username]').fill(process.env.PI_TEST_USERNAME);await page.locator('#login-form [name=password]').fill(process.env.PI_TEST_PASSWORD||'browser-test-password');await page.locator('#login-form [type=submit]').click();await page.locator('#session').waitFor({state:'visible'});
const port=process.env.WIN2K_TEST_DB_PORT;
await page.evaluate(async port=>{const r=await fetch('/api/databases/connections',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:'phpMyAdmin fixture',host:'127.0.0.1',port:Number(port),username:'root',password:'',database:'',tls:'disabled',ca:'',save_password:true})});if(!r.ok)throw Error(await r.text());Win2kShell.actions.database();},port);
const w=page.locator('.phpmyadmin-window');await w.locator('option').waitFor();await w.getByRole('button',{name:'Connect',exact:true}).click();await w.locator('iframe').waitFor({state:'visible'}).catch(async e=>{console.log(await w.innerText());throw e;});const f=page.frameLocator('.pma-frame');
async function noNotices(){assert(!/(?:E_USER_DEPRECATED|Deprecation Notice|Since twig\/twig)/i.test(await f.locator('body').innerText()),'No rendered dependency notices on full/AJAX pages');}
await f.locator('#topmenucontainer').waitFor({timeout:30000});await noNotices();await page.screenshot({path:'/tmp/pi2000-phpmyadmin.png'});

assert(await f.locator('link[href="./pi2000.css"]').count());
await f.locator('#topmenu a[href*="route=/server/sql"]').click();
await f.locator('#sqlqueryform .CodeMirror').waitFor({timeout:10000}).catch(async e=>{console.log('SQL PAGE',await f.locator('body').innerText());await noNotices();await page.screenshot({path:'/tmp/pi2000-pma-failure.png'});throw e;});
await f.locator('#sqlqueryform .CodeMirror').evaluate(el=>el.CodeMirror.setValue("CREATE DATABASE pma_suite; USE pma_suite; CREATE TABLE notes (id INT AUTO_INCREMENT PRIMARY KEY, note VARCHAR(80), created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP); INSERT INTO notes(note) VALUES ('from phpMyAdmin');"));
await f.locator('#button_submit_query').click();
await f.locator('.alert-success').first().waitFor({timeout:15000}).catch(async e=>{console.log('EXECUTE PAGE',await f.locator('body').innerText());throw e;});
const base=await w.locator('iframe').getAttribute('src');
await w.locator('iframe').evaluate((el,base)=>el.src=base+'index.php?route=/sql&db=pma_suite&table=notes',base);
await f.locator('.table_results').waitFor({timeout:15000}).catch(async e=>{console.log('BROWSE PAGE',await f.locator('body').innerText());throw e;});assert((await f.locator('.table_results').innerText()).includes('from phpMyAdmin'));
await f.locator('#topmenu a[href*="route=/table/change"]').click();
await f.locator('#insertForm').waitFor();

await f.locator('#field_2_3').fill('Direct insert form');
await f.locator('#buttonYes').click();await f.locator('.alert-success').first().waitFor();
async function go(route){await noNotices();await w.locator('iframe').evaluate((el,url)=>el.src=url,base+'index.php?route='+route+'&db=pma_suite&table=notes');}
await go('/sql');await f.locator('.table_results').waitFor();assert((await f.locator('.table_results').innerText()).includes('Direct insert form'));
await noNotices();await page.screenshot({path:'/tmp/pi2000-pma-rows.png'});
await page.setViewportSize({width:600,height:760});await page.evaluate(()=>document.documentElement.style.setProperty('--personal-font-size','18px'));await w.locator('[data-control=max]').click();
assert((await w.locator('iframe').boundingBox()).height>250);
await noNotices();await page.screenshot({path:'/tmp/pi2000-pma-small.png'});
await page.setViewportSize({width:1280,height:900});await page.evaluate(()=>document.documentElement.style.setProperty('--personal-font-size','13px'));

await f.locator('#topmenu a[href*="route=/table/export"]').click();await f.locator('#buttonGo').waitFor();
const download=page.waitForEvent('download');await f.locator('#buttonGo').click();const file=await download;
const dump=require('node:fs').readFileSync(await file.path(),'utf8');assert(dump.includes('Direct insert form'));assert(dump.includes('CREATE TABLE'));
await go('/table/import');await f.locator('#input_import_file').setInputFiles({name:'roundtrip.sql',mimeType:'application/sql',buffer:Buffer.from("INSERT INTO pma_suite.notes(note) VALUES ('Imported SQL file');")});await f.locator('#buttonGo').click();await f.locator('.alert-success').first().waitFor();
await go('/sql');await f.locator('.table_results').waitFor();assert((await f.locator('.table_results').innerText()).includes('Imported SQL file'));
const rejected=await page.evaluate(async base=>{const result={};for(const path of ['config.inc.php','libraries/config.default.php','setup/index.php'])result[path]=(await fetch(base+path)).status;return result;},base);
assert(Object.values(rejected).every(n=>n===404));
const anon=await browser.newContext({ignoreHTTPSErrors:!!process.env.PI_TEST_ORIGIN});assert.equal((await anon.request.get(origin+base)).status(),401);await anon.close();
await w.getByRole('button',{name:'Disconnect',exact:true}).click();await w.locator('iframe').waitFor({state:'hidden'});
assert.equal(await page.evaluate(async base=>(await fetch(base)).status,base),401);
assert.deepEqual(errors,[]);console.log('PASS: phpMyAdmin connection, SQL create/browse, direct insert with auto ID/timestamp, SQL download/upload, protected paths and session revocation');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exit(1)});
