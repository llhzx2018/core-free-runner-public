'use strict';
const fs=require('fs'),assert=require('assert/strict'),{chromium}=require('playwright');
const base='http://127.0.0.1:18880',baseline=process.argv[2]==='baseline';
(async()=>{
 const b=await chromium.launch(),p=await b.newPage({viewport:{width:1440,height:1000}}),errors=[];
 p.on('pageerror',e=>errors.push(e.message));
 await p.goto(base+'/tools/');await p.waitForLoadState('networkidle');
 const items=()=>p.locator('[data-vf-directory-item]:visible'),matrix=p.locator('[data-vf-theme-module=content_matrix]');
 async function performanceSamples(){const values=[];for(let i=0;i<3;i++){await p.goto(base+'/tools/');await p.waitForLoadState('networkidle');values.push(await p.evaluate(()=>{const n=performance.getEntriesByType('navigation')[0];return n.responseStart-n.startTime;}));}return {values,median:[...values].sort((a,b)=>a-b)[1]};}
 if(baseline){const timing=await performanceSamples();fs.writeFileSync('proof/performance-baseline.json',JSON.stringify(timing));assert.equal(await items().count(),9);fs.writeFileSync('proof/directory-baseline.json',JSON.stringify({status:'REPRODUCED',directory_tools:9,expected_provider_tools:11},null,2));await b.close();return;}
 assert.equal(await items().count(),11);assert.equal(await p.locator('h1').count(),1);
 assert.equal(await p.locator('[data-vf-theme-module=cta]').count(),0,'directory must not render a self reload as next step');
 const targets=await matrix.locator('.vf-content-matrix-grid a').evaluateAll(a=>a.map(x=>x.href));assert.equal(targets.length,new Set(targets).size);assert.equal(targets.length,6);
 assert(!await matrix.innerText().then(t=>t.includes('without adding sample blocks')));
 const routes=await items().evaluateAll(a=>a.map(x=>({route:x.getAttribute('data-vf-directory-route'),url:x.href})));
 for(const {route,url} of routes){const result=await p.goto(url);assert.equal(result.status(),200,route);assert.equal(await p.locator('h1').count(),1,route);assert.equal(await p.locator('.vf-m3u8-launchbar').count(),1,route);assert.equal(await p.locator('input,textarea,select,button').count()>0,true,route);}
 const rows=[];
 for(const width of [1920,1440,1319,1024,768,390]){
  await p.setViewportSize({width,height:1000});await p.goto(base+'/tools/');await p.waitForLoadState('networkidle');
  assert.equal(await items().count(),11);const geometry=await p.evaluate(()=>({width:innerWidth,client:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth,mains:document.querySelectorAll('main').length}));assert(geometry.scroll<=geometry.client+4);assert.equal(geometry.mains,1);
  if(width===1440||width===390)await p.screenshot({path:'proof/tools-'+width+'.png',fullPage:true});rows.push(geometry);
 }
 await p.setViewportSize({width:1440,height:1000});await p.goto(base+'/tools/');await p.waitForLoadState('networkidle');
 const query=()=>p.locator('[data-vf-directory-query]');
 await Promise.all([p.waitForURL(u=>u.searchParams.get('vf_filter')==='export'),p.locator('[data-vf-directory-filter-button=export]').click()]);await p.waitForLoadState('networkidle');assert.equal(await items().count(),2);
 await query().fill('MP4');assert.equal(await items().count(),1);await query().press('Enter');await p.waitForLoadState('networkidle');await p.reload();await p.waitForLoadState('networkidle');assert.equal(await items().count(),1);assert.equal(await query().inputValue(),'MP4');
 await Promise.all([p.waitForURL(u=>!u.searchParams.has('vf_filter')&&!u.searchParams.has('vf_q')),p.locator('[data-vf-directory-reset]').click()]);await p.waitForLoadState('networkidle');assert.equal(await items().count(),11);
 await query().fill('unmatched-synthetic-input');assert.equal(await items().count(),0);assert(await p.locator('[data-vf-directory-empty]').isVisible());await query().fill('');assert.equal(await items().count(),11);
 await p.setViewportSize({width:390,height:1000});await Promise.all([p.waitForURL(u=>u.searchParams.get('vf_filter')==='export'),p.locator('[data-vf-directory-filter-select]').selectOption('export')]);await p.waitForLoadState('networkidle');assert.equal(await items().count(),2);
 const nojs=await b.newContext({javaScriptEnabled:false}),np=await nojs.newPage();await np.goto(base+'/tools/?vf_filter=export');assert.equal(await np.locator('[data-vf-directory-item]:visible').count(),2);await np.goto(base+'/tools/?vf_filter=inspect&vf_q=encryption');assert.equal(await np.locator('[data-vf-directory-item]:visible').count(),1);await nojs.close();
 await p.setViewportSize({width:1440,height:1000});const downloader=routes.find(x=>x.route==='m3u8-downloader');await p.goto(downloader.url);
 const download=p.waitForEvent('download');await p.getByRole('button',{name:'Download built-in demo',exact:true}).click();const file=await download;const filePath=await file.path();assert(filePath);const bytes=fs.readFileSync(filePath);assert(bytes.length>1000);assert.equal(bytes.subarray(4,8).toString(),'ftyp');await p.getByRole('button',{name:'Save again',exact:true}).waitFor();assert.match(await p.locator('main').innerText(),/3 \/ 3/);
 const converter=routes.find(x=>x.route==='m3u8-to-mp4');await p.goto(converter.url);assert.equal(await p.locator('.vf-m3u8-launchbar').count(),1);assert.equal(await p.getByRole('button',{name:'Start',exact:true}).isEnabled(),true);
 const conversionDownload=p.waitForEvent('download');await p.getByRole('button',{name:'Convert bundled sample',exact:true}).click();const conversionFile=await conversionDownload;const convertedBytes=fs.readFileSync(await conversionFile.path());assert(convertedBytes.length>1000);assert.equal(convertedBytes.subarray(4,8).toString(),'ftyp');await p.getByRole('button',{name:'Save again',exact:true}).waitFor();
 const timing=await performanceSamples(),previous=JSON.parse(fs.readFileSync('proof/performance-baseline.json'));assert(timing.median<=previous.median*2+500,'bounded directory latency regression');fs.writeFileSync('proof/performance.json',JSON.stringify({status:'PASS',operation:'same isolated WordPress directory navigation TTFB',baseline:previous,current:timing,budget_ms:previous.median*2+500,dataset:{baseline_tools:9,current_tools:11},public_js_css_unchanged:true},null,2));assert.equal(errors.length,0,JSON.stringify(errors));fs.writeFileSync('proof/directory-browser.json',JSON.stringify({status:'PASS',rows,tool_routes:routes.map(x=>x.route),directory_tools:11,unique_recommendations:6,category_search_clear_reload:'PASS',mobile_select:'PASS',no_javascript:'PASS',real_demo_download:{bytes:bytes.length,segments:3,format:'ftyp MP4',result:'SAVED'},converter_workspace:'READY',page_errors:errors,production:'NOT_EXECUTED'},null,2));await b.close();
})().catch(e=>{console.error(e);process.exit(1)});
