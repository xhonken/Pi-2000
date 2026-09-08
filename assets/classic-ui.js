(() => {
'use strict';
const d=window.Win2kDesktop,s=window.Win2kShell;
const actionIcons={taskmanager:'activities',computer:'computer',files:'files',devices:'devices',browser:'browser',editor:'editor',cad:'cad',calculator:'calculator',notes:'notes',search:'search',sftp:'sftp',activities:'activities',status:'status',preferences:'settings',settings:'settings',users:'users',password:'users',trash:'recycle',links:'link',add:'link',help:'help',run:'run',logout:'logout',shutdown:'computer'};
const typeIcons={'taskmanager-window':'activities','explorer-window':'devices','files-window':'files','trash-window':'recycle','terminal-window':'run','users-window':'users','browser-window':'browser','status-window':'status','editor-window':'editor','preview-window':'file','search-window':'search','activities-window':'activities','notes-window':'notes','preferences-window':'settings','sftp-window':'sftp','cad-window':'cad','calculator-window':'calculator'};
const help={
 'taskmanager-window':'Applications lists your open windows and terminal sessions. Processes lists your browser processes; the owner can also view server processes. Performance shows server CPU and memory with 120 seconds of history. Storage shows your quota and the server data volume. Pause updates using View. CPU usage is measured against total server capacity.',
 'editor-window':'Open local files from the tree or select Connection → SFTP for remote files. Ctrl+S saves the active file. SFTP tabs save to the remote device. Drafts are recovered after reloading. Find and Replace is under Edit.',
 'files-window':'Double-click a file or folder to open it. Select checkboxes and use Edit to copy, move or delete multiple items. Drag files from your computer into the window to upload them. Each row has an Actions menu with more commands.',
 'trash-window':'Restore individual items or empty the Recycle Bin using File. Permanent deletion cannot be undone.',
 'cad-window':'Choose an outer shape and enter dimensions in millimetres. Add cutouts with dimensions, centre position and rotation. Select a cutout in the drawing or table to edit it. Save and export using File. Curve checks are approximate; the tolerance is shown in the drawing.',
 'calculator-window':'Type an expression or use the buttons. Enter calculates the result. Functions use degrees. % divides the entire expression by 100. Scientific functions and history are under View.',
 'notes-window':'Notes and tasks are saved automatically for your account. You can also select File → Save Now.',
 'browser-window':'Your browser has its own tabs, cookies and logins. Closing the window preserves the session. Connection → End Session stops the browser.',
 'explorer-window':'Create folders and SSH connections. Select a device for Properties or double-click to connect. Only your own connections are shown.',
 'sftp-window':'Choose a connection, SSH password and folder. Download files to My Files or send saved files to the device. Use Code Editor to edit remote files directly.',
 'activities-window':'View your terminals, browser session, file transfers and open windows here. Terminal jobs continue even when their windows are closed.',
 'preferences-window':'Text size applies throughout the desktop interface. Choose how text files open, change your background or password, and review signed-in sessions.',
 'search-window':'Search your files, folders, applications and connections. Use the star to save favourites. Filter the list to favourites or recent items.',
 'terminal-window':'Work on the connected device. The terminal continues on the server when its window is closed. End the job using exit or My Activities.',
 'status-window':'Shows server status and resource usage.',
 'users-window':'Manage users and storage. Available actions depend on your permissions. Only the owner can change roles.',
 'preview-window':'Preview text, images and PDFs. Download files or open text in Code Editor. Use the toolbar to change PDF pages and zoom.'
};
const configs={
 'taskmanager-window':{keep:null,groups:[['File','f',[]],['View','v',['Refresh Now','CPU per Core']]]},
 'editor-window':{keep:['New Local File','Save','Undo','Find/Replace','SFTP – Open Device…'],groups:[['File','f',['New Local File','New Local Folder','Save','Save As…','Save Copy on Device…','Download']],['Edit','e',['Undo','Redo','Cut','Copy','Paste','Select All','Search','Find/Replace']],['View','v',['My Files','Word Wrap','Theme','Refresh Files']],['Connection','c',['SFTP – Open Device…','Open Device Version','Send to Device…']]]},
 'files-window':{keep:['Up','New Folder…','Upload…','Copy','Paste','Refresh'],groups:[['File','f',['New Folder…','Upload…','Upload Folder…','Download ZIP']],['Edit','e',['Select All','Copy','Cut','Paste','Delete Selected']],['View','v',['My Files','Desktop','Up','Refresh']]]},
 'trash-window':{keep:['Empty Recycle Bin…','Refresh'],groups:[['File','f',['Empty Recycle Bin…']],['View','v',['Refresh']]]},
 'explorer-window':{keep:['Up','New Folder','New Connection','Open'],groups:[['File','f',['New Folder','New Connection','Open']],['Edit','e',['Properties','Delete']],['View','v',['Up']]]},
 'users-window':{keep:['New User…','Refresh'],groups:[['File','f',['New User…']],['Account','a',['Change My Password…']],['View','v',['Refresh']]]},
 'browser-window':{keep:['Reconnect','Full Screen'],groups:[['File','f',[]],['View','v',['Full Screen']],['Connection','c',['Reconnect','End Session…']]]},
 'terminal-window':{keep:null,groups:[['File','f',[]],['Connection','c',['Reconnect']],['View','v',[]]]},
 'cad-window':{keep:null,groups:[['File','f',['Save Drawing','Export SVG','Export Hole Table CSV']],['Object','o',[]],['Cutouts','u',['Add Cutout','Edit Selected Cutout','Remove Selected','Clear Holes','Holes Along Frame','Hole Grid']],['View','v',[]]]},
 'calculator-window':{keep:null,groups:[['Edit','e',['C','⌫','MC']],['View','v',[]]]},
 'notes-window':{keep:['Save Now'],groups:[['File','f',['Save Now']],['View','v',[]]]},
 'preview-window':{keep:['Download','Edit','Previous','Next','−','+'],groups:[['File','f',['Download','Edit']],['View','v',['Previous','Next','−','+']]]},
 'activities-window':{keep:['Refresh'],groups:[['File','f',[]],['View','v',['Refresh']]]},
 'sftp-window':{keep:['New Remote Folder'],groups:[['File','f',['New Remote Folder']],['View','v',[]]]},
 'search-window':{keep:null,groups:[['File','f',[]],['View','v',[]]]},
 'preferences-window':{keep:['Background and Desktop','Change Password'],groups:[['File','f',['Save Settings']],['View','v',['Background and Desktop']],['Account','a',['Change Password']]]}
};
const toolbarSelector='.editor-toolbar,.file-toolbar,.explorer-toolbar,.browser-toolbar,.tool-toolbar,.sftp-toolbar,.terminal-toolbar';
let popup=null,anchor=null,currentWin=null,returnFocus=null;
function icon(name){const el=document.createElement('span');el.className='win2k-pixel-icon win2k-icon-'+name;el.setAttribute('aria-hidden','true');return el;}
function decorate(root){
 for(const el of root.querySelectorAll('[data-action]')){const name=actionIcons[el.dataset.action];if(!name)continue;let image=el.querySelector(':scope > .win2k-pixel-icon');if(!image&&el.closest('#start-menu')){image=icon(name);el.prepend(image);}if(image){const cls='win2k-pixel-icon win2k-icon-'+name;if(image.className!==cls)image.className=cls;}}
}
function closeMenu(focus=false){const previous=anchor;popup?.remove();popup=null;anchor=null;currentWin=null;previous?.setAttribute('aria-expanded','false');if(focus)previous?.focus();}
function showMenu(button,entries,win){closeMenu();anchor=button;currentWin=win;returnFocus=document.activeElement;button.setAttribute('aria-expanded','true');popup=document.createElement('div');popup.className='classic-popup';popup.setAttribute('role','menu');popup.setAttribute('aria-label',button.textContent.trim());
 for(const entry of entries){if(!entry){const sep=document.createElement('div');sep.className='classic-separator';sep.setAttribute('role','separator');popup.append(sep);continue;}const b=document.createElement('button');b.type='button';b.setAttribute('role',entry.checked===undefined?'menuitem':'menuitemcheckbox');if(entry.checked!==undefined)b.setAttribute('aria-checked',String(entry.checked));b.className='classic-menuitem';b.setAttribute('aria-label',entry.label);b.disabled=entry.disabled===true;const check=document.createElement('span');check.className='menu-check';check.textContent=entry.checked?'✓':'';b.append(check);const label=document.createElement('span');label.className='command-label';label.textContent=entry.label;b.append(label);if(entry.key){const key=document.createElement('span');key.className='command-key';key.textContent=entry.key;b.append(key);}b.onclick=()=>{closeMenu();if(win.uiLastFocus?.isConnected)win.uiLastFocus.focus({preventScroll:true});Promise.resolve().then(()=>entry.run()).catch(e=>s.notify(e.message));};popup.append(b);}
 document.body.append(popup);const r=button.getBoundingClientRect(),bottom=innerHeight-parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--shell-height'))-4;popup.style.maxHeight=Math.max(80,bottom-4)+'px';const p=popup.getBoundingClientRect();popup.style.left=Math.max(4,Math.min(r.left,innerWidth-p.width-4))+'px';popup.style.top=Math.max(4,Math.min(r.bottom,bottom-p.height))+'px';popup.querySelector('button:not(:disabled)')?.focus();
 popup.onkeydown=e=>{const buttons=[...popup.querySelectorAll('button:not(:disabled)')],i=buttons.indexOf(document.activeElement);if(['ArrowDown','ArrowUp','Home','End'].includes(e.key)){e.preventDefault();buttons[e.key==='Home'?0:e.key==='End'?buttons.length-1:(i+(e.key==='ArrowDown'?1:-1)+buttons.length)%buttons.length]?.focus();}else if(e.key==='Escape'){e.preventDefault();e.stopPropagation();closeMenu(true);}else if(['ArrowLeft','ArrowRight'].includes(e.key)&&anchor?.closest('.classic-menubar')){e.preventDefault();const siblings=[...anchor.parentElement.children],index=siblings.indexOf(anchor),next=siblings[(index+(e.key==='ArrowRight'?1:-1)+siblings.length)%siblings.length];next.click();}else if(e.key==='Tab')closeMenu();};
}
const shortcuts={'Save':'Ctrl+S','Save As…':'Ctrl+Shift+S','Undo':'Ctrl+Z','Redo':'Ctrl+Y','Find/Replace':'Ctrl+H','Search':'Ctrl+F','Cut':'Ctrl+X','Copy':'Ctrl+C','Paste':'Ctrl+V','Select All':'Ctrl+A'};
function original(win,label){return [...win.body.querySelectorAll('button:not(.row-actions-trigger)')].find(b=>(b.dataset.uiLabel||b.textContent.trim())===label);}
function command(win,label){const b=original(win,label);return {label,key:win.type==='editor-window'?shortcuts[label]:undefined,disabled:!b||b.disabled||!!b.closest('[inert]')||(win.type==='files-window'&&['Copy','Cut','Delete Selected','Download ZIP'].includes(label)&&!win.selected?.size),run:()=>{if(b&&!b.disabled&&!b.closest('[inert]'))b.click();}};}
function entries(win,name,labels){const rows=labels.map(label=>command(win,label));
 if(name==='File')rows.push(null,{label:'Close',run:()=>win.close()});
 if(name==='View'){
  if(win.type==='taskmanager-window')rows.unshift(command(win,original(win,'Resume Updates')?'Resume Updates':'Pause Updates'));
  if(win.type==='calculator-window'){rows.unshift({label:'Scientific Functions',checked:win.body.classList.contains('calculator-advanced'),run:()=>win.body.classList.toggle('calculator-advanced')},{label:'History',checked:!!win.body.querySelector('details')?.open,run:()=>{const el=win.body.querySelector('details');if(el)el.open=!el.open;}});}
  if(win.type==='cad-window')rows.unshift({label:'Show Dimensions and Cutouts',run:()=>win.body.querySelector('.cad-summary')?.scrollIntoView({block:'nearest'})});
  if(win.type==='search-window')for(const [value,label] of [['all','All Items'],['favorite','Favourites'],['recent','Recent Items']])rows.push({label,checked:win.body.querySelector('.search-filter')?.value===value,run:()=>{const select=win.body.querySelector('.search-filter');select.value=value;select.dispatchEvent(new Event('change'));}});
  if(win.body.querySelector(toolbarSelector))rows.push(null,{label:'Toolbar',checked:!win.element.classList.contains('toolbar-hidden'),run:()=>{win.element.classList.toggle('toolbar-hidden');win.onresize?.();}});rows.push({label:'Maximise / Restore Window',run:()=>win.element.querySelector('[data-control=max]').click()});
 }
 if(name==='Object')rows.push({label:'Outer Shape and Dimensions',run:()=>{const field=win.body.querySelector('[name=outertype]');field?.scrollIntoView({block:'nearest'});field?.focus();}});
 if(name==='Edit'&&win.type==='calculator-window')rows.push(null,{label:'Copy Result',run:()=>navigator.clipboard.writeText(win.body.querySelector('output').textContent)});
 return rows;
}
function enhance(win){
 const config=configs[win.type];
 if(config?.keep)for(const b of win.body.querySelectorAll(toolbarSelector.split(',').map(x=>x+' > button').join(','))){if(!b.dataset.uiLabel)b.dataset.uiLabel=b.textContent.trim();const hidden=!config.keep.includes(b.dataset.uiLabel);b.classList.toggle('ui-menu-command',hidden);if(['Save','Save Now'].includes(b.dataset.uiLabel))b.dataset.icon='save';if(b.dataset.uiLabel.includes('SFTP'))b.dataset.icon='sftp';if(b.dataset.uiLabel==='New Folder…'||b.dataset.uiLabel==='New Folder')b.dataset.icon='folder';if(b.dataset.uiLabel==='Find/Replace')b.dataset.icon='search';}
 // Compact row commands without removing their handlers or changing selection.
 if(['files-window','users-window'].includes(win.type))for(const cell of win.body.querySelectorAll('tbody tr > td:last-child')){if(cell.querySelector('.row-actions-trigger'))continue;const buttons=[...cell.querySelectorAll(':scope > button')];if(buttons.length<3)continue;for(const b of buttons)b.classList.add('ui-menu-command');const trigger=document.createElement('button');trigger.className='win2k-button row-actions-trigger';trigger.textContent='Actions';trigger.setAttribute('aria-label','Actions');trigger.setAttribute('aria-haspopup','menu');trigger.setAttribute('aria-expanded','false');trigger.onclick=e=>{e.stopPropagation();showMenu(trigger,buttons.map(b=>({label:b.textContent,disabled:b.disabled,run:()=>b.click()})),win);};cell.prepend(trigger);}
 if(win.type==='files-window')for(const label of ['Copy','Cut','Delete Selected','Download ZIP']){const b=[...win.body.querySelectorAll('.file-toolbar button')].find(b=>b.textContent===label);if(b)b.disabled=!win.selected?.size;}
 if(win.type==='cad-window')win.body.querySelector('.cad-storage')?.classList.add('ui-menu-command');
 if(win.type==='calculator-window'){
  const panel=win.body.querySelector('.calculator-keys');if(panel&&!panel.dataset.classic){panel.dataset.classic='true';const buttons=[...panel.children];for(const b of buttons){const label=b.textContent;if(['sin(','cos(','tan(','asin(','acos(','atan(','abs(','log(','ln(','^','pi','e','Ans'].includes(label))b.classList.add('calculator-scientific');if(['MC','MR','M+','M−','C','⌫'].includes(label))b.classList.add('calculator-memory');}
   const groups=[['calculator-memory-keys',['MC','MR','M+','M−','C','⌫']],['calculator-number-keys',['7','8','9','/','sqrt(','4','5','6','*','%','1','2','3','-','±','0','.','(',')','+']],['calculator-scientific-keys',['^','pi','e','Ans','abs(','sin(','cos(','tan(','log(','ln(','asin(','acos(','atan(']]];
   for(const [cls,labels] of groups){const group=document.createElement('div');group.className=cls;for(const label of labels){const b=buttons.find(b=>b.textContent===label);if(b)group.append(b);}panel.append(group);}
   win.body.querySelector('details').open=false;
  }
 }
 decorate(win.body);
}
function attach(win){if(win.element.querySelector('.classic-menubar'))return;
 const name=typeIcons[win.type]||'file';win.element.style.setProperty('--app-icon','var(--icon-'+name+')');win.task.style.setProperty('--app-icon','var(--icon-'+name+')');const header=win.element.querySelector('header');header.prepend(icon(name));
 const config=configs[win.type]||{groups:[['File','f',[]],['View','v',[]]]},bar=document.createElement('nav');bar.className='classic-menubar';bar.setAttribute('role','menubar');bar.setAttribute('aria-label','Application Menu');
 for(const [label,key,commands] of [...config.groups,['Help','h',[]]]){const b=document.createElement('button');b.type='button';b.dataset.mnemonic=key;b.setAttribute('role','menuitem');b.setAttribute('aria-haspopup','menu');b.setAttribute('aria-expanded','false');b.textContent=label;b.onclick=()=>{if(anchor===b){closeMenu(true);return;}showMenu(b,label==='Help'?[{label:'Using This Application',run:()=>s.show('Help – '+win.task.textContent,'<p>'+window.Win2kTools.esc(help[win.type]||'Open the application menus for available commands.')+'</p>')}]:entries(win,label,commands),win);};b.onmouseenter=()=>{if(popup&&anchor?.parentElement===bar&&anchor!==b)b.click();};b.onkeydown=e=>{if(['ArrowDown','Enter',' '].includes(e.key)){e.preventDefault();b.click();}if(['ArrowRight','ArrowLeft'].includes(e.key)){e.preventDefault();const buttons=[...bar.children],i=buttons.indexOf(b);buttons[(i+(e.key==='ArrowRight'?1:-1)+buttons.length)%buttons.length].focus();}};bar.append(b);}
 header.after(bar);win.body.addEventListener('focusin',e=>{win.uiLastFocus=e.target;});win.body.addEventListener('change',()=>enhance(win));let pending=false;const observer=new MutationObserver(()=>{if(!pending){pending=true;queueMicrotask(()=>{pending=false;enhance(win);});}});observer.observe(win.body,{childList:true,subtree:true});win.uiCleanup=()=>{observer.disconnect();if(currentWin===win)closeMenu();};enhance(win);
}
document.addEventListener('pointerdown',e=>{if(popup&&!popup.contains(e.target)&&!anchor?.contains(e.target))closeMenu();});window.addEventListener('blur',()=>closeMenu());window.addEventListener('resize',()=>closeMenu());
document.addEventListener('keydown',e=>{if(document.querySelector('#session').hidden||document.querySelector('#window').open)return;const win=d.listWindows().find(w=>!w.element.hidden&&!w.element.classList.contains('inactive'));if(!win)return;if(e.key==='F10'&&!e.shiftKey){e.preventDefault();win.element.querySelector('.classic-menubar button')?.focus();}if(e.altKey&&!e.ctrlKey&&!e.metaKey){const b=[...win.element.querySelectorAll('.classic-menubar button')].find(b=>b.dataset.mnemonic===e.key.toLowerCase());if(b){e.preventDefault();b.click();}}});
window.Win2kUI={attach,decorate,icon};decorate(document);for(const win of d.listWindows())attach(win);
new MutationObserver(()=>decorate(document.querySelector('#desktop-icons'))).observe(document.querySelector('#desktop-icons'),{childList:true,subtree:true});
})();
