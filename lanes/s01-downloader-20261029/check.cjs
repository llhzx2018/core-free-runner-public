const {chromium}=require('playwright');const fs=require('fs'),assert=require('assert/strict');
(async()=>{const browser=await chromium.launch({headless:true});let proof=[];try{
 for(const lang of ['en','zh'])for(const width of [1024,1440]){
  const page=await browser.newPage({viewport:{width,height:1000}});const path=lang==='zh'?'/zh/m3u8-downloader/':'/m3u8-downloader/';
  await page.goto('http://127.0.0.1:18880'+path,{waitUntil:'networkidle'});const root=page.locator('[data-vf-tool-id="downloader"]').first();await root.waitFor();
  assert.equal(await page.locator('h1').count(),1);assert.ok(await page.locator('.vf-m3u8-launchbar__back').isVisible());
  assert.equal(await page.locator('.vf-m3u8-launchbar__steps').isVisible(),false);assert.equal(await page.locator('.vf-m3u8-launchbar__current').isVisible(),false);
  const description=page.locator('.vf-tool-faq-section .vf-tool-support-head p').first();const text=(await description.innerText()).trim();assert.ok(text.length>0);assert.ok(!text.includes('useful for search and real users'));assert.ok(!text.includes('同时服务搜索和真实用户'));
  assert.ok(await root.locator('[data-downloader-url]').isVisible());assert.ok(await root.locator('[data-vf-dl-id="analyzeBtn"]').isVisible());
  const metrics=await page.evaluate(()=>({width:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth}));assert.ok(metrics.scroll<=metrics.width+1,'horizontal page overflow');
  await root.locator('[data-downloader-url]').fill('https://example.invalid/video.m3u8');await root.locator('[data-vf-dl-id="clearBtn"]').click();assert.equal(await root.locator('[data-downloader-url]').inputValue(),'');
  await root.locator('[data-vf-downloader-mode-button="pro"]').click();await root.locator('[data-vf-downloader-mode-button="pro"][aria-checked="true"]').waitFor({timeout:4000});
  await root.locator('[data-vf-downloader-mode-button="normal"]').click();await root.locator('[data-vf-downloader-mode-button="normal"][aria-checked="true"]').waitFor({timeout:4000});
  if(width===1440){
   await page.route('https://download-fixture.invalid/**',async route=>{const u=route.request().url();const body=u.endsWith('/fixture.m3u8')?'#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:2\n#EXTINF:2.0,\none.ts\n#EXTINF:2.0,\ntwo.ts\n#EXT-X-ENDLIST\n':u.endsWith('/one.ts')?'SEGMENT-ONE':u.endsWith('/two.ts')?'SEGMENT-TWO':'';await route.fulfill({status:body?200:404,headers:{'access-control-allow-origin':'*','content-type':u.endsWith('.m3u8')?'application/vnd.apple.mpegurl':'video/mp2t'},body});});
   await root.locator('[data-downloader-url]').fill('https://download-fixture.invalid/fixture.m3u8');
   const pending=page.waitForEvent('download',{timeout:20000});await root.locator('[data-vf-dl-id="analyzeBtn"]').click();const download=await pending;
   const payload=fs.readFileSync(await download.path()).toString();assert.equal(payload,'SEGMENT-ONESEGMENT-TWO','download content/order');
   await page.waitForFunction(()=>{const b=document.querySelector('#barFill'),p=document.querySelector('#progressBar');return b && p && p.getAttribute('aria-valuenow')==='100' && b.getBoundingClientRect().width >= p.getBoundingClientRect().width-2;},null,{timeout:5000});
  }
  await page.screenshot({path:`proof/downloader-${lang}-${width}.png`,fullPage:true});proof.push({language:lang,width,description:text,controls:'PASS',overflow:'PASS'});await page.close();
 }
 fs.writeFileSync('proof/downloader.json',JSON.stringify({status:'PASS',cases:proof,production:'UNTOUCHED'},null,2));
 }finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
