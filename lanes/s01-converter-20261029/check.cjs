const {chromium}=require('playwright');const fs=require('fs'),assert=require('assert/strict');
(async()=>{const browser=await chromium.launch({headless:true});let proof=[];try{
 for(const lang of ['en','zh'])for(const width of [1024,1440]){
  const page=await browser.newPage({viewport:{width,height:1000}});const route=lang==='zh'?'/zh/m3u8-to-mp4/':'/m3u8-to-mp4/';
  await page.goto('http://127.0.0.1:18880'+route,{waitUntil:'networkidle'});const root=page.locator('[data-vf-shortcode-tool="converter"]').first();await root.waitFor();
  assert.equal(await page.locator('h1').count(),1);assert.ok(await page.locator('.vf-m3u8-launchbar__back').isVisible());
  assert.equal(await page.locator('.vf-m3u8-launchbar__steps').isVisible(),false);assert.equal(await page.locator('.vf-m3u8-launchbar__current').isVisible(),false);
  assert.ok(await root.locator('[data-converter-url]').isVisible());assert.ok(await root.locator('[data-converter-generate]').isVisible());
  const metrics=await page.evaluate(()=>({width:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth}));assert.ok(metrics.scroll<=metrics.width+1,'horizontal overflow');
  await root.locator('[data-converter-url]').fill('https://example.invalid/video.m3u8');await root.locator('[data-converter-clear]').click();assert.equal(await root.locator('[data-converter-url]').inputValue(),'');
  await root.locator('[data-converter-view-mode="pro"]').click();await root.locator('[data-converter-view-mode="pro"][aria-selected="true"]').waitFor({timeout:5000});
  await root.locator('[data-converter-view-mode="simple"]').click();await root.locator('[data-converter-view-mode="simple"][aria-selected="true"]').waitFor({timeout:5000});
  if(width===1440){
   const target=root.locator('.vf-converter').first();
   await root.locator('[data-load-converter-sample]').first().click();
   await page.waitForFunction(()=>{const r=document.querySelector('.vf-converter');return r&&['completed','blocked'].includes(r.dataset.vfConverterTaskState)},null,{timeout:60000});
   const state=await target.getAttribute('data-vf-converter-task-state');
   const result=await target.innerText();
   fs.writeFileSync('proof/converter-sample-'+lang+'.json',JSON.stringify({state,text:result.slice(-6000)}));
   assert.equal(state,'completed','bundled sample should finish');
   assert.equal(await target.getAttribute('data-vf-converter-output-ready'),'1','output must be ready');
  }
  await page.screenshot({path:`proof/converter-${lang}-${width}.png`,fullPage:true});proof.push({language:lang,width,controls:'PASS',overflow:'PASS',actual_conversion:width===1440?'PASS':'NOT_RUN'});await page.close();
 }
 fs.writeFileSync('proof/converter.json',JSON.stringify({status:'PASS',cases:proof,production:'UNTOUCHED'},null,2));
 }finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
