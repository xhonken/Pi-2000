/* Versioned client encryption; never sends passwords or plaintext to the server. */
(() => {
 'use strict';
 const te=new TextEncoder(),td=new TextDecoder('utf-8',{fatal:true}),hex=/^[a-f0-9]{32}$/;
 const kdf=Object.freeze({name:'argon2id',memory:65536,iterations:3,parallelism:1});
 const bytes=n=>crypto.getRandomValues(new Uint8Array(n));
 const id=()=>Array.from(bytes(16),v=>v.toString(16).padStart(2,'0')).join('');
 function b64(raw){let text='';for(const value of raw)text+=String.fromCharCode(value);return btoa(text);}
 function un64(text,min=0,max=4*1024*1024){if(typeof text!=='string'||text.length>Math.ceil(max/3)*4)throw Error('Invalid encrypted field.');let raw;try{raw=Uint8Array.from(atob(text),c=>c.charCodeAt(0));}catch{throw Error('Invalid encrypted field.');}if(raw.length<min||raw.length>max||b64(raw)!==text)throw Error('Invalid encrypted field.');return raw;}
 function exact(value,fields){if(!value||Object.getPrototypeOf(value)!==Object.prototype||Object.keys(value).sort().join(',')!==fields.slice().sort().join(','))throw Error('Unsupported Pi-Vault format.');}
 function envelope(v,min=16,max=131072){exact(v,['iv','data']);un64(v.iv,12,12);un64(v.data,min,max);}
 function validate(v){exact(v,['format','id','kdf','a','b','recovery','index','entries']);if(v.format!==1||!hex.test(v.id))throw Error('Unsupported Pi-Vault format.');exact(v.kdf,Object.keys(kdf));if(Object.keys(kdf).some(k=>v.kdf[k]!==kdf[k]))throw Error('Unsupported password derivation settings.');for(const slot of ['a','b']){exact(v[slot],['salt','wrapped']);un64(v[slot].salt,16,16);envelope(v[slot].wrapped,48,48);}if(v.a.salt===v.b.salt)throw Error('Invalid password salts.');envelope(v.recovery,80,80);envelope(v.index,16,262144);if(!v.entries||Object.getPrototypeOf(v.entries)!==Object.prototype||Object.keys(v.entries).length>500)throw Error('Invalid entry collection.');for(const [key,value] of Object.entries(v.entries)){if(!hex.test(key))throw Error('Invalid entry identifier.');envelope(value);}return v;}
 function strong(a,b){if(typeof a!=='string'||typeof b!=='string'||[a,b].some(p=>p.length<14||te.encode(p).length>512))throw Error('Use two different passphrases of at least 14 characters (maximum 512 UTF-8 bytes).');if(a===b)throw Error('Passwords A and B must be different.');}
 async function key(raw){return crypto.subtle.importKey('raw',raw,'AES-GCM',false,['encrypt','decrypt']);}
 // Stable authenticated-data prefix: changing a product label must not break existing exports.
 const aad=(v,label)=>te.encode('Pi-2000 Vault 1|'+v.id+'|'+label);
 async function encrypt(k,raw,context){const iv=bytes(12);return {iv:b64(iv),data:b64(new Uint8Array(await crypto.subtle.encrypt({name:'AES-GCM',iv,additionalData:context,tagLength:128},k,raw)))};}
 async function decrypt(k,env,context){return new Uint8Array(await crypto.subtle.decrypt({name:'AES-GCM',iv:un64(env.iv,12,12),additionalData:context,tagLength:128},k,un64(env.data)));}
 async function derive(password,salt,signal){
  if(signal?.aborted)throw Error('Pi-Vault locked.');
  return new Promise((resolve,reject)=>{
   const worker=new Worker('assets/vault-kdf.js');let timer;
   const finish=(error,result)=>{clearTimeout(timer);worker.terminate();signal?.removeEventListener('abort',abort);password='';error?reject(error):resolve(result);};
   const abort=()=>finish(Error('Pi-Vault locked.'));signal?.addEventListener('abort',abort,{once:true});timer=setTimeout(()=>finish(Error('Password derivation timed out.')),60000);
   worker.onerror=()=>finish(Error('Cannot start the local password derivation worker.'));
   worker.onmessage=({data})=>data instanceof ArrayBuffer?finish(null,new Uint8Array(data)):finish(Error(data.error));
   worker.postMessage({password,salt});password='';
  });
 }
 async function wrapping(password,salt,signal){const raw=await derive(password,salt,signal);try{return await key(raw);}finally{raw.fill(0);}}
 async function wrap(v,slot,password,raw,signal){const salt=bytes(16),k=await wrapping(password,salt,signal);return {salt:b64(salt),wrapped:await encrypt(k,raw,aad(v,'key-'+slot))};}
 async function unlockRaw(v,slot,password,signal){validate(v);try{const k=await wrapping(password,un64(v[slot].salt),signal);return await decrypt(k,v[slot].wrapped,aad(v,'key-'+slot));}catch(error){if(signal?.aborted)throw Error('Pi-Vault locked.');throw Error('Incorrect password '+slot.toUpperCase()+' or damaged Pi-Vault.');}}
 async function unlock(v,slot,password,signal){const raw=await unlockRaw(v,slot,password,signal);try{return await key(raw);}finally{raw.fill(0);}}
 async function recovery(v,a,b){const raw=bytes(32),joined=new Uint8Array(64);joined.set(a);joined.set(b,32);try{v.recovery=await encrypt(await key(raw),joined,aad(v,'recovery'));return 'PV1-'+Array.from(raw,x=>x.toString(16).padStart(2,'0')).join('');}finally{raw.fill(0);joined.fill(0);}}
 async function create(a,b,signal){strong(a,b);const v={format:1,id:id(),kdf:{...kdf},entries:{}},rawA=bytes(32),rawB=bytes(32);try{v.a=await wrap(v,'a',a,rawA,signal);v.b=await wrap(v,'b',b,rawB,signal);v.index=await encrypt(await key(rawA),te.encode(JSON.stringify({items:[]})),aad(v,'index'));const code=await recovery(v,rawA,rawB);return {vault:v,recovery:code};}finally{rawA.fill(0);rawB.fill(0);}}
 function validIndex(v,index){exact(index,['items']);if(!Array.isArray(index.items)||index.items.length>500)throw Error('Invalid Pi-Vault list.');const seen=new Set();for(const item of index.items){exact(item,['id','title','category','created','updated']);if(!hex.test(item.id)||seen.has(item.id)||!Object.hasOwn(v.entries,item.id)||typeof item.title!=='string'||!item.title.trim()||item.title.length>200||!['Password','API key','Text','Link'].includes(item.category)||![item.created,item.updated].every(t=>Number.isSafeInteger(t)&&t>=0&&t<=8640000000000000))throw Error('Invalid Pi-Vault list.');seen.add(item.id);}if(seen.size!==Object.keys(v.entries).length)throw Error('Pi-Vault list does not match its encrypted entries.');return index;}
 async function readIndex(v,k){const raw=await decrypt(k,v.index,aad(v,'index'));try{return validIndex(v,JSON.parse(td.decode(raw)));}finally{raw.fill(0);}}
 async function writeIndex(v,k,index){validIndex(v,index);v.index=await encrypt(k,te.encode(JSON.stringify(index)),aad(v,'index'));}
 function validSecret(value){exact(value,['username','url','secret','notes']);if(Object.values(value).some(s=>typeof s!=='string'||te.encode(s).length>32768))throw Error('Each content field must be at most 32 KB.');if(te.encode(JSON.stringify(value)).length>120000)throw Error('Entry content is too large.');return value;}
 async function readEntry(v,k,id){const raw=await decrypt(k,v.entries[id],aad(v,'entry-'+id));try{return validSecret(JSON.parse(td.decode(raw)));}finally{raw.fill(0);}}
 async function writeEntry(v,k,id,value){v.entries[id]=await encrypt(k,te.encode(JSON.stringify(validSecret(value))),aad(v,'entry-'+id));}
 // Password changes and recovery must revoke old data keys too. Rewrapping
 // alone lets keys recovered from an old stolen export decrypt future entries.
 async function rotate(v,oldA,oldB,newA,newB,signal){
  const next={format:1,id:id(),kdf:{...kdf},entries:{}},rawA=bytes(32),rawB=bytes(32);
  const check=()=>{if(signal?.aborted)throw Error('Pi-Vault locked.');};
  try{
   check();const list=await readIndex(v,oldA),a=await key(rawA),b=await key(rawB);
   next.a=await wrap(next,'a',newA,rawA,signal);next.b=await wrap(next,'b',newB,rawB,signal);
   for(const item of list.items){check();const plain=await decrypt(oldB,v.entries[item.id],aad(v,'entry-'+item.id));try{validSecret(JSON.parse(td.decode(plain)));next.entries[item.id]=await encrypt(b,plain,aad(next,'entry-'+item.id));}finally{plain.fill(0);}}
   check();await writeIndex(next,a,list);const code=await recovery(next,rawA,rawB);check();return {vault:next,recovery:code};
  }finally{rawA.fill(0);rawB.fill(0);}
 }
 async function rekey(v,a,b,newA,newB,signal){strong(newA,newB);const oldA=await unlock(v,'a',a,signal),oldB=await unlock(v,'b',b,signal);return rotate(v,oldA,oldB,newA,newB,signal);}
 async function recover(v,code,newA,newB,signal){validate(v);strong(newA,newB);if(!/^PV1-[a-f0-9]{64}$/.test(code))throw Error('Enter the complete recovery key.');const rawKey=Uint8Array.from(code.slice(4).match(/../g),x=>parseInt(x,16));let raw;try{raw=await decrypt(await key(rawKey),v.recovery,aad(v,'recovery'));return await rotate(v,await key(raw.subarray(0,32)),await key(raw.subarray(32)),newA,newB,signal);}catch(e){if(e.name==='OperationError')throw Error('Incorrect recovery key or damaged Pi-Vault.');throw e;}finally{rawKey.fill(0);raw?.fill(0);}}
 window.PiVaultCrypto=Object.freeze({validate,strong,create,unlock,readIndex,writeIndex,readEntry,writeEntry,rekey,recover,id});
})();
