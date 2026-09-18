const {chromium}=require('playwright'),assert=require('node:assert/strict'),path=require('node:path');
const {command}=require('./classic_helpers.cjs');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.WIN2K_TEST_CHROMIUM||'/usr/bin/chromium',headless:true,args:['--autoplay-policy=no-user-gesture-required']});
 try{
  const context=await browser.newContext({viewport:{width:1280,height:900}}),page=await context.newPage(),errors=[],requests=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>requests.push(r.url()));
  await page.goto(process.env.WIN2K_TEST_URL);await page.locator('#login-form [name=password]').fill('browser-test-password');await page.locator('#login-form [type=submit]').click();await page.locator('#session').waitFor({state:'visible'});
  await page.evaluate(()=>Win2kShell.actions.iptv());const w=page.locator('.iptv-window'),dialog=page.locator('#window');
  await w.getByRole('button',{name:'Add Playlist',exact:true}).click();await dialog.locator('[name=name]').fill('Fixture TV');await dialog.locator('[name=url]').fill('https://media.example/playlist.m3u8');await dialog.getByRole('button',{name:'Import Playlist'}).click();await dialog.waitFor({state:'hidden'});assert.equal(await w.locator('[aria-label="IPTV playlist"] option:checked').textContent(),'Fixture TV');
  await w.getByRole('option',{name:/Swedish Test News/}).waitFor();assert.equal(await w.locator('.iptv-row').count(),3);
  await w.getByLabel('IPTV country',{exact:true}).selectOption('SE');await page.waitForFunction(()=>document.querySelectorAll('.iptv-row').length===2);assert.equal(await w.locator('.iptv-row').count(),2);
  await w.getByLabel('Search IPTV',{exact:true}).fill('Swedish');await page.waitForFunction(()=>document.querySelectorAll('.iptv-row').length===1);
  await w.getByRole('option',{name:/Swedish Test News/}).dblclick();
  async function decoded(){try{await page.waitForFunction(()=>{const v=document.querySelector('.iptv-window video');return v.videoWidth===320&&v.currentTime>.5&&v.readyState>=2;},null,{timeout:20000});}catch(e){console.log(await w.locator('video').evaluate(v=>({time:v.currentTime,width:v.videoWidth,ready:v.readyState,error:v.error?.message,src:v.currentSrc,buffered:v.buffered.length})));console.log(await w.locator('.app-status').textContent(),await w.locator('.iptv-error').textContent());throw e;}}
  await decoded();const audio=await w.locator('video').evaluate(v=>({bytes:v.webkitAudioDecodedByteCount||0,tracks:v.captureStream().getAudioTracks().length}));assert.ok(audio.bytes>0||audio.tracks>0,'audio stream was not decoded');
  await w.getByRole('button',{name:'Favorite',exact:true}).click();await w.getByRole('tab',{name:'Favorites',exact:true}).click();await w.getByRole('option',{name:/Swedish Test News/}).waitFor();assert.equal(await w.locator('.iptv-row').count(),1);
  await command(page,w,'File','Programme Guide');await dialog.locator('[name=index]').selectOption('0');await dialog.getByRole('button',{name:'Import Guide'}).click();await dialog.waitFor({state:'hidden'});
  await w.getByRole('option',{name:/Swedish Test News/}).click();await w.getByRole('button',{name:'Load Guide'}).click();await w.getByText('Test Bulletin',{exact:true}).waitFor();
  await page.screenshot({path:path.join(process.env.WIN2K_TEST_ARTIFACTS,'iptv-hls.png')});
  await w.getByRole('tab',{name:'Live TV',exact:true}).click();await w.getByRole('option',{name:/British Test TS/}).dblclick();await decoded();
  await w.getByLabel('Playback mode',{exact:true}).selectOption('audio');await decoded();await w.getByRole('button',{name:'Stop',exact:true}).click();
  await w.getByLabel('Playback mode',{exact:true}).selectOption('original');await w.getByRole('tab',{name:'Movies',exact:true}).click();await w.getByRole('option',{name:/Test Film/}).dblclick();await decoded();await w.locator('video').evaluate(v=>{v.currentTime=2;v.pause();});
  await w.getByRole('button',{name:'Stop',exact:true}).click();await w.getByRole('tab',{name:'Continue Watching',exact:true}).click();await w.getByRole('option',{name:/Test Film/}).waitFor();
  await w.getByRole('button',{name:'Add Playlist',exact:true}).click();await dialog.locator('[name=name]').fill('Xtream Fixture');await dialog.locator('[name=kind]').selectOption('xtream');await dialog.locator('[name=url]').fill('https://media.example');await dialog.locator('[name=username]').fill('fixture-user');await dialog.locator('[name=password]').fill('fixture-secret');await dialog.getByRole('button',{name:'Import Playlist'}).click();await dialog.waitFor({state:'hidden'});
  await w.getByRole('tab',{name:'Series',exact:true}).click();await w.getByRole('option',{name:/Example Series/}).dblclick();await w.getByRole('option',{name:/S01 E01/}).waitFor();assert.equal(await w.locator('.iptv-row').count(),2);await w.getByRole('option',{name:/S01 E01/}).dblclick();await decoded();
  await w.getByRole('button',{name:'Stop',exact:true}).click();await w.getByRole('tab',{name:'Live TV',exact:true}).click();await w.getByRole('option',{name:/Archive TV/}).click();await w.getByRole('button',{name:'Load Guide'}).click();await w.getByRole('button',{name:'Watch Archive'}).click();await decoded();
  await w.getByRole('button',{name:'Stop',exact:true}).click();
  assert.ok(!requests.some(v=>v.includes('fixture-secret')||v.includes('media.example')),'provider credential/URL escaped opaque gateway');
  await page.evaluate(()=>document.documentElement.style.setProperty('--personal-font-size','18px'));await page.setViewportSize({width:650,height:800});
  assert.ok(await w.locator('[data-control=close]').isVisible());assert.ok(await w.getByRole('button',{name:'Add Playlist',exact:true}).isVisible());
  const bounds=await w.locator('.iptv-main').evaluate(e=>({width:e.clientWidth,scroll:e.scrollWidth}));assert.ok(bounds.scroll<=bounds.width+2,JSON.stringify(bounds));
  await page.screenshot({path:path.join(process.env.WIN2K_TEST_ARTIFACTS,'iptv-narrow.png')});
  await page.setViewportSize({width:1280,height:900});await page.evaluate(()=>document.documentElement.style.removeProperty('--personal-font-size'));
  await page.waitForTimeout(2200);await page.reload();await page.locator('#session').waitFor({state:'visible'});await w.waitFor();assert.equal(await w.locator('video').evaluate(v=>v.paused),true);await w.getByRole('option',{name:/Archive TV/}).waitFor();
  await w.locator('[data-control=close]').click();assert.equal(await page.locator('.iptv-window').count(),0);assert.deepEqual(errors,[]);
  console.log('PASS IPTV private import, country/search filters, HLS and TS decoded video/audio, isolated AAC conversion, MP4/history, Xtream episodes/archive, guide, favorites, window recovery, narrow 18px UI and credential-free media URLs');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
