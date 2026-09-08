const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1400,height:950}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:18765');
  await page.locator('#login-form [name=password]').fill('browser-test-password');
  await page.locator('#login-form [type=submit]').click();await page.locator('#session').waitFor({state:'visible'});
  const appearance=()=>page.locator('#desktop').evaluate(el=>{const s=getComputedStyle(el);return [s.backgroundColor,s.outlineStyle,s.outlineWidth];});
  const normal=await appearance();
  const icon=page.locator('#desktop [data-action=files]'),rect=await icon.boundingBox();
  await page.mouse.move(rect.x+40,rect.y+20);await page.mouse.down();await page.mouse.move(650,350,{steps:20});
  assert.deepEqual(await appearance(),normal,'Desktop appearance during drag');
  await page.mouse.up();assert.deepEqual(await appearance(),normal,'Desktop appearance after drop');
  assert.equal(await page.locator('.file-drop-target').count(),0);
  await page.waitForFunction(async()=>{const data=await(await fetch('/api/desktop')).json();return data.positions?.['app:files']?.[0]>400;});
  // Folder feedback must also disappear on cancellation and consumed drops.
  const dt=await page.evaluateHandle(()=>{const dt=new DataTransfer();dt.items.add(new File(['hello'],'test.txt'));return dt;});
  await icon.dispatchEvent('dragover',{dataTransfer:dt});assert.equal(await icon.evaluate(el=>el.classList.contains('file-drop-target')),true);
  await page.locator('#desktop').dispatchEvent('dragend',{dataTransfer:dt});assert.equal(await page.locator('.file-drop-target').count(),0);
  await icon.dispatchEvent('dragover',{dataTransfer:dt});await icon.dispatchEvent('drop',{dataTransfer:dt});
  assert.equal(await page.locator('.file-drop-target').count(),0);
  await page.locator('.files-window').getByRole('row').filter({hasText:'test.txt'}).waitFor();
  assert.deepEqual(await appearance(),normal);assert.deepEqual(errors,[]);
  console.log('PASS: desktop unchanged during and after real icon drag, position saved, folder highlight cleared on cancellation and upload, no JS errors');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
