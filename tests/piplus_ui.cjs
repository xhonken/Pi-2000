const {chromium}=require('playwright');const assert=require('node:assert/strict');const {command}=require('./classic_helpers.cjs');
(async()=>{
 let installed=null;if(process.env.PI2000_PIPLUS_INSTALLED_TEST==='1'){let input='';for await(const chunk of process.stdin)input+=chunk;installed=JSON.parse(input);}
 const browser=await chromium.launch({executablePath:process.env.WIN2K_TEST_CHROMIUM||'/usr/bin/chromium',headless:true});
 try{
  const context=await browser.newContext({viewport:{width:1400,height:1000},ignoreHTTPSErrors:!!installed});
  if(installed)await context.addCookies([{name:installed.cookie,value:installed.token,url:installed.origin,secure:true,httpOnly:true,sameSite:'Strict'}]);
  const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(installed?.origin||(process.env.WIN2K_TEST_URL||'http://127.0.0.1:18765'));if(!installed){await page.locator('#login-form [name=password]').fill('browser-test-password');await page.locator('#login-form [type=submit]').click();}await page.locator('#session').waitFor({state:'visible'});
  const files=await page.evaluate(async()=>{
   const out=[];for(const [name,text] of [['display.cpp','#include <Arduino.h>\n#include <Adafruit_GC9A01A.h>\n\n// Pi++ display experiment\nconst int ledPin = 2;\n\nvoid setup() {\n    Serial.begin(115200);\n    pinMode(ledPin, OUTPUT);\n}\n\nvoid loop() {\n    digitalWrite(ledPin, HIGH);\n    Serial.println("Hello from Pi++!");\n    delay(500);\n    digitalWrite(ledPin, LOW);\n    delay(500);\n}\n'],['config.h','#pragma once\n// display configuration\nconst int screenWidth = 240;\n']]){const r=await fetch('/api/files/upload?'+new URLSearchParams({parent:'files',name}),{method:'POST',body:text});out.push({...await r.json(),name});}return out;
  });
  await page.locator('#desktop-icons [data-action=editor]').dblclick();const w=page.locator('.editor-window');await w.waitFor();
  assert.match(await w.locator('header').textContent(),/Pi\+\+/);assert.equal(await page.locator('#desktop-icons [data-action=editor] .icon-label').textContent(),'Pi++');
  await w.getByRole('button',{name:'Open…',exact:true}).click();let form=page.locator('.piplus-form');await form.locator('[name=filter]').fill('display.cpp');await form.getByRole('button',{name:'Open',exact:true}).click();
  await w.getByRole('tab',{name:'display.cpp',exact:true}).waitFor();await page.evaluate(id=>Win2kEditor.openFile(id),files[1].id);await w.getByRole('tab',{name:'config.h',exact:true}).waitFor();
  await w.getByRole('tab',{name:'display.cpp',exact:true}).focus();await page.keyboard.press('ArrowRight');assert.equal(await w.getByRole('tab',{name:'config.h',exact:true}).getAttribute('aria-selected'),'true');
  // Existing file saves are batched, with each target's revision retained.
  await page.evaluate(()=>{for(const t of Win2kEditor.remoteContext().tabs)t.session.insert({row:0,column:0},'// display test\n');});
  await w.getByRole('button',{name:'Save All',exact:true}).click();await w.locator('.app-status').filter({hasText:'All open documents saved.'}).waitFor();
  for(const file of files){const text=await page.evaluate(async id=>(await(await fetch('/api/files/'+id+'/content')).json()).text,file.id);assert.ok(text.startsWith('// display test\n'));}
  await w.getByRole('tab',{name:'display.cpp',exact:true}).click();
  await command(page,w,'Search','Go to Line…');await form.locator('[name=line]').fill('8');await form.getByRole('button',{name:'Go',exact:true}).click();assert.equal(await page.evaluate(()=>ace.edit(document.querySelector('.editor-code')).getCursorPosition().row),7);
  await page.keyboard.press('Control+F2');await page.evaluate(()=>{const c=Win2kEditor.remoteContext();c.active.session.insert({row:0,column:0},'// added above bookmark\n');ace.edit(document.querySelector('.editor-code')).gotoLine(1);});await page.keyboard.press('F2');
  assert.equal(await page.evaluate(()=>ace.edit(document.querySelector('.editor-code')).getCursorPosition().row),8);
  await command(page,w,'Search','Find in Open Documents…');await form.locator('[name=query]').fill('display');await form.getByRole('button',{name:'Find All',exact:true}).click();await w.locator('.editor-search-result').first().waitFor();assert.ok(await w.locator('.editor-search-result').count()>=4);
  await w.locator('.editor-search-result').filter({hasText:'config.h'}).first().click();assert.equal(await w.getByRole('tab',{name:'config.h',exact:true}).getAttribute('aria-selected'),'true');await w.getByRole('button',{name:'Close Search Results',exact:true}).click();
  await command(page,w,'Language','Select Language…');await form.locator('[name=filter]').fill('Python');await form.locator('[name=language]').selectOption('ace/mode/python');await form.getByRole('button',{name:'Use Language',exact:true}).click();await page.waitForFunction(()=>Win2kEditor.remoteContext().active.session.getMode().$id==='ace/mode/python');
  await w.getByRole('menuitem',{name:'Encoding',exact:true}).click();await page.getByRole('menuitemcheckbox',{name:'Convert to Windows (CR LF)',exact:true}).click();await w.getByRole('button',{name:'Save',exact:true}).click();await page.waitForFunction(()=>Win2kEditor.remoteContext().active.saved.includes('\r\n'));
  const crlf=await page.evaluate(async id=>(await(await fetch('/api/files/'+id+'/content')).json()).text,files[1].id);assert.ok(crlf.includes('\r\n'));assert.ok(!crlf.replace(/\r\n/g,'').includes('\n'));
  await command(page,w,'Settings','Preferences…');await form.locator('[name=tabSize]').selectOption('2');await form.locator('[name=fontSize]').selectOption('16');await form.locator('[name=invisibles]').check();await form.getByRole('button',{name:'Save Preferences',exact:true}).click();await form.waitFor({state:'hidden'});
  await w.getByRole('tab',{name:/display.cpp/}).click();await w.getByRole('button',{name:'Save',exact:true}).click();await page.waitForFunction(()=>Win2kEditor.remoteContext().tabs.every(t=>t.saved===t.session.getValue()));
  assert.equal(Math.round((await w.locator('.editor-toolbar .win2k-pixel-icon').first().boundingBox()).width),18);await page.screenshot({path:require('node:path').join(process.env.WIN2K_TEST_ARTIFACTS||'/tmp','pi2000-piplus-desktop.png')});
  await page.reload();await w.getByRole('tab',{name:'display.cpp',exact:true}).waitFor();assert.equal(await page.evaluate(()=>ace.edit(document.querySelector('.editor-code')).getShowInvisibles()),true);assert.equal(await page.evaluate(()=>Win2kEditor.remoteContext().active.session.getTabSize()),2);
  // A cancelled Save As must stop Save All before later unsaved documents.
  await page.evaluate(()=>{const c=Win2kEditor.remoteContext();c.addTab('one.txt','one').saved=null;c.addTab('two.txt','two').saved=null;});await w.getByRole('button',{name:'Save All',exact:true}).click();await page.locator('#editor-save-form').waitFor();assert.equal(await page.locator('#editor-save-form [name=name]').inputValue(),'one.txt');await page.locator('#close-window').click();await page.waitForTimeout(200);assert.equal(await page.locator('#window').evaluate(e=>e.open),false);
  // Import preserves UTF-8 BOM and CR LF; exporting uses the exact text.
  await command(page,w,'File','Import from Computer…');await form.locator('[name=files]').setInputFiles({name:'utf8.txt',mimeType:'text/plain',buffer:Buffer.from('\ufeffRäksmörgås\r\n')});await form.getByRole('button',{name:'Open Files',exact:true}).click();await w.getByRole('tab',{name:'● utf8.txt',exact:true}).waitFor();assert.equal(await page.evaluate(()=>Win2kEditor.remoteContext().active.session.getValue()),'\ufeffRäksmörgås\r\n');
  await page.setViewportSize({width:650,height:850});await page.evaluate(()=>document.documentElement.style.setProperty('--personal-font-size','18px'));await w.getByRole('menuitem',{name:'View',exact:true}).click();await page.getByRole('menuitemcheckbox',{name:'Document Panel',exact:true}).click();assert.equal(await w.locator('.editor-sidebar').isVisible(),false);
  await page.screenshot({path:require('node:path').join(process.env.WIN2K_TEST_ARTIFACTS||'/tmp','pi2000-piplus-narrow.png')});const box=await w.locator('.editor-code').boundingBox();assert.ok(box.width>250&&box.height>150);assert.deepEqual(errors,[]);
  console.log('PASS Pi++ identity, graphical open, accessible tabs, Save All/cancellation, goto/bookmark anchors, search all tabs, language, CR LF persistence, private preferences/reload, UTF-8 BOM import, narrow 18px layout');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
