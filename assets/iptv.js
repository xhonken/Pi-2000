/* Private IPTV library and player; all media is addressed by login-bound IDs. */
(() => {
 'use strict';
 const d=Win2kDesktop,s=Win2kShell,esc=Win2kDevelopment.esc;let current=null;
 const sample='https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8';
 function open(saved={}){
  s.closeStart();if(current){current.focus();return current;}const owner=d.getUser()?.id;if(!owner)return;
  const w=d.makeWindow('Pi-IPTV','iptv-window');current=w;
  let closed=false,sources=[],items=[],source=String(saved.source||''),kind=saved.kind||'live',parent='',selected=null,playing=null,hls=null,ts=null,session=null,offset=0,total=0,loading=0,playEpoch=0,importing=false,lastSave=0,searchTimer=null,startTimer=null,seekTo=0;
  const controllers=new Set(),alive=()=>!closed&&d.getUser()?.id===owner;
  w.body.innerHTML=`<div class="tool-toolbar iptv-toolbar"></div><div class="iptv-error" role="alert" hidden></div>
   <div class="iptv-source-bar"><label>Playlist<select aria-label="IPTV playlist"></select></label><span class="iptv-library-summary"></span></div>
   <div class="iptv-tabs" role="tablist" aria-label="Media library">${[['live','Live TV'],['movie','Movies'],['series','Series'],['favorites','Favorites'],['recent','Continue Watching'],['all','All Media']].map(([v,n])=>`<button class="win2k-button" role="tab" data-kind="${v}" aria-selected="false">${n}</button>`).join('')}</div>
   <div class="iptv-main"><section class="iptv-library" aria-label="Channel library"><div class="iptv-filters"><input type="search" aria-label="Search IPTV" placeholder="Search channels, films or episodes…" maxlength="200"><label>Group<select aria-label="IPTV group"><option value="">All groups</option></select></label><label>Country<select aria-label="IPTV country"><option value="">All countries</option></select></label></div><div class="iptv-breadcrumb" hidden><button class="win2k-button" type="button">Back to Series</button><span></span></div><div class="iptv-list" tabindex="0" role="listbox" aria-label="Channels and media"></div><div class="iptv-pages"><button class="win2k-button" data-page="previous">Previous</button><span></span><button class="win2k-button" data-page="next">Next</button></div></section>
   <section class="iptv-viewer" aria-label="Media player"><div class="iptv-screen"><video controls playsinline preload="none" aria-label="IPTV video"></video><div class="iptv-empty"><strong>Pi-IPTV</strong><span>Add a playlist, then double-click a channel or film.</span></div></div><div class="iptv-now" aria-live="polite">Nothing playing</div><div class="iptv-playback"><label>Playback<select aria-label="Playback mode"><option value="original">Original quality</option><option value="audio">Compatible audio (AAC)</option><option value="compatible">Compatible video + audio (720p)</option></select></label><label>Picture<select aria-label="Picture fit"><option value="contain">Fit</option><option value="cover">Fill</option><option value="fill">Stretch</option></select></label><label>Quality<select aria-label="Stream quality"><option value="-1">Automatic</option></select></label><label>Audio<select aria-label="Audio track"><option>Default</option></select></label><label>Subtitles<select aria-label="Subtitle track"><option value="-1">Off</option></select></label></div><section class="iptv-guide" aria-label="Programme guide"><div class="iptv-guide-heading"><strong>Programme Guide / TV Archive</strong><button class="win2k-button" type="button">Load Guide</button></div><div class="iptv-programmes">Select a live channel to see its programme guide.</div></section></section></div>`;
  const $=q=>w.body.querySelector(q),video=$('video'),list=$('.iptv-list'),selector=$('[aria-label="IPTV playlist"]'),search=$('[aria-label="Search IPTV"]'),group=$('[aria-label="IPTV group"]'),country=$('[aria-label="IPTV country"]');
  const status=v=>{if(alive())w.status.textContent=v;},message=v=>{if(alive()){$('.iptv-error').textContent=v;$('.iptv-error').hidden=!v;}};
  async function api(path,body,method=body===undefined?'GET':'POST',keepalive=false){
   if(!alive()&&!keepalive)throw Error('This player is closed.');
   const c=new AbortController();controllers.add(c);const timer=setTimeout(()=>c.abort(),260000);
   try{const r=await fetch('/api/iptv'+path,{method,headers:{'Content-Type':'application/json','X-IPTV-Owner':String(owner)},body:body===undefined?undefined:JSON.stringify(body),signal:keepalive?undefined:c.signal,keepalive});const data=await r.json();if(!r.ok)throw Error(data.error||'The IPTV request failed.');return data;}
   catch(e){if(e.name==='AbortError')throw Error('The IPTV request was cancelled or timed out.');throw e;}finally{clearTimeout(timer);controllers.delete(c);}
  }
  const run=fn=>Promise.resolve().then(()=>{if(alive()){message('');return fn();}}).catch(e=>{if(alive()){message(e.message);status(e.message);}});
  function command(label,fn){const b=document.createElement('button');b.className='win2k-button';b.type='button';b.textContent=label;b.onclick=()=>run(fn);$('.iptv-toolbar').append(b);return b;}
  function entryPath(item=selected,src=source){if(!src||!item)throw Error('Select a channel, film or episode first.');return '/sources/'+src+'/entries/'+item.id;}
  function options(select,values,label,old){select.replaceChildren(new Option(label,''));for(const value of values){let name=value;if(select===country&&/^[A-Za-z]{2}$/.test(value)){try{name=new Intl.DisplayNames(['en'],{type:'region'}).of(value.toUpperCase())+' ('+value.toUpperCase()+')';}catch{}}select.add(new Option(name,value));}if(values.includes(old))select.value=old;}
  function select(item){selected=item;for(const row of list.children)row.setAttribute('aria-selected',String(row.dataset.id===item?.id));$('.iptv-programmes').textContent=item?.kind==='live'?(item.archive?'Archive available for '+item.archive+' days. Load Guide to select a programme.':'Load the programme guide for this channel.'):'Choose a live channel for the programme guide.';}
  function render(){
   list.replaceChildren();for(const item of items){const row=document.createElement('button');row.type='button';row.className='iptv-row';row.dataset.id=item.id;row.setAttribute('role','option');row.setAttribute('aria-selected',String(selected?.id===item.id));row.innerHTML='<span class="iptv-row-icon" aria-hidden="true">'+(item.series_folder?'▣':item.favorite?'★':item.kind==='live'?'▸':'▷')+'</span><span><strong>'+esc(item.name)+'</strong><small>'+esc(item.group)+(item.archive?' · TV archive':'')+(item.position>5?' · Resume '+clock(item.position):'')+'</small></span>';row.onclick=()=>select(item);row.ondblclick=()=>run(()=>activate(item));row.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();run(()=>activate(item));}};list.append(row);}
   if(!items.length){const p=document.createElement('p');p.className='iptv-list-empty';p.textContent=source?'No entries match these filters.':'Use Add Playlist to import your private channel library.';list.append(p);}
   $('.iptv-pages span').textContent=total?(offset+1)+'–'+Math.min(offset+items.length,total)+' of '+total:'0 entries';$('[data-page=previous]').disabled=offset===0;$('[data-page=next]').disabled=offset+200>=total;
   for(const b of w.body.querySelectorAll('[data-kind]'))b.setAttribute('aria-selected',String(b.dataset.kind===kind));
   $('.iptv-breadcrumb').hidden=!parent;
  }
  async function catalog(reset=false){
   const epoch=++loading;if(reset)offset=0;
   if(!source){items=[];total=0;selected=null;render();return;}
   const q=new URLSearchParams({kind,parent,offset:String(offset),q:search.value,group:group.value,country:country.value});status('Loading library…');
   const data=await api('/sources/'+source+'/catalog?'+q);if(!alive()||epoch!==loading)return;
   items=data.items;total=data.count;selected=items.find(i=>i.id===selected?.id)||null;
   options(group,data.groups,'All groups',group.value);options(country,data.countries,'All countries',country.value);
   $('.iptv-library-summary').textContent=data.source.count.toLocaleString()+' entries · '+data.source.kind.toUpperCase();render();status(total.toLocaleString()+' matching entries · '+data.source.name);
  }
  async function refreshSources(){const data=await api('/sources');if(!alive())return;sources=data.sources;selector.replaceChildren(new Option('Select a playlist',''));for(const row of sources)selector.add(new Option(row.name,row.id));if(!sources.some(p=>p.id===source))source=sources[0]?.id||'';selector.value=source;await catalog(true);}
  function resetFilters(){parent='';selected=null;group.value='';country.value='';search.value='';offset=0;}
  selector.onchange=()=>run(async()=>{source=selector.value;resetFilters();await catalog(true);});
  search.oninput=()=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>run(()=>catalog(true)),250);};group.onchange=country.onchange=()=>run(()=>catalog(true));
  for(const b of w.body.querySelectorAll('[data-kind]'))b.onclick=()=>run(()=>{kind=b.dataset.kind;resetFilters();return catalog(true);});
  for(const b of w.body.querySelectorAll('[data-page]'))b.onclick=()=>run(()=>{offset=Math.max(0,offset+(b.dataset.page==='next'?200:-200));return catalog();});
  $('.iptv-breadcrumb button').onclick=()=>run(()=>{parent='';return catalog(true);});
  function clock(value){value=Math.floor(value||0);return Math.floor(value/3600)+':'+String(Math.floor(value%3600/60)).padStart(2,'0')+':'+String(value%60).padStart(2,'0');}
  function savePosition(keepalive=false){if(!playing||!alive()&&!keepalive||!Number.isFinite(video.currentTime))return Promise.resolve();lastSave=Date.now();return api(entryPath(playing.item,playing.source),{position:video.currentTime},'PATCH',keepalive).catch(()=>{});}
  function stop(notify=true,closing=false){
   playEpoch++;clearTimeout(startTimer);startTimer=null;savePosition(closing);hls?.destroy();hls=null;ts?.destroy();ts=null;video.pause();video.removeAttribute('src');video.load();playing=null;seekTo=0;
   if(session){api('/play/'+session,undefined,'DELETE',closing||!alive()).catch(()=>{});session=null;}
   $('.iptv-empty').hidden=false;$('.iptv-now').textContent='Nothing playing';if(notify)status('Playback stopped');
  }
  function playbackError(){clearTimeout(startTimer);startTimer=null;message('Playback failed. Try Reconnect, another channel or a compatible playback mode. The provider may be offline, geo-blocked, over its connection limit, DRM-protected or using an unsupported codec.');status('Playback unavailable');}
  function bufferedAhead(){
   for(let i=0;i<video.buffered.length;i++)if(video.currentTime>=video.buffered.start(i)-.1&&video.currentTime<=video.buffered.end(i))return video.buffered.end(i)-Math.max(video.currentTime,video.buffered.start(i));
   return 0;
  }
  function startLive(epoch){
   // Build a cushion before consuming a real-time TS stream. Never keep a stale
   // channel/account alive or restart playback after Stop/Close/manual Play.
   const deadline=performance.now()+12000;
   const ready=()=>{
    startTimer=null;if(!alive()||epoch!==playEpoch||!video.paused)return;
    if(bufferedAhead()>=4||performance.now()>=deadline){video.play().catch(()=>status('Press Play to start audio and video.'));return;}
    status('Buffering live TV · '+bufferedAhead().toFixed(1)+' / 4 s');startTimer=setTimeout(ready,200);
   };ready();
  }
  async function activate(item,start){
   if(item.series_folder){status('Loading seasons and episodes…');await api(entryPath(item)+'/episodes',{});if(!alive())return;parent=item.id;$('.iptv-breadcrumb span').textContent=item.name;await catalog(true);return;}
   select(item);await play(item,start);
  }
  async function play(item,start,src=source){
   stop(false);const epoch=playEpoch;status('Connecting…');message('');
   const data=await api(entryPath(item,src)+'/play',{mode:$('[aria-label="Playback mode"]').value,...(start===undefined?{}:{start})});
   if(!alive()||epoch!==playEpoch){api('/play/'+data.session,undefined,'DELETE',true).catch(()=>{});return;}
   session=data.session;playing={item,source:src,start,live:data.live};seekTo=!data.live&&start===undefined?item.position||0:0;
   $('.iptv-empty').hidden=true;$('.iptv-now').textContent=data.name+(start===undefined?'':' · TV archive');
   const quality=$('[aria-label="Stream quality"]'),audio=$('[aria-label="Audio track"]'),subtitles=$('[aria-label="Subtitle track"]');quality.replaceChildren(new Option('Automatic','-1'));audio.replaceChildren(new Option('Default','0'));subtitles.replaceChildren(new Option('Off','-1'));
   if(data.format==='hls'&&Hls.isSupported()){
    hls=new Hls({enableWorker:true,backBufferLength:30,maxBufferLength:30,maxMaxBufferLength:60,lowLatencyMode:false,liveSyncDurationCount:5,capLevelToPlayerSize:true});const player=hls;
    player.on(Hls.Events.MANIFEST_PARSED,()=>{if(epoch!==playEpoch)return;player.levels.forEach((v,i)=>quality.add(new Option((v.height?v.height+'p':'Stream '+(i+1))+(v.bitrate?' · '+Math.round(v.bitrate/1000)+' kb/s':''),String(i))));video.play().catch(()=>status('Press Play to start audio and video.'));});
    player.on(Hls.Events.AUDIO_TRACKS_UPDATED,(_,e)=>{audio.replaceChildren();e.audioTracks.forEach((t,i)=>audio.add(new Option(t.name||t.lang||'Audio '+(i+1),String(i))));});
    player.on(Hls.Events.SUBTITLE_TRACKS_UPDATED,(_,e)=>{subtitles.replaceChildren(new Option('Off','-1'));e.subtitleTracks.forEach((t,i)=>subtitles.add(new Option(t.name||t.lang||'Subtitles '+(i+1),String(i))));});
    let recovered=false;player.on(Hls.Events.ERROR,(_,e)=>{if(epoch!==playEpoch||!e.fatal)return;if(e.type===Hls.ErrorTypes.MEDIA_ERROR&&!recovered){recovered=true;player.recoverMediaError();}else{player.stopLoad();playbackError();}});
    player.loadSource(data.url);player.attachMedia(video);
   }else if(data.format==='ts'){
    if(!mpegts.isSupported()){stop(false);throw Error('This browser does not support TS playback. Try a browser with Media Source Extensions or an HLS source.');}
    ts=mpegts.createPlayer({type:'mpegts',isLive:data.live,url:new URL(data.url,location.origin).href},{enableWorker:true,enableStashBuffer:true,stashInitialSize:384*1024,lazyLoad:!data.live,liveBufferLatencyChasing:data.live,liveBufferLatencyMaxLatency:20,liveBufferLatencyMinRemain:6,liveBufferLatencyChasingOnPaused:false,autoCleanupSourceBuffer:true,autoCleanupMaxBackwardDuration:30,autoCleanupMinBackwardDuration:15});
    ts.on(mpegts.Events.ERROR,()=>{if(epoch===playEpoch)playbackError();});ts.attachMediaElement(video);ts.load();if(data.live)startLive(epoch);else ts.play().catch(()=>status('Press Play to start audio and video.'));
   }else {video.src=data.url;video.play().catch(()=>status('Press Play to start audio and video.'));}
   status('Buffering · '+(data.live?'Live TV':'On demand'));api(entryPath(item,src),{position:item.position||0},'PATCH').catch(()=>{});
  }
  video.addEventListener('loadedmetadata',()=>{if(seekTo>0&&Number.isFinite(video.duration)&&seekTo<video.duration-5){video.currentTime=seekTo;seekTo=0;}});
  video.addEventListener('playing',()=>{message('');status('Playing · '+video.videoWidth+' × '+video.videoHeight);});video.addEventListener('waiting',()=>{if(playing)status('Buffering…');});video.addEventListener('error',()=>{if(playing)playbackError();});
  video.addEventListener('timeupdate',()=>{if(playing&&!playing.live&&Date.now()-lastSave>10000)savePosition();});video.addEventListener('pause',()=>savePosition());video.addEventListener('ended',()=>savePosition());
  $('[aria-label="Stream quality"]').onchange=e=>{if(hls)hls.loadLevel=Number(e.target.value);};$('[aria-label="Audio track"]').onchange=e=>{if(hls)hls.audioTrack=Number(e.target.value);};$('[aria-label="Subtitle track"]').onchange=e=>{if(hls){hls.subtitleTrack=Number(e.target.value);hls.subtitleDisplay=Number(e.target.value)>=0;}};
  $('[aria-label="Picture fit"]').onchange=e=>video.style.objectFit=e.target.value;
  $('[aria-label="Playback mode"]').onchange=()=>run(()=>{if(playing){const value=playing;return play(value.item,value.start,value.source);}status('Playback mode selected.');});
  async function guide(){
   if(!selected||selected.kind!=='live')throw Error('Select a live channel first.');const item=selected,src=source;status('Loading programme guide…');
   const result=await api(entryPath(item,src)+'/guide',{});if(!alive()||selected?.id!==item.id||source!==src)return;
   const area=$('.iptv-programmes');area.replaceChildren();
   for(const p of result.programmes){const row=document.createElement('div');row.className='iptv-programme';const now=Date.now()/1000;row.innerHTML='<time>'+esc(new Date(p.start*1000).toLocaleString([], {month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}))+'</time><div><strong>'+esc(p.title)+'</strong><small>'+esc(p.description)+'</small></div>';if(p.available){const b=document.createElement('button');b.className='win2k-button';b.textContent='Watch Archive';b.onclick=()=>run(()=>activate(item,p.start));row.append(b);}else if(p.start<=now&&now<p.stop){const label=document.createElement('span');label.textContent='Now';row.append(label);}area.append(row);}
   if(!result.programmes.length)area.textContent='No guide data available. Use File → Programme Guide to import a matching XMLTV guide, or try another channel.';
   status(result.programmes.length+' programmes · Archive availability is supplied by the provider');
  }
  $('.iptv-guide-heading button').onclick=()=>run(guide);
  function form(title,html,submit,fn){
   s.show(title,'<form class="iptv-form">'+html+'<p class="iptv-form-message" role="alert"></p><div class="actions"><button class="win2k-button" type="submit">'+submit+'</button><button class="win2k-button" type="button" data-cancel>Cancel</button></div></form>');
   const f=document.querySelector('#window .iptv-form'),dialog=document.querySelector('#window');f.querySelector('[data-cancel]').onclick=()=>{f.reset();dialog.close();};
   f.onsubmit=async e=>{e.preventDefault();if(!alive())return;const b=f.querySelector('[type=submit]');b.disabled=true;f.querySelector('.iptv-form-message').textContent='Working…';try{await fn(f);if(!alive())return;f.reset();dialog.close();}catch(error){if(alive())f.querySelector('.iptv-form-message').textContent=error.message;}finally{b.disabled=false;}};return f;
  }
  function add(){
   if(importing)throw Error('Wait for the import to finish.');
   const f=form('Add IPTV Playlist','<label>Playlist name<input name="name" maxlength="100" required autocomplete="off"></label><label>Source type<select name="kind"><option value="m3u">M3U / M3U8 URL</option><option value="xtream">Xtream server + login</option><option value="file">M3U file</option></select></label><label data-address>Playlist / server URL<input name="url" type="password" autocomplete="new-password" spellcheck="false" maxlength="8192" placeholder="https://provider.example/get.php?…"></label><div data-login hidden><label>IPTV username<input name="username" autocomplete="off" maxlength="512"></label><label>IPTV password<input name="password" type="password" autocomplete="new-password" maxlength="512"></label></div><label data-upload hidden>M3U file<input name="file" type="file" accept=".m3u,.m3u8,text/plain"></label><label data-xtream><input name="use_xtream" type="checkbox" checked>Use Xtream categories, series and archive when the URL supports it</label><button class="win2k-button" type="button" data-sample>Use Free-TV Sample</button><p>Saved links and credentials are private to your Pi-2000 account and encrypted on the server. HTTP providers send their credentials without transport encryption. Import may take a few minutes for large libraries.</p>','Import Playlist',async f=>{
    const data={name:f.elements.name.value,kind:f.elements.kind.value,url:f.elements.url.value.trim(),username:f.elements.username.value,password:f.elements.password.value,use_xtream:f.elements.use_xtream.checked};
    if(data.kind==='file'){const file=f.elements.file.files[0];if(!file||file.size>6*1024*1024)throw Error('Choose an M3U file up to 6 MB.');data.content=await file.text();}
    importing=true;status('Importing private IPTV catalogue…');try{const result=await api('/sources',data);f.elements.url.value='';f.elements.password.value='';if(!alive())return;source=result.source.id;resetFilters();await refreshSources();message(result.warnings.join(' '));}finally{importing=false;}
   });
   const changed=()=>{const kind=f.elements.kind.value;f.querySelector('[data-address]').hidden=kind==='file';f.querySelector('[data-login]').hidden=kind!=='xtream';f.querySelector('[data-upload]').hidden=kind!=='file';f.querySelector('[data-xtream]').hidden=kind!=='m3u';};f.elements.kind.onchange=changed;
   f.querySelector('[data-sample]').onclick=()=>{f.elements.name.value='Free-TV';f.elements.kind.value='m3u';f.elements.url.value=sample;changed();};
  }
  async function configureGuide(){
   if(!source)throw Error('Add or select a playlist first.');const src=source;const data=await api('/sources/'+src+'/guides');
   form('Programme Guide','<p>Choose a country-specific XMLTV guide. The provider channel IDs must match your playlist. Import replaces this playlist’s current XMLTV guide.</p><label>Guide from playlist<select name="index"><option value="">Choose a guide</option>'+data.guides.map(g=>'<option value="'+g.index+'">'+esc(g.name)+'</option>').join('')+'</select></label><label>Or custom XMLTV / XML.GZ URL<input name="url" type="password" autocomplete="new-password" maxlength="8192"></label><p>'+(data.xtream?'Xtream channel guides load automatically with Load Guide.':'')+'</p>','Import Guide',async f=>{if(!f.elements.url.value&&!f.elements.index.value)throw Error('Select a guide or enter its URL.');const r=await api('/sources/'+src+'/guides',{index:Number(f.elements.index.value),url:f.elements.url.value.trim()});f.elements.url.value='';status('Imported '+r.count+' programme listings');});
  }
  command('Add Playlist',add);command('Refresh Playlist',async()=>{if(!source)throw Error('Select a playlist.');if(importing)throw Error('Wait for the import to finish.');importing=true;try{status('Refreshing catalogue…');const r=await api('/sources/'+source+'/refresh',{});await refreshSources();message(r.warnings.join(' '));}finally{importing=false;}});
  command('Rename Playlist',()=>{if(!source)throw Error('Select a playlist.');const src=source;form('Rename Playlist','<label>Name<input name="name" maxlength="100" required value="'+esc(sources.find(p=>p.id===src)?.name)+'"></label>','Save Name',async f=>{await api('/sources/'+src,{name:f.elements.name.value},'PATCH');await refreshSources();});});
  command('Remove Playlist',async()=>{if(!source)throw Error('Select a playlist.');if(!confirm('Remove this private playlist, its favorites and viewing history?'))return;const src=source;if(playing?.source===src)stop(false);await api('/sources/'+src,undefined,'DELETE');source='';resetFilters();await refreshSources();});
  command('Programme Guide',configureGuide);command('Play',()=>activate(selected||(()=>{throw Error('Select a channel, film or episode.');})()));command('Stop',()=>stop());command('Reconnect',()=>{if(!playing)throw Error('Choose media and press Play.');const value=playing;return play(value.item,value.start,value.source);});
  command('Favorite',async()=>{const item=selected;if(!item)throw Error('Select an entry.');await api(entryPath(item),{favorite:!item.favorite},'PATCH');item.favorite=!item.favorite;render();status(item.favorite?'Added to Favorites':'Removed from Favorites');});
  command('Full Screen',()=>video.requestFullscreen());command('Refresh View',()=>catalog());
  w.captureState=()=>({source,kind,group:group.value,country:country.value,search:search.value});
  const accountChanged=()=>{if(d.getUser()?.id!==owner)w.close(true);};window.addEventListener('win2k-user',accountChanged);
  const leaving=()=>{savePosition(true);if(session)api('/play/'+session,undefined,'DELETE',true).catch(()=>{});};window.addEventListener('pagehide',leaving);
  w.onclose=()=>{stop(false,true);const form=document.querySelector('#window .iptv-form');if(form){form.reset();form.replaceChildren();document.querySelector('#window').close();}closed=true;clearTimeout(searchTimer);for(const c of controllers)c.abort();window.removeEventListener('win2k-user',accountChanged);window.removeEventListener('pagehide',leaving);current=null;};
  // Restore the library, never autoplay paid streams after login/reboot.
  run(async()=>{await refreshSources();if(!alive())return;search.value=String(saved.search||'').slice(0,200);if([...group.options].some(o=>o.value===saved.group))group.value=saved.group;if([...country.options].some(o=>o.value===saved.country))country.value=saved.country;await catalog();});
  return w;
 }
 s.actions.iptv=()=>open();Win2kApps.register({type:'iptv-window',singleton:true,restore:entry=>open(entry?.state)});
})();
