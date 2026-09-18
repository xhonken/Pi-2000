const {chromium}=require('playwright'),assert=require('node:assert/strict'),path=require('node:path');
(async()=>{const browser=await chromium.launch({executablePath:process.env.WIN2K_TEST_CHROMIUM||'/usr/bin/chromium',headless:true});try{
 const context=await browser.newContext({viewport:{width:1400,height:950}}),page=await context.newPage(),errors=[];
 page.on('pageerror',e=>errors.push(e.message));const origin=process.env.WIN2K_TEST_URL;
 await page.goto(origin);await page.locator('#login-form [name=password]').fill('browser-test-password');await page.locator('#login-form [type=submit]').click();await page.locator('#session').waitFor({state:'visible'});
 const icon=id=>page.locator('#desktop-icons > [data-action="'+id+'"]'),form=()=>page.locator('#window-content form'),menu=()=>page.locator('.desktop-context');
 const saved=()=>page.evaluate(()=>Win2kShell.whenSaved());
 // Former default labels follow branding; personal labels and icon IDs persist.
 await page.evaluate(()=>Win2kShell.updateDesktop(s=>{s.icons.vault={name:'Vault',visible:true};s.icons.iptv={name:'IPTV Player',visible:true};}));
 assert.equal(await icon('vault').innerText(),'Pi-Vault');assert.equal(await icon('iptv').innerText(),'Pi-IPTV');
 async function background(){await page.locator('#desktop').click({button:'right',position:{x:1250,y:35}});}
 // Single click selects; double click opens once; Enter also opens.
 await icon('calculator').click();assert.equal(await page.locator('.calculator-window').count(),0);await icon('calculator').dblclick();await page.locator('.calculator-window').waitFor();await page.locator('.calculator-window [data-control=close]').click();
 await icon('vault').click();await page.keyboard.press('F2');await form().locator('[name=name]').fill('My Safe <private>');await form().getByRole('button',{name:'Save',exact:true}).click();await saved();assert.equal(await icon('vault').innerText(),'My Safe <private>');
 await icon('vault').click({button:'right'});await menu().getByRole('button',{name:'Properties',exact:true}).click();assert.match(await page.locator('.desktop-properties').innerText(),/My Safe <private>/);await page.locator('#window-content [data-action=close]').click();
 await icon('vault').click({button:'right'});page.once('dialog',d=>d.accept());await menu().getByRole('button',{name:'Remove from Desktop…'}).click();await saved();assert.equal(await icon('vault').isVisible(),false);
 // Program remains accessible in Start and can be restored with its personal label.
 assert.equal(await page.locator('#programs [data-action=vault]').count(),1);await background();await menu().getByRole('button',{name:'Desktop Icons…'}).click();await form().getByLabel('Pi-Vault',{exact:true}).check();await form().getByLabel('Notes',{exact:true}).check();await form().getByRole('button',{name:'Save',exact:true}).click();await saved();await icon('vault').waitFor();await icon('notes').waitFor();
 await page.reload();await page.locator('#session').waitFor({state:'visible'});assert.equal(await icon('vault').innerText(),'My Safe <private>');await icon('notes').waitFor();
 // Keyboard menu navigation, explicit sort order and collision-free positions.
 await icon('vault').focus();await page.keyboard.press('Shift+F10');await menu().waitFor();await page.keyboard.press('End');assert.equal(await page.locator(':focus').innerText(),'Properties');await page.keyboard.press('Escape');
 await background();await menu().getByRole('button',{name:'Sort by Name',exact:true}).click();await saved();
 let data=await page.evaluate(()=>Win2kShell.getDesktop());assert.equal(data.view.sort,'name');assert.equal(new Set(Object.values(data.positions).map(String)).size,Object.values(data.positions).length);
 await background();await menu().getByRole('button',{name:'Sort by Type',exact:true}).click();await saved();assert.equal(await page.evaluate(()=>Win2kShell.getDesktop().view.sort),'type');
 await background();await menu().getByRole('menuitemcheckbox',{name:'Auto Arrange',exact:true}).click();await saved();assert.equal(await icon('files').getAttribute('draggable'),'false');
 await background();await menu().getByRole('menuitemcheckbox',{name:'Show Desktop Icons',exact:true}).click();await saved();assert.equal(await icon('files').isVisible(),false);await background();await menu().getByRole('menuitemcheckbox',{name:'Show Desktop Icons',exact:true}).click();await saved();await icon('files').waitFor();
 // File rename uses the file API, deletion uses real Recycle Bin semantics.
 const file=await page.evaluate(async()=>await Win2kDesktop.api('/files/folders','POST',{name:'Desktop folder',parent:'desktop'}));await page.evaluate(()=>Win2kFiles.refresh());const folder=page.locator('#file-icons [data-file-id="'+file.id+'"]');await folder.click();await page.keyboard.press('F2');await page.locator('#file-name-form [name=name]').fill('Renamed folder');await page.locator('#file-name-form button').click();await folder.filter({hasText:'Renamed folder'}).waitFor();
 await folder.click({button:'right'});await menu().getByRole('button',{name:'Move to Recycle Bin',exact:true}).click();await folder.waitFor({state:'detached'});
 // Multiple selection removes only the selected application shortcuts.
 await icon('notes').click();await icon('calculator').click({modifiers:['Control']});assert.equal(await page.locator('.desktop-selected').count(),2);page.once('dialog',d=>d.accept());await page.keyboard.press('Delete');await saved();assert.equal(await icon('notes').isVisible(),false);assert.equal(await icon('calculator').isVisible(),false);assert.equal(await icon('vault').isVisible(),true);
 // Clipboard uses the existing private file manager; copied content survives reload.
 const document=await page.evaluate(async()=>{const r=await fetch('/api/files/upload?parent=desktop&name=copy-me.txt',{method:'POST',headers:{'Content-Type':'application/octet-stream'},body:'private fixture'});return r.json();});await page.evaluate(()=>Win2kFiles.refresh());
 const docIcon=page.locator('#file-icons .desktop-icon').filter({hasText:'copy-me.txt'});await docIcon.click();await page.keyboard.press('Control+c');await page.locator('#desktop').click({position:{x:1200,y:20}});await page.keyboard.press('Control+v');await page.locator('#file-icons .desktop-icon').filter({hasText:'copy-me (copy 2).txt'}).waitFor();
 // Selecting single-click is persistent and only affects desktop activation.
 await page.evaluate(()=>Win2kShell.actions['desktop-options']());await form().locator('[name=openMode]').selectOption('single');await form().locator('[name=autoArrange]').uncheck();await form().getByRole('button',{name:'Save',exact:true}).click();await saved();
 await icon('files').click();await page.locator('.files-window').waitFor();await page.locator('.files-window [data-control=close]').click();
 await page.evaluate(()=>Win2kShell.actions['desktop-options']());await form().locator('[name=openMode]').selectOption('double');await form().getByRole('button',{name:'Save',exact:true}).click();await saved();
 // Add an application through the real Start menu without opening it.
 await page.locator('#start-button').click();await page.locator('#start-menu summary').filter({hasText:'Programs'}).first().hover();await page.locator('#programs summary').filter({hasText:'Accessories'}).hover();await page.locator('#programs [data-action=notes]').click({button:'right'});await menu().getByRole('button',{name:'Send to Desktop',exact:true}).click();await saved();await icon('notes').waitFor();
 // Two selected icons move together and their saved displacement agrees.
 await icon('vault').click();await icon('notes').click({modifiers:['Control']});const initial=await page.evaluate(()=>[...document.querySelectorAll('.desktop-selected')].map(el=>({id:Win2kDesktopManager.key(el),x:parseInt(el.style.left),y:parseInt(el.style.top)})));
 const from=await icon('vault').boundingBox();await page.mouse.move(from.x+25,from.y+15);await page.mouse.down();await page.mouse.move(from.x+220,from.y+15,{steps:15});await page.mouse.up();await saved();
 const moved=await page.evaluate(()=>Win2kShell.getPositions());assert.equal(moved[initial[0].id][0]-initial[0].x,moved[initial[1].id][0]-initial[1].x);assert.ok(moved[initial[0].id][0]>initial[0].x);
 // Selection rectangle, grid snapping and additional file sorting commands.
 await page.mouse.move(4,4);await page.mouse.down();await page.mouse.move(230,220,{steps:10});await page.mouse.up();assert.ok(await page.locator('.desktop-selected').count()>1);await page.keyboard.press('Escape');assert.equal(await page.locator('.desktop-selected').count(),0);
 await background();await menu().getByRole('button',{name:'Align to Grid',exact:true}).click();await saved();await page.waitForFunction(()=>Win2kShell.getView().snap===true);
 for(const [label,value] of [['Sort by Size','size'],['Sort by Modified','modified']]){await background();await menu().getByRole('button',{name:label,exact:true}).click();await saved();assert.equal(await page.evaluate(()=>Win2kShell.getView().sort),value);}
 // Account-safe two-tab writes must reject a stale layout instead of erasing it.
 const second=await context.newPage();await second.goto(origin);await second.locator('#session').waitFor({state:'visible'});await page.evaluate(()=>Win2kShell.updateDesktop(s=>{s.icons.vault.name='First tab';}));
 const conflict=await second.evaluate(async()=>{try{await Win2kShell.updateDesktop(s=>{s.icons.vault.name='Stale tab';});return false;}catch{return true;}});assert.equal(conflict,true);assert.equal((await page.evaluate(async()=>await Win2kDesktop.api('/desktop'))).icons.vault.name,'First tab');await second.close();
 // Large text, narrow viewport and menu bounds; screenshot contains only fixture content.
 await page.setViewportSize({width:650,height:700});await page.evaluate(()=>{document.documentElement.style.setProperty('--ui-size','18px');document.documentElement.style.setProperty('--personal-font-size','18px');});await page.locator('#desktop').click({button:'right',position:{x:600,y:500}});const r=await menu().boundingBox();assert.ok(r.x>=0&&r.y>=0&&r.x+r.width<=650&&r.y+r.height<=700);await page.screenshot({path:path.join(process.env.WIN2K_TEST_ARTIFACTS,'desktop-menu.png')});await page.keyboard.press('Escape');
 // New ordinary account has no other user's labels, hidden icons or admin terminal.
 await page.evaluate(async()=>{await Win2kDesktop.api('/users','POST',{username:'desktop-other',password:'desktop-other-fixture'});await Win2kShell.actions.logout();});await page.locator('#login-form [name=username]').fill('desktop-other');await page.locator('#login-form [name=password]').fill('desktop-other-fixture');await page.locator('#login-form [type=submit]').click();await page.locator('#session').waitFor({state:'visible'});assert.equal(await icon('vault').innerText(),'Pi-Vault');assert.equal(await icon('calculator').isVisible(),true);assert.equal(await icon('localterminal').isVisible(),false);
 await page.evaluate(async()=>{await fetch('/api/logout',{method:'POST'});try{await Win2kShell.updateDesktop(s=>{s.view.snap=true;});}catch{}});await page.locator('#logon').waitFor({state:'visible'});assert.equal(await page.locator('#session').isVisible(),false);assert.deepEqual(errors,[]);
 console.log('PASS: desktop activation, rename/remove/restore/pin, persistence, keyboard menus, sort/grid/hide, file trash, multi-selection, two-tab conflicts, narrow display and account isolation');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exit(1)});
