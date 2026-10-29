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
  await root.locator('[data-vf-downloader-mode-button="pro"]').click();assert.equal(await root.locator('[data-vf-downloader-mode-button="pro"]').getAttribute('aria-selected'),'true');
  await root.locator('[data-vf-downloader-mode-button="normal"]').click();assert.equal(await root.locator('[data-vf-downloader-mode-button="normal"]').getAttribute('aria-selected'),'true');
  await page.screenshot({path:`proof/downloader-${lang}-${width}.png`,fullPage:true});proof.push({language:lang,width,description:text,controls:'PASS',overflow:'PASS'});await page.close();
 }
 fs.writeFileSync('proof/downloader.json',JSON.stringify({status:'PASS',cases:proof,production:'UNTOUCHED'},null,2));
 }finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
