(() => {
 'use strict';
 const shell=window.Win2kShell,root=document.querySelector('#desktop-icons'),desktop=document.querySelector('#desktop');
 const key=icon=>icon.dataset.fileId?'file:'+icon.dataset.fileId:icon.dataset.shortcutId?'link:'+icon.dataset.shortcutId:'app:'+icon.dataset.action;
 function layout(){
  const positions=shell.getPositions(),icons=[...root.querySelectorAll('.desktop-icon')],occupied=[];
  const maxX=Math.max(0,desktop.clientWidth-130),maxY=Math.max(0,desktop.clientHeight-115);
  function place(icon,point){const x=Math.min(point[0],maxX),y=Math.min(point[1],maxY);icon.style.left=x+'px';icon.style.top=y+'px';occupied.push([x,y]);}
  for(const icon of icons){icon.draggable=true;if(positions[key(icon)])place(icon,positions[key(icon)]);}
  for(const icon of icons.filter(icon=>!positions[key(icon)])){
   let x=0,y=0;while(occupied.some(([a,b])=>Math.abs(a-x)<108&&Math.abs(b-y)<88)){y+=96;if(y>maxY){y=0;x+=114;}if(x>10000)break;}
   place(icon,[x,y]);
  }
 }
 let moving=null;
 root.addEventListener('dragstart',event=>{
  const icon=event.target.closest('.desktop-icon');if(!icon)return;
  const rect=icon.getBoundingClientRect();moving={key:key(icon),dx:event.clientX-rect.left,dy:event.clientY-rect.top};
  event.dataTransfer.setData('application/x-win2k-icon',moving.key);event.dataTransfer.effectAllowed='move';
 });
 desktop.addEventListener('drop',event=>{
  if(!moving||!event.dataTransfer.types.includes('application/x-win2k-icon'))return;
  // A folder or trash target handles actual file moves through the file manager.
  const target=event.target.closest('.desktop-icon');
  if(event.dataTransfer.types.includes('application/x-win2k-shortcut')&&target?.dataset.action==='trash'){moving=null;return;}
  if(event.dataTransfer.types.includes('application/x-win2k-file')&&target&&(target.dataset.fileId||['files','trash'].includes(target.dataset.action)))return;
  if(event.target.closest('.app-window'))return;
  event.preventDefault();event.stopImmediatePropagation();
  const rect=root.getBoundingClientRect();
  const x=Math.max(0,Math.min(desktop.clientWidth-130,Math.round(event.clientX-rect.left-moving.dx)));
  const y=Math.max(0,Math.min(desktop.clientHeight-115,Math.round(event.clientY-rect.top-moving.dy)));
  shell.setPosition(moving.key,[x,y]);moving=null;layout();
 },true);
 desktop.addEventListener('dragover',event=>{if(moving){event.preventDefault();event.dataTransfer.dropEffect='move';}});
 root.addEventListener('dragend',()=>{moving=null;});
 new MutationObserver(layout).observe(root,{childList:true,subtree:true});
 window.addEventListener('resize',layout);window.addEventListener('win2k-user',()=>requestAnimationFrame(layout));
 shell.actions['arrange-icons']=()=>{for(const k of Object.keys(shell.getPositions()))delete shell.getPositions()[k];shell.setPosition('layout-reset',[0,0]);layout();};
 layout();
})();
