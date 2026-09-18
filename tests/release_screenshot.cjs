/* Public screenshot from disposable state and generated media only. */
const {chromium}=require('playwright'),assert=require('node:assert/strict'),path=require('node:path');
(async()=>{
 const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--autoplay-policy=no-user-gesture-required']});
 try{
  const page=await browser.newPage({viewport:{width:1600,height:1000}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(process.env.WIN2K_TEST_URL);await page.locator('#login-form [name=password]').fill('browser-test-password');await page.locator('#login-form [type=submit]').click();await page.locator('#session').waitFor({state:'visible'});
  await page.evaluate(async()=>{
   const r=await fetch('/api/files/upload?'+new URLSearchParams({parent:'files',name:'Welcome to Alpha 6.txt'}),{method:'POST',body:'Pi-2000 — Alpha 6\n===================\n\nYour private Raspberry Pi desktop.\n\nPi-IPTV\n  Live TV, movies and series\n  Country and group filters\n  Favorites and programme guides\n  Buffered audio and video\n\nPersonal workspace\n  Arrange your desktop icons\n  Restore windows and drafts\n  Keep private entries in Pi-Vault\n\nClassic tools\n  Pi++ and Pi-Arduino\n  SSH, files and MariaDB\n\nThis is a disposable demo.\nTV media is generated locally.\n'});
   const file=await r.json();await Win2kEditor.openFile(file.id);
   const owner=Win2kDesktop.getUser().id;
   const imported=await fetch('/api/iptv/sources',{method:'POST',headers:{'Content-Type':'application/json','X-IPTV-Owner':String(owner)},body:JSON.stringify({name:'Demo Television',kind:'file',content:'#EXTM3U\n#EXTINF:-1 tvg-country="SE" group-title="Sweden",Swedish Test News\nhttps://media.example/master.m3u8\n#EXTINF:-1 tvg-country="SE" group-title="Sweden",Culture — Demo\nhttps://media.example/master.m3u8?channel=culture\n#EXTINF:-1 tvg-country="GB" group-title="United Kingdom",British Test Channel\nhttps://media.example/live.ts\n#EXTINF:-1 tvg-country="FI" group-title="Finland",Nordic Test Channel\nhttps://media.example/master.m3u8?channel=nordic\n#EXTINF:-1 group-title="Movies",Sample Film\nhttps://media.example/film.mp4\n'})});
   if(!imported.ok)throw Error('Demo import failed');Win2kShell.actions.iptv();
  });
  const w=page.locator('.iptv-window');await w.getByRole('option',{name:/Swedish Test News/}).dblclick();
  await page.waitForFunction(()=>{const v=document.querySelector('.iptv-window video');return v.videoWidth===320&&v.currentTime>1;});
  await w.locator('video').evaluate(v=>v.pause());
  await page.evaluate(()=>{
   const editor=document.querySelector('.editor-window');Object.assign(editor.style,{left:'125px',top:'55px',width:'510px',height:'830px'});
   const player=document.querySelector('.iptv-window');Object.assign(player.style,{left:'650px',top:'100px',width:'930px',height:'750px'});
   window.dispatchEvent(new Event('resize'));
  });
  const editor=page.locator('.editor-window');await editor.getByRole('menuitem',{name:'View',exact:true}).click();await page.getByRole('menuitemcheckbox',{name:'Document Panel',exact:true}).click();
  await w.getByRole('option',{name:/Swedish Test News/}).click();
  await page.mouse.move(1590,960);await page.waitForTimeout(500);
  assert.deepEqual(errors,[]);
  await page.screenshot({path:path.join(process.env.WIN2K_TEST_ARTIFACTS,'desktop.png')});
  console.log('PASS public desktop screenshot: isolated Pi++ document and generated HLS media');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
