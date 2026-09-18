/* Placement, sorting and drag operations are separate from desktop object commands. */
(() => {
'use strict';
const shell=Win2kShell,manager=Win2kDesktopManager,root=document.querySelector('#desktop-icons'),desktop=document.querySelector('#desktop');
const {key}=manager,stepX=114,stepY=104;
let moving=null,scheduled=false;
function ordered(sort=manager.options().sort,direction=manager.options().direction){
 const nodes=manager.visible();if(sort==='manual')return nodes;
 const meta=new Map(nodes.map(el=>[el,manager.info(el)]));
 return nodes.sort((a,b)=>{const x=meta.get(a),y=meta.get(b);const cmp=['size','modified'].includes(sort)?((x.item?.[sort]||0)-(y.item?.[sort]||0)||x.name.localeCompare(y.name,undefined,{numeric:true,sensitivity:'base'})):sort==='type'?x.type.localeCompare(y.type)||x.name.localeCompare(y.name,undefined,{numeric:true,sensitivity:'base'}):x.name.localeCompare(y.name,undefined,{numeric:true,sensitivity:'base'});return (direction==='desc'?-1:1)*cmp||key(a).localeCompare(key(b));});
}
function gridPoint(index,rows){const band=88*rows;return [Math.floor(index%band/rows)*stepX,((index%rows)+Math.floor(index/band)*rows)*stepY];}
function layout(){
 scheduled=false;const options=manager.options(),nodes=ordered(),positions=shell.getPositions(),buckets=new Map(),placed=new Set();let nextCell=0;
 // Overflow extends horizontally instead of piling icons on the last visible cell.
 const rows=Math.max(1,Math.floor((desktop.clientHeight-36)/stepY)),width=Math.max(100,desktop.clientWidth-24);
 const maxX=Math.max(0,width-100),maxY=Math.max(0,desktop.clientHeight-126);
 function free(x,y){const bx=Math.floor(x/104),by=Math.floor(y/94);for(let i=bx-1;i<=bx+1;i++)for(let j=by-1;j<=by+1;j++)for(const [a,b] of buckets.get(i+','+j)||[])if(Math.abs(a-x)<104&&Math.abs(b-y)<94)return false;return true;}
 function cell(){for(;nextCell<10000;){const p=gridPoint(nextCell++,rows);if(free(...p))return p;}return [0,0];}
 function place(el,p){el.style.left=p[0]+'px';el.style.top=p[1]+'px';const bucket=Math.floor(p[0]/104)+','+Math.floor(p[1]/94);if(!buckets.has(bucket))buckets.set(bucket,[]);buckets.get(bucket).push(p);placed.add(el);el.draggable=!options.autoArrange;}
 if(!options.autoArrange)for(const el of nodes){const p=positions[key(el)];if(p){const point=[Math.min(p[0],maxX),Math.min(p[1],maxY)];if(free(...point))place(el,point);}}
 for(const el of nodes)if(!placed.has(el))place(el,cell());
}
function schedule(){if(!scheduled){scheduled=true;requestAnimationFrame(layout);}}
async function arrange(sort='name',direction=manager.options().direction){
 const nodes=ordered(sort,direction),rows=Math.max(1,Math.floor((desktop.clientHeight-36)/stepY));
 await shell.updateDesktop(state=>{state.view={...manager.options(),sort,direction};state.positions={};nodes.forEach((el,i)=>state.positions[key(el)]=gridPoint(i,rows));});layout();
}
async function align(){
 await shell.updateDesktop(state=>{state.view={...manager.options(),snap:true};for(const el of manager.visible())state.positions[key(el)]=[Math.max(0,Math.round(parseInt(el.style.left)/stepX)*stepX),Math.max(0,Math.round(parseInt(el.style.top)/stepY)*stepY)];});layout();
 // Persist collision-free display coordinates after rounding.
 await shell.updateDesktop(state=>{for(const el of manager.visible())state.positions[key(el)]=[parseInt(el.style.left),parseInt(el.style.top)];});
}
root.addEventListener('dragstart',event=>{
 const icon=event.target.closest('.desktop-icon');if(!icon)return;if(manager.options().autoArrange){event.preventDefault();shell.notify('Turn off Auto Arrange to move icons.');return;}
 if(!manager.selected.has(key(icon)))manager.select(icon);
 const rect=icon.getBoundingClientRect();moving={key:key(icon),dx:event.clientX-rect.left,dy:event.clientY-rect.top,origin:[parseInt(icon.style.left),parseInt(icon.style.top)],nodes:manager.visible().filter(el=>manager.selected.has(key(el))).map(el=>({el,key:key(el),x:parseInt(el.style.left),y:parseInt(el.style.top)}))};
 event.dataTransfer.setData('application/x-win2k-icon',moving.key);event.dataTransfer.effectAllowed='move';
});
desktop.addEventListener('drop',event=>{
 if(!moving||!event.dataTransfer.types.includes('application/x-win2k-icon'))return;
 if(event.target.closest('.app-window'))return;
 const target=event.target.closest('.desktop-icon');
 if(target?.dataset.action==='trash'){
  if(moving.nodes.length===1&&!moving.nodes[0].key.startsWith('app:')){moving=null;return;}
  event.preventDefault();event.stopImmediatePropagation();const nodes=moving.nodes.map(x=>x.el);moving=null;manager.afterDrag();manager.remove(nodes).catch(e=>shell.notify(e.message));return;
 }
 if(event.dataTransfer.types.includes('application/x-win2k-file')&&target&&(target.dataset.fileId||target.dataset.action==='files')){
  if(moving.nodes.length>1){event.preventDefault();event.stopImmediatePropagation();const ids=moving.nodes.map(n=>n.el.dataset.fileId),parent=target.dataset.fileId||'files';moving=null;if(ids.every(Boolean))Win2kFiles.moveDesktopItems(ids,parent).catch(e=>shell.notify(e.message));else shell.notify('Select only files and folders to move into a folder.');return;}
  moving=null;return;
 }
 event.preventDefault();event.stopImmediatePropagation();
 const bounds=root.getBoundingClientRect(),options=manager.options();let x=event.clientX-bounds.left-moving.dx,y=event.clientY-bounds.top-moving.dy;
 if(options.snap){x=Math.round(x/stepX)*stepX;y=Math.round(y/stepY)*stepY;}
 let dx=Math.round(x-moving.origin[0]),dy=Math.round(y-moving.origin[1]);
 dx=Math.max(-Math.min(...moving.nodes.map(n=>n.x)),Math.min(dx,10000-Math.max(...moving.nodes.map(n=>n.x))));
 dy=Math.max(-Math.min(...moving.nodes.map(n=>n.y)),Math.min(dy,Math.max(0,desktop.clientHeight-126)-Math.max(...moving.nodes.map(n=>n.y))));
 const nodes=moving.nodes;moving=null;manager.afterDrag();shell.updateDesktop(state=>{state.view={...options,sort:'manual'};for(const n of nodes)state.positions[n.key]=[Math.round(n.x+dx),Math.max(0,Math.round(n.y+dy))];}).catch(()=>{});layout();
},true);
desktop.addEventListener('dragover',event=>{if(moving){event.preventDefault();event.dataTransfer.dropEffect='move';}});
root.addEventListener('dragend',()=>{moving=null;manager.afterDrag();});
new MutationObserver(schedule).observe(root,{childList:true,subtree:true});
window.addEventListener('resize',schedule);window.addEventListener('win2k-user',schedule);window.addEventListener('win2k-icons-changed',schedule);
shell.actions['arrange-icons']=()=>arrange('name');window.Win2kIconLayout={arrange,align,layout};layout();
})();
