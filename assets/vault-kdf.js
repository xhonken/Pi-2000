/* One-use worker: terminated by the client after each derivation. */
importScripts('vendor/hash-wasm/argon2.umd.min.js');
self.onmessage=async({data})=>{
 try {
  const key=await hashwasm.argon2id({password:data.password,salt:new Uint8Array(data.salt),parallelism:1,iterations:3,memorySize:65536,hashLength:32,outputType:'binary'});
  data.password='';self.postMessage(key.buffer,[key.buffer]);
 }catch{self.postMessage({error:'Password derivation failed. This browser must support WebAssembly.'});}
};
