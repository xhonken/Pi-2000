const {chromium}=require('playwright'),assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.PI2000_TEST_CHROMIUM||'/usr/bin/chromium',headless:true});
 try{
  const page=await browser.newPage();await page.goto(process.env.PI2000_TEST_URL);
  const result=await page.evaluate(async()=>{
   const c=PiVaultCrypto,A='original list fixture passphrase',B='original secret fixture passphrase',N='rotated list fixture passphrase',M='rotated secret fixture passphrase';
   const original=await c.create(A,B),v=original.vault,a=await c.unlock(v,'a',A),b=await c.unlock(v,'b',B),entry=c.id();
   const content={username:'fixture',url:'',secret:'before rotation',notes:''};
   await c.writeEntry(v,b,entry,content);await c.writeIndex(v,a,{items:[{id:entry,title:'Fixture',category:'Password',created:1,updated:1}]});
   const rotated=await c.rekey(v,A,B,N,M);await c.unlock(rotated.vault,'a',N);const rb=await c.unlock(rotated.vault,'b',M);
   const retained=(await c.readEntry(rotated.vault,rb,entry)).secret==='before rotation';
   await c.writeEntry(rotated.vault,rb,entry,{...content,secret:'after rotation'});
   let oldContentKeyRejected=false,oldListKeyRejected=false;
   try{await c.readEntry(rotated.vault,b,entry);}catch{oldContentKeyRejected=true;}
   try{await c.readIndex(rotated.vault,a);}catch{oldListKeyRejected=true;}
   const recovered=await c.recover(rotated.vault,rotated.recovery,A,B),recoveredB=await c.unlock(recovered.vault,'b',B);
   const recoveryRetained=(await c.readEntry(recovered.vault,recoveredB,entry)).secret==='after rotation';
   let previousKeyRejectedAfterRecovery=false;try{await c.readEntry(recovered.vault,rb,entry);}catch{previousKeyRejectedAfterRecovery=true;}
   // A corrupt entry must not result in a partially re-encrypted vault.
   const damaged=structuredClone(v);damaged.entries[entry].data='AAAA'+damaged.entries[entry].data.slice(4);
   let damagedRejected=false;try{await c.rekey(damaged,A,B,N,M);}catch{damagedRejected=true;}
   return {retained,oldContentKeyRejected,oldListKeyRejected,recoveryRetained,previousKeyRejectedAfterRecovery,damagedRejected};
  });
  assert.deepEqual(result,{retained:true,oldContentKeyRejected:true,oldListKeyRejected:true,recoveryRetained:true,previousKeyRejectedAfterRecovery:true,damagedRejected:true});
  console.log('PASS Pi-Vault password/recovery rotation replaces data keys, preserves entries and rejects compromised old keys and corrupt content');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
