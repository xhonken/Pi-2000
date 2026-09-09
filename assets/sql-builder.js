/* SELECT builder with metadata-driven joins and an editable SQL handoff. */
(() => {
 'use strict';
 const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const ident=v=>'`'+String(v).replace(/`/g,'``')+'`';
 const literal=v=>"CONVERT(X'"+Array.from(new TextEncoder().encode(v),b=>b.toString(16).padStart(2,'0')).join('')+"' USING utf8mb4)";
 window.Win2kSQLBuilder={attach(ctx){ctx.button(ctx.toolbar,'Query Builder',async()=>{
  const database=ctx.database();if(!database)throw Error('Select a database first.');
  const tables=(await ctx.command('objects',{database})).results[0].rows.map(r=>r[0]);
  const relations=(await ctx.command('admin_list',{section:'relations',database})).results[0].rows;
  const el=ctx.dialog('SQL Query Builder',`<p>Build a SELECT query without changing data. Aliases t1, t2… distinguish tables, including repeated tables.</p><label>Starting table<select name="base">${tables.map(t=>`<option>${esc(t)}</option>`).join('')}</select></label><div class="qb-joins"></div><div class="qb-add"></div><label>Output columns (Ctrl / Shift selects several)<select name="columns" multiple size="7"></select></label><fieldset><legend>Optional filter — WHERE</legend><label>Column<select name="filter"></select></label><label>Comparison<select name="operator">${['=','<>','>','>=','<','<=','LIKE','IS NULL','IS NOT NULL'].map(v=>`<option>${esc(v)}</option>`).join('')}</select></label><label>Value<input name="value"></label><small>A WHERE filter on the optional side of an outer join can exclude rows with no match. Use IS NULL to find missing matches. LIKE supports % and _ wildcards.</small></fieldset><label>Sort by<select name="sort"></select></label><label>Direction<select name="direction"><option>ASC</option><option>DESC</option></select></label><label>Maximum rows<input name="limit" type="number" min="1" max="1000" value="100"></label><div class="qb-preview-actions"></div><pre class="db-admin-preview" aria-label="Generated SQL"></pre>`);
  el.classList.add('db-admin-wide');const form=el.querySelector('form'),f=form.elements;f.base.value=ctx.table()||tables[0]||'';let joins=[],columns=new Map(),updating=false;
  const error=e=>el.querySelector('.db-dialog-error').textContent=e.message;
  const refs=()=>[{table:f.base.value,alias:'t1'},...joins.map((j,i)=>({table:j.table,alias:'t'+(i+2)}))];
  const options=list=>list.map(v=>`<option value="${esc(v)}">${esc(v)}</option>`).join('');
  const reference=v=>{const i=v.indexOf('.');if(i<0)throw Error('Select a column.');return ident(v.slice(0,i))+'.'+ident(v.slice(i+1));};
  async function metadata(){for(const table of refs().map(r=>r.table)){if(!columns.has(table)){const result=await ctx.command('columns',{database,table});columns.set(table,result.results[0].rows.map(r=>r[0]));}}}
  function sql(){
   const all=refs(),chosen=Array.from(f.columns.selectedOptions,o=>o.value);
   if(!all[0].table)throw Error('Choose a starting table.');
   let value='SELECT '+(chosen.length?chosen.map(reference).join(',\n       '):all.map(r=>ident(r.alias)+'.*').join(', '))+'\nFROM '+ident(database)+'.'+ident(all[0].table)+' AS '+ident('t1');
   joins.forEach((join,i)=>{const alias='t'+(i+2);value+='\n'+join.kind+' JOIN '+ident(database)+'.'+ident(join.table)+' AS '+ident(alias);if(join.kind!=='CROSS'){const pairs=join.relation?join.suggestions[join.relation-1]?.pairs:[[join.left,alias+'.'+join.right]];if(!pairs?.length||pairs.some(p=>!p[0]||!p[1]))throw Error('Choose both columns for every join.');value+=' ON '+pairs.map(([a,b])=>reference(a)+' = '+reference(b)).join(' AND ');}});
   if(f.filter.value)value+='\nWHERE '+reference(f.filter.value)+' '+f.operator.value+(['IS NULL','IS NOT NULL'].includes(f.operator.value)?'':' '+literal(f.value.value));
   if(f.sort.value)value+='\nORDER BY '+reference(f.sort.value)+' '+f.direction.value;
   const limit=Number(f.limit.value);if(!Number.isInteger(limit)||limit<1||limit>1000)throw Error('Use a row limit from 1 to 1,000.');return value+'\nLIMIT '+limit+';';
  }
  function preview(){try{el.querySelector('.db-admin-preview').textContent=sql();el.querySelector('.db-dialog-error').textContent='';}catch(e){error(e);}}
  async function draw(){
   updating=true;form.querySelector('[type=submit]').disabled=true;
   try{await metadata();if(!el.isConnected)return;const all=refs(),values=all.flatMap(r=>(columns.get(r.table)||[]).map(c=>r.alias+'.'+c)),selected=Array.from(f.columns.selectedOptions,o=>o.value),filter=f.filter.value,sort=f.sort.value;
    f.columns.innerHTML=options(values);for(const o of f.columns.options)o.selected=selected.includes(o.value);f.filter.innerHTML='<option value="">No filter</option>'+options(values);f.sort.innerHTML='<option value="">No sorting</option>'+options(values);f.filter.value=values.includes(filter)?filter:'';f.sort.value=values.includes(sort)?sort:'';
    const area=el.querySelector('.qb-joins');area.replaceChildren();
    joins.forEach((join,i)=>{
     const alias='t'+(i+2),earlier=all.slice(0,i+1),lefts=earlier.flatMap(r=>(columns.get(r.table)||[]).map(c=>r.alias+'.'+c));if(!lefts.includes(join.left))join.left=lefts[0]||'';if(!(columns.get(join.table)||[]).includes(join.right))join.right=(columns.get(join.table)||[])[0]||'';
     const groups=new Map();for(const prior of earlier)for(const r of relations){let pair;if(r[1]===prior.table&&r[3]===database&&r[4]===join.table)pair=[prior.alias+'.'+r[2],alias+'.'+r[5]];else if(r[1]===join.table&&r[3]===database&&r[4]===prior.table)pair=[prior.alias+'.'+r[5],alias+'.'+r[2]];if(pair){const key=prior.alias+':'+r[1]+':'+r[0];if(!groups.has(key))groups.set(key,{label:r[0]+' → '+prior.alias,pairs:[]});groups.get(key).pairs.push(pair);}}
     join.suggestions=Array.from(groups.values());if(join.relation===undefined)join.relation=join.suggestions.length?1:0;if(join.relation>join.suggestions.length)join.relation=0;
     const box=document.createElement('fieldset');box.innerHTML=`<legend>Join ${alias}</legend><label>Type<select data-kind>${options(['LEFT','RIGHT','INNER','CROSS'])}</select></label><p data-help></p><label>Table<select data-table>${options(tables)}</select></label><label>Relationship<select data-relation><option value="0">Choose columns manually</option>${join.suggestions.map((r,n)=>`<option value="${n+1}">${esc(r.label)}</option>`).join('')}</select></label><div data-manual><label>Existing table column<select data-left>${options(lefts)}</select></label><label>${alias} column<select data-right>${options(columns.get(join.table)||[])}</select></label></div>`;
     const $=q=>box.querySelector(q);$('[data-kind]').value=join.kind;$('[data-table]').value=join.table;$('[data-left]').value=join.left;$('[data-right]').value=join.right;$('[data-relation]').value=String(join.relation);
     function help(){$('[data-help]').textContent={LEFT:'Keep every row from the existing left side. Unmatched new-table columns become NULL.',RIGHT:'Keep every row from the new right table. Unmatched existing-table columns become NULL.',INNER:'Keep only rows that match on both sides.',CROSS:'Combine every left row with every right row. This can produce a very large result.'}[join.kind];$('[data-manual]').hidden=join.kind==='CROSS'||!!join.relation;$('[data-relation]').disabled=join.kind==='CROSS';}
     $('[data-kind]').onchange=e=>{join.kind=e.target.value;help();preview();};$('[data-table]').onchange=e=>{join.table=e.target.value;join.relation=undefined;draw().catch(error);};$('[data-relation]').onchange=e=>{join.relation=Number(e.target.value);help();preview();};$('[data-left]').onchange=e=>{join.left=e.target.value;preview();};$('[data-right]').onchange=e=>{join.right=e.target.value;preview();};ctx.button(box,'Remove This and Later Joins',()=>{joins.splice(i);return draw();});help();area.append(box);
    });preview();
   }finally{updating=false;form.querySelector('[type=submit]').disabled=false;}
  }
  ctx.button(el.querySelector('.qb-add'),'Add Join',async()=>{if(updating)return;if(joins.length>=8)throw Error('The builder supports up to eight joins.');joins.push({table:tables.find(t=>t!==f.base.value)||tables[0],kind:'LEFT'});await draw();});
  ctx.button(el.querySelector('.qb-preview-actions'),'Update SQL Preview',preview);
  el.classList.add('qb-dialog');
  const fields=el.querySelector('.db-dialog-fields'),navigation=document.createElement('div'),panels=document.createElement('div');navigation.className='db-admin-tabs';navigation.setAttribute('role','tablist');panels.className='qb-panels';
  const groups=[['Tables and Joins',[f.base.closest('label'),el.querySelector('.qb-joins'),el.querySelector('.qb-add')]],['Columns and Filters',[f.columns.closest('label'),f.filter.closest('fieldset'),f.sort.closest('label'),f.direction.closest('label'),f.limit.closest('label')]],['SQL Preview',[el.querySelector('.qb-preview-actions'),el.querySelector('.db-admin-preview')]]];
  fields.querySelector('.db-dialog-error').before(navigation,panels);
  groups.forEach(([label,nodes],index)=>{const panel=document.createElement('section');panel.hidden=index!==0;panel.setAttribute('role','tabpanel');nodes.forEach(n=>panel.append(n));panels.append(panel);const b=ctx.button(navigation,label,()=>{for(const [i,p] of Array.from(panels.children).entries())p.hidden=i!==index;for(const [i,t] of Array.from(navigation.children).entries())t.setAttribute('aria-selected',String(i===index));preview();});b.setAttribute('role','tab');b.setAttribute('aria-selected',String(index===0));});
  f.base.onchange=()=>{joins=[];draw().catch(error);};for(const key of ['columns','filter','operator','value','sort','direction','limit'])f[key].addEventListener('change',preview);
  form.querySelector('[type=submit]').textContent='Open SQL Query';form.onsubmit=e=>{e.preventDefault();try{if(updating)return;ctx.putSQL(sql(),'Query Builder');el.close();}catch(e){error(e);}};
  await draw();
 });}};
})();
