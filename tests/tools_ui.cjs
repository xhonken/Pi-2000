const {command}=require('./classic_helpers.cjs');
const {chromium}=require('playwright'),assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true});try{
 const page=await browser.newPage({viewport:{width:1500,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:18765');await page.locator('#login-form [name=password]').fill('browser-test-password');await page.locator('#login-form [type=submit]').click();await page.locator('#session').waitFor({state:'visible'});
 const open=name=>page.evaluate(name=>window.Win2kShell.actions[name](),name);
 const close=type=>page.locator('.'+type+' [data-control=close]').click();
 await open('notes');await page.locator('.notes-text').fill('Privat anteckning åäö');await page.locator('.todo-form [name=task]').fill('Mät ramen');await page.locator('.todo-form button').click();await page.locator('.notes-window .app-status').filter({hasText:'Saved on server'}).waitFor();await close('notes-window');
 await open('notes');await page.waitForFunction(()=>document.querySelector('.notes-text').value==='Privat anteckning åäö');await close('notes-window');
 await open('cad');const cad=page.locator('.cad-window');await cad.locator('.cad-controls:not([inert])').waitFor();await cad.locator('summary').click();await cad.getByRole('button',{name:'Holes Along Frame',exact:true}).click();assert.equal(await cad.locator('tbody tr').count(),10);assert.equal(await cad.locator('.cad-invalid').count(),0);
 await command(page,cad,'File','Save Drawing');await cad.locator('.app-status').filter({hasText:'The drawing has been saved'}).waitFor();
 const dl=page.waitForEvent('download');await command(page,cad,'File','Export SVG');assert.equal((await dl).suggestedFilename(),'dimension-drawing.svg');await page.screenshot({path:'/tmp/win2k-cad-tools.png'});await close('cad-window');
 await open('cad');await page.waitForFunction(()=>document.querySelectorAll('.cad-table tbody tr').length===10);await close('cad-window');
 await open('editor');await page.evaluate(()=>ace.edit(document.querySelector('.editor-code')).setValue('const recover = "utkast";',-1));await page.locator('.editor-window .app-status').filter({hasText:'Recovery draft saved'}).waitFor();
 await page.reload();await page.waitForFunction(()=>document.querySelector('.editor-code')&&ace.edit(document.querySelector('.editor-code')).getValue().includes('utkast'));
 await page.locator('.editor-window').getByRole('button',{name:'Save',exact:true}).click();await page.locator('#editor-save-form [name=name]').fill('utkast.js');await page.locator('#editor-save-form button').click();await page.locator('#editor-save-form').waitFor({state:'hidden'});await close('editor-window');
 await open('search');const search=page.locator('.search-window');await search.locator('input[type=search]').fill('utkast');await search.getByRole('button',{name:'utkast.js',exact:true}).waitFor();await search.getByRole('button',{name:'☆',exact:true}).click();await search.locator('select').selectOption('favorite');await search.getByRole('button',{name:'utkast.js',exact:true}).click();
 await page.locator('.preview-content pre').filter({hasText:'const recover'}).waitFor();await close('preview-window');await close('search-window');
 await open('preferences');await page.locator('.preferences-form [name=fontSize]').selectOption('16');await page.locator('.preferences-form button').click();await page.locator('.preferences-window .app-status').filter({hasText:'Settings saved'}).waitFor();assert.equal(await page.evaluate(()=>getComputedStyle(document.querySelector('.preferences-window .app-body')).fontSize),'16px');await page.locator('.personal-sessions').filter({hasText:'This Session'}).waitFor();await close('preferences-window');
 await open('activities');await page.locator('.activities-list').filter({hasText:'Terminals'}).waitFor();await close('activities-window');
 await open('sftp');await page.locator('.sftp-window .app-status').filter({hasText:'Create an SSH connection'}).waitFor();await close('sftp-window');
 // Upload a minimal PDF, then render it locally with PDF.js under the CSP.
 const pdf='%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]/Resources<<>>/Contents 4 0 R>>endobj\n4 0 obj<</Length 22>>stream\n0 0 100 100 re S\nendstream\nendobj\ntrailer<</Root 1 0 R>>\n%%EOF';
 await page.evaluate(async pdf=>{const r=await fetch('/api/files/upload?name=skiss.pdf',{method:'POST',body:pdf});if(!r.ok)throw Error(await r.text());const id=(await r.json()).id;const data=await(await fetch('/api/files')).json();await window.Win2kTools.openItem(data.items.find(x=>x.id===id));},pdf);
 await page.locator('.preview-window .app-status').filter({hasText:'Page 1 of 1'}).waitFor();assert.ok(await page.locator('.preview-content canvas').evaluate(c=>c.width)>0);await close('preview-window');
 assert.deepEqual(errors,[]);console.log('PASS: notes/todos autosave, CAD geometry/save/export, draft crash recovery/save, search/favorites, text/PDF preview, preferences/session list, activities and SFTP UI');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exit(1)});
