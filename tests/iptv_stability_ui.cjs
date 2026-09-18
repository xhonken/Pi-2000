const {chromium}=require('playwright'),assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.PI2000_TEST_CHROMIUM||'/usr/bin/chromium',headless:true,args:['--autoplay-policy=no-user-gesture-required']});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(process.env.PI2000_TEST_URL);await page.locator('#login-form [name=password]').fill('browser-test-password');await page.locator('#login-form [type=submit]').click();await page.locator('#session').waitFor({state:'visible'});
  await page.evaluate(async()=>{
   const user=Pi2000Desktop.getUser();
   const response=await fetch('/api/iptv/sources',{method:'POST',headers:{'Content-Type':'application/json','X-IPTV-Owner':String(user.id)},body:JSON.stringify({kind:'file',name:'Network jitter fixture',content:'#EXTM3U\n#EXTINF:-1,Jitter TV\nhttps://media.example/jitter.ts\n'})});
   if(!response.ok)throw Error('Fixture import failed');Pi2000Shell.actions.iptv();
  });
  const w=page.locator('.iptv-window');await w.getByRole('option',{name:/Jitter TV/}).waitFor();
  await w.locator('video').evaluate(v=>{
   window.playbackMetrics={started:false,stalls:0,seeks:0,minBuffer:100,samples:0};
   v.addEventListener('playing',()=>window.playbackMetrics.started=true);
   v.addEventListener('waiting',()=>{if(window.playbackMetrics.started)window.playbackMetrics.stalls++;});
   v.addEventListener('seeking',()=>{if(window.playbackMetrics.started)window.playbackMetrics.seeks++;});
   window.sampleTimer=setInterval(()=>{const m=window.playbackMetrics;if(m.started&&v.buffered.length){m.minBuffer=Math.min(m.minBuffer,v.buffered.end(v.buffered.length-1)-v.currentTime);m.samples++;}},100);
  });
  await w.getByRole('option',{name:/Jitter TV/}).dblclick();
  await page.waitForFunction(()=>document.querySelector('.iptv-window video').currentTime>.3,null,{timeout:20000});
  await page.waitForTimeout(17000);
  const metrics=await w.locator('video').evaluate(v=>{clearInterval(window.sampleTimer);return {...window.playbackMetrics,time:v.currentTime,width:v.videoWidth,audio:v.webkitAudioDecodedByteCount||0,error:v.error?.code||0};});
  console.log('Live TS with 2.5 s network outage:',JSON.stringify(metrics));
  assert.equal(metrics.width,320);assert.equal(metrics.error,0);assert.ok(metrics.time>15);assert.ok(metrics.audio>0);assert.deepEqual(errors,[]);
  if(!process.env.PI2000_TEST_BASELINE){assert.equal(metrics.stalls,0,'network outage exhausted the live buffer');assert.equal(metrics.seeks,0,'live latency chasing skipped programme content');}
  await w.getByRole('button',{name:'Stop',exact:true}).click();
  // Stop must cancel delayed startup, so a slow connection cannot restart itself.
  await w.getByRole('option',{name:/Jitter TV/}).dblclick();await page.waitForTimeout(500);await w.getByRole('button',{name:'Stop',exact:true}).click();await page.waitForTimeout(5000);
  const stopped=await w.locator('video').evaluate(v=>({paused:v.paused,src:v.getAttribute('src'),currentSrc:v.currentSrc,time:v.currentTime}));assert.ok(stopped.paused&&!stopped.src,JSON.stringify(stopped));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
