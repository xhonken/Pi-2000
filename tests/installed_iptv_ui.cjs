/* Explicit installed acceptance. Credentials arrive on stdin and are never logged. */
const {chromium}=require('playwright'),assert=require('node:assert/strict'),path=require('node:path');
let phase='startup';
(async()=>{
 let raw='';for await(const chunk of process.stdin)raw+=chunk;const cfg=JSON.parse(raw);raw='';
 const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--autoplay-policy=no-user-gesture-required']});
 try{
  // The Python operator harness independently verifies system-CA HTTPS trust.
  const context=await browser.newContext({ignoreHTTPSErrors:true,viewport:{width:1280,height:900}}),page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.name));
  phase='PAM login';await page.goto(cfg.origin);await page.locator('#login-form [name=username]').fill(cfg.username);await page.locator('#login-form [name=password]').fill(cfg.password);cfg.password='';await page.locator('#login-form [type=submit]').click();await page.locator('#session').waitFor({state:'visible'});
  await page.evaluate(()=>Win2kShell.actions.iptv());const w=page.locator('.iptv-window'),dialog=page.locator('#window');
  phase='public Free-TV import';await w.getByRole('button',{name:'Add Playlist',exact:true}).click();await dialog.getByRole('button',{name:'Use Free-TV Sample'}).click();await dialog.getByRole('button',{name:'Import Playlist'}).click();await dialog.waitFor({state:'hidden',timeout:120000});
  await w.getByLabel('IPTV country',{exact:true}).selectOption('SE');await page.waitForFunction(()=>document.querySelector('.iptv-window .app-status').textContent.includes('matching entries'));
  assert.ok(await w.locator('.iptv-row').count()>0);assert.equal(await w.locator('[aria-label="IPTV playlist"] option:checked').textContent(),'Free-TV');console.log('PASS installed PAM/HTTPS, new desktop app, public Free-TV import and Sweden filter');
  phase='public media test list';await w.getByRole('button',{name:'Add Playlist',exact:true}).click();await dialog.locator('[name=name]').fill('Public Playback Check');await dialog.locator('[name=kind]').selectOption('file');
  const text='#EXTM3U\n#EXTINF:-1 group-title="Test",Public HLS Test\nhttps://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8\n#EXTINF:-1 group-title="Movies",Public MP4 Test\nhttps://media.w3.org/2010/05/sintel/trailer.mp4\n';
  await dialog.locator('[name=file]').setInputFiles({name:'playback-check.m3u',mimeType:'text/plain',buffer:Buffer.from(text)});await dialog.getByRole('button',{name:'Import Playlist'}).click();await dialog.waitFor({state:'hidden'});
  for(const [tab,title] of [['Live TV','Public HLS Test'],['Movies','Public MP4 Test']]){
   phase='public '+tab+' audio/video';await w.getByRole('tab',{name:tab,exact:true}).click();await w.getByRole('option',{name:new RegExp(title)}).dblclick();
   await page.waitForFunction(()=>{const v=document.querySelector('.iptv-window video');return v.videoWidth>0&&v.currentTime>1&&v.readyState>=2;},null,{timeout:60000});
   const result=await w.locator('video').evaluate(v=>({width:v.videoWidth,height:v.videoHeight,decodedAudio:v.webkitAudioDecodedByteCount>0||v.captureStream().getAudioTracks().length>0}));assert.ok(result.decodedAudio);
   console.log('PASS installed public media:',tab,JSON.stringify(result));await w.getByRole('button',{name:'Stop',exact:true}).click();
  }
  phase='saved catalog and UI';await w.getByRole('tab',{name:'All Media',exact:true}).click();await page.screenshot({path:path.join(cfg.artifacts,'iptv-installed.png')});assert.deepEqual(errors,[]);await w.locator('[data-control=close]').click();
 }finally{await browser.close();}
})().catch(e=>{console.error('Installed IPTV acceptance failed during '+phase+' ('+e.name+').');process.exit(1);});
