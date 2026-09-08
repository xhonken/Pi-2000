(() => {
'use strict';
const TAU=Math.PI*2,N=128;
const dist=(a,b)=>Math.hypot(a.x-b.x,a.y-b.y);
function shape(p){
 const positive=(v)=>{if(!Number.isFinite(v)||v<=0||v>10000)throw Error('All lengths must be greater than 0 and no more than 10,000 mm.');return v;};
 const type=p.type||'rectangle',w=positive(p.width),h=['square','circle','polygon','triangle'].includes(type)?w:positive(p.height);
 let points=[],area=0,error=0,labels=[];
 const pt=(x,y)=>({x,y});
 if(type==='rectangle'||type==='square'){points=[pt(0,0),pt(w,0),pt(w,h),pt(0,h)];area=w*h;}
 else if(type==='circle'||type==='ellipse'){for(let i=0;i<N;i++){const a=TAU*i/N;points.push(pt(w/2+w/2*Math.cos(a),h/2+h/2*Math.sin(a)));}area=Math.PI*w*h/4;error=Math.max(w,h)/2*(1-Math.cos(Math.PI/N));labels=[type==='circle'?`Ø ${w} · R ${w/2}`:`Axes ${w} × ${h}`];}
 else if(type==='slot'){if(w<h)throw Error('Slot length must be at least equal to its width.');const r=h/2;for(let i=0;i<=N/2;i++){const a=-Math.PI/2+TAU*i/N;points.push(pt(w-r+r*Math.cos(a),r+r*Math.sin(a)));}for(let i=0;i<=N/2;i++){const a=Math.PI/2+TAU*i/N;points.push(pt(r+r*Math.cos(a),r+r*Math.sin(a)));}area=(w-h)*h+Math.PI*r*r;error=r*(1-Math.cos(Math.PI/N));labels=[`L ${w} · W ${h} · R ${r}`];}
 else if(type==='triangle'){const b=positive(p.sideB),c=positive(p.sideC);if(w+b<=c||w+c<=b||b+c<=w)throw Error('The sum of the two shorter triangle sides must exceed the third side.');const x=(c*c+w*w-b*b)/(2*w),y=Math.sqrt(Math.max(0,c*c-x*x));points=[pt(0,0),pt(w,0),pt(x,y)];area=w*y/2;}
 else if(type==='right-triangle'){points=[pt(0,0),pt(w,0),pt(0,h)];area=w*h/2;}
 else if(type==='trapezoid'){const top=positive(p.top);if(top>w)throw Error('The top side of the trapezoid must not exceed the base.');points=[pt(0,0),pt(w,0),pt((w+top)/2,h),pt((w-top)/2,h)];area=(w+top)*h/2;}
 else if(type==='polygon'){const count=p.sides;if(!Number.isInteger(count)||count<3||count>12)throw Error('Choose between 3 and 12 sides.');const r=w/(2*Math.sin(Math.PI/count));if(r>10000)throw Error('The polygon is too large.');for(let i=0;i<count;i++){const a=-Math.PI/2-Math.PI/count+i*TAU/count;points.push(pt(r*Math.cos(a),r*Math.sin(a)));}area=count*w*w/(4*Math.tan(Math.PI/count));labels=[`${count} sides × ${w}`];}
 else throw Error('Unknown shape.');
 const minX=Math.min(...points.map(p=>p.x)),minY=Math.min(...points.map(p=>p.y));points=points.map(p=>pt(p.x-minX,p.y-minY));
 const width=Math.max(...points.map(p=>p.x)),height=Math.max(...points.map(p=>p.y));
 return {type,points,width,height,area,error,labels,curved:error>0};
}
function placed(p){const base=shape(p),angle=Number(p.rotation||0)*Math.PI/180;if(![p.x,p.y,angle].every(Number.isFinite)||Math.abs(p.x)>20000||Math.abs(p.y)>20000)throw Error('Invalid position.');return {...base,points:base.points.map(v=>{const x=v.x-base.width/2,y=v.y-base.height/2;return {x:p.x+x*Math.cos(angle)-y*Math.sin(angle),y:p.y+x*Math.sin(angle)+y*Math.cos(angle)};})};}
const cross=(a,b,p)=>(b.x-a.x)*(p.y-a.y)-(b.y-a.y)*(p.x-a.x);
function segmentDistance(p,a,b){const dx=b.x-a.x,dy=b.y-a.y,l=dx*dx+dy*dy,t=l?Math.max(0,Math.min(1,((p.x-a.x)*dx+(p.y-a.y)*dy)/l)):0;return Math.hypot(p.x-a.x-t*dx,p.y-a.y-t*dy);}
function inside(p,poly){return poly.every((a,i)=>cross(a,poly[(i+1)%poly.length],p)>=-1e-8);}
function bounds(s){return {x0:Math.min(...s.points.map(p=>p.x)),x1:Math.max(...s.points.map(p=>p.x)),y0:Math.min(...s.points.map(p=>p.y)),y1:Math.max(...s.points.map(p=>p.y))};}
function overlaps(a,b){const aa=bounds(a),bb=bounds(b);if(aa.x1<=bb.x0||bb.x1<=aa.x0||aa.y1<=bb.y0||bb.y1<=aa.y0)return false;
 for(const poly of [a.points,b.points])for(let i=0;i<poly.length;i++){const p=poly[i],q=poly[(i+1)%poly.length],axis={x:p.y-q.y,y:q.x-p.x};const project=s=>s.points.map(v=>v.x*axis.x+v.y*axis.y),ap=project(a),bp=project(b);if(Math.max(...ap)<=Math.min(...bp)+1e-8||Math.max(...bp)<=Math.min(...ap)+1e-8)return false;}return true;}
function migrate(data){if(data.schema===2)return data;return {schema:2,outer:{type:'rectangle',width:data.width,height:data.height},frame:data.frame||0,cuts:(data.holes||[]).map(h=>({type:'circle',width:h.d,height:h.d,x:h.x,y:h.y,rotation:0}))};}
function analyze(input){const model=migrate(input),outer=shape(model.outer),cuts=model.cuts;if(!Array.isArray(cuts)||cuts.length>200)throw Error('Maximum 200 holes/cutouts per drawing.');const frame=Number(model.frame||0);if(!Number.isFinite(frame)||frame<0||frame*2>=Math.min(outer.width,outer.height))throw Error('Frame width must be less than half the smallest outer dimension.');let opening=null;
 if(frame>0){if(!['rectangle','square','circle'].includes(outer.type))throw Error('Frame width applies to rectangles, squares and circles.');opening=placed({type:outer.type,width:outer.width-2*frame,height:outer.height-2*frame,x:outer.width/2,y:outer.height/2});}
 const shapes=cuts.map(placed),checks=shapes.map((s,i)=>{let clearance=Infinity,out=false;for(const p of s.points){if(!inside(p,outer.points))out=true;for(let j=0;j<outer.points.length;j++)clearance=Math.min(clearance,segmentDistance(p,outer.points[j],outer.points[(j+1)%outer.points.length]));}const problems=[];if(out)problems.push('Outside outer edge');if(opening&&overlaps(s,opening))problems.push('Overlaps frame opening');if(opening)for(const p of s.points)for(let j=0;j<opening.points.length;j++)clearance=Math.min(clearance,segmentDistance(p,opening.points[j],opening.points[(j+1)%opening.points.length]));if(opening)for(const p of opening.points)for(let j=0;j<s.points.length;j++)clearance=Math.min(clearance,segmentDistance(p,s.points[j],s.points[(j+1)%s.points.length]));const tolerance=outer.error+s.error+(opening?.error||0);if(!out&&clearance<=tolerance+1e-7)problems.push('On/near edge');return {...cuts[i],shape:s,clearance:out?-clearance:clearance,tolerance,problems};});
 for(let i=0;i<shapes.length;i++)for(let j=0;j<i;j++)if(overlaps(shapes[i],shapes[j])){checks[i].problems.push('Overlaps cutout '+(j+1));checks[j].problems.push('Overlaps cutout '+(i+1));}
 const gross=outer.area-(opening?.area||0);return {model,outer,opening,checks,gross,net:checks.some(c=>c.problems.length)?null:gross-shapes.reduce((sum,s)=>sum+s.area,0),tolerance:Math.max(outer.error,...checks.map(c=>c.tolerance))};
}
window.Win2kGeometry={shape,placed,analyze,migrate,dist};
})();
