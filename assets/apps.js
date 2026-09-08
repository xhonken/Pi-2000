/* Shared lifecycle registry for desktop apps. App-specific state stays in devices.js. */
(() => {
 'use strict';
 const apps=new Map();
 window.Win2kApps=Object.freeze({
  register(descriptor){
   if(!descriptor.type || apps.has(descriptor.type))throw new Error('The application is already registered or has no type.');
   apps.set(descriptor.type,Object.freeze({allowed:()=>true,singleton:false,...descriptor}));
  },
  get(type){return apps.get(type);},
  async restore(entry,user,context){
   const app=apps.get(entry.type);
   if(!app || !app.allowed(user))return null;
   return app.restore?.(entry,context);
  }
 });
})();
