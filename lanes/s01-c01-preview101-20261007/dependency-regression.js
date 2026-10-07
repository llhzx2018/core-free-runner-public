'use strict';
const fs=require('fs'),assert=require('assert/strict'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true}),context=await browser.newContext({acceptDownloads:true}),page=await context.newPage(),base='http://127.0.0.1:18880',url=base+'/wp-admin/themes.php?page=vf-theme-modules&tab=preview';
 await page.goto(base+'/wp-login.php');await page.locator('#user_login').fill('admin');await page.locator('#user_pass').fill('Synthetic-Only-Update-54!');await Promise.all([page.waitForURL(/wp-admin/),page.locator('#wp-submit').click()]);
 await page.goto(url);const nonce=await page.evaluate(()=>VFThemePreview.probeNonce);const routes=[],headProof=JSON.parse(fs.readFileSync('proof/dependency-head-proof.json','utf8'));assert.equal(headProof.rows.length,4);for(const r of headProof.rows){assert.equal(r.http,200);assert.equal(new URL(r.resolved_url).pathname,r.route);assert.equal(r.issues.length,0,JSON.stringify(r.issues));}
 for(const route of ['/m3u8-player/','/guides/how-to-check-if-m3u8-is-encrypted/','/problems/m3u8-403-forbidden-fix/','/tool-notes/m3u8-player/']){
  const response=await page.goto(base+route+'?vf_probe=1&vf_probe_nonce='+encodeURIComponent(nonce));await page.waitForFunction(()=>typeof vfToolSiteRunBrowserProbe==='function');
  const head=await page.evaluate(()=>({path:location.pathname,error404:document.body.classList.contains('error404'),title:document.title,canonical:[...document.querySelectorAll('link[rel="canonical"]')].map(n=>n.href),robots:[...document.querySelectorAll('meta[name="robots"]')].map(n=>n.content),hreflang:[...document.querySelectorAll('link[rel="alternate"][hreflang]')].map(n=>({lang:n.hreflang,url:n.href})),container:vfToolSiteRunBrowserProbe().checks['m3u8-tool-container-width-contract'],toolControls:[...document.querySelectorAll('.vf-container-tool input,.vf-container-tool button,.vf-container-tool select')].map(n=>({tag:n.tagName,type:n.type,id:n.id,role:n.getAttribute('role'),label:n.getAttribute('aria-label'),text:(n.textContent||'').trim().slice(0,80)}))}));
  routes.push({route,http:response.status(),...head});fs.writeFileSync('proof/dependency-routes-progress.json',JSON.stringify(routes,null,2));assert.equal(response.status(),200,route);assert(!head.error404);assert.equal(head.canonical.length,1,route);assert.equal(new URL(head.canonical[0]).pathname,route);assert(head.title);assert(!head.robots.join(',').includes('noindex'));const expected=Object.fromEntries(Object.entries(headProof.rows.find(n=>n.route===route).expected.hreflang));assert.deepEqual(Object.fromEntries(head.hreflang.map(n=>[n.lang,n.url])),expected);
  if(route==='/m3u8-player/'){
   assert.equal(head.container.status,'PASS');assert(head.toolControls.length>0,'actual Provider controls absent');
   const contrast=await page.evaluate(()=>{const nodes=[...document.querySelectorAll('.vf-container-tool')],saved=nodes.map(n=>n.className);nodes.forEach(n=>n.classList.remove('vf-container-tool'));const bad=vfToolSiteRunBrowserProbe().checks['m3u8-tool-container-width-contract'];nodes.forEach((n,i)=>n.className=saved[i]);const restored=vfToolSiteRunBrowserProbe().checks['m3u8-tool-container-width-contract'];return {container_count:nodes.length,bad,restored};});assert.equal(contrast.bad.status,'FAIL');assert.equal(contrast.restored.status,'PASS');routes[routes.length-1].contrast=contrast;
   const ownershipContrast=await page.evaluate(()=>{const shell=document.querySelector('.vf-theme-tool-shortcode'),n=document.createElement('input');shell.appendChild(n);const bad=vfToolSiteRunBrowserProbe().checks['theme-tool-shell-has-no-runtime-controls'];n.remove();const restored=vfToolSiteRunBrowserProbe().checks['theme-tool-shell-has-no-runtime-controls'];return {bad,restored};});assert.equal(ownershipContrast.bad.status,'FAIL');assert.equal(ownershipContrast.restored.status,'PASS');routes[routes.length-1].ownershipContrast=ownershipContrast;
   const stage=page.locator('.vf-theme-tool-shortcode > .vf-container-tool'),input=stage.locator('input[type="url"]').first();
   await input.fill('https://example.invalid/isolated-owned-input.m3u8');
   await stage.getByRole('button',{name:'Clear',exact:true}).click();assert.equal(await input.inputValue(),'','Provider clear did not reset URL input');
   await stage.locator('button').filter({hasText:/^Pro$/}).click();
   const advanced=stage.getByRole('button',{name:'Expand professional options',exact:true});if(await advanced.isVisible())await advanced.click();
   const select=stage.locator('select:visible').first();assert(await select.isVisible(),'real Provider dropdown unavailable');
   const values=await select.locator('option').evaluateAll(ns=>ns.map(n=>n.value));assert(values.length>=2);await select.selectOption(values[1]);assert.equal(await select.inputValue(),values[1]);
   await stage.locator('button').filter({hasText:/^Simple$/}).click();
   routes[routes.length-1].interactions={url_input:'PASS',clear:'PASS',pro_mode:'PASS',dropdown:'PASS',simple_mode:'PASS',external_media_requests:'NOT_EXECUTED'};

  }
 }
 for(const width of [1440,768,390]){await page.setViewportSize({width,height:1000});await page.goto(base+'/m3u8-player/');await page.evaluate(()=>document.fonts.ready);assert(await page.locator('.vf-theme-tool-shortcode > .vf-container-tool').isVisible());const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+4);assert(!overflow);await page.screenshot({path:'proof/provider-player-'+width+'.png',fullPage:true});}
 await page.goto(url);const root=page.locator('[data-vf-preview-page]');await root.locator('[data-vf-preview-mode]').selectOption('live_roundtrip');await root.locator('[data-vf-preview-run]').click();await page.waitForFunction(()=>document.querySelector('[data-vf-preview-page]').getAttribute('aria-busy')==='false',{},{timeout:480000});
 const [download]=await Promise.all([page.waitForEvent('download'),root.locator('[data-vf-preview-download]').click()]);const artifact=JSON.parse(fs.readFileSync(await download.path(),'utf8'));assert.equal(artifact.mode,'live_roundtrip');
 // Keep the engine's real verdict and every remaining issue; availability
 // checks below are bounded to the actual dependency/content setup above.
 fs.writeFileSync('proof/dependency-engine-full.json',JSON.stringify(artifact,null,2));
 const focused=artifact.issues.filter(n=>routes.some(r=>(n.path||'').split('?')[0]===base+r.route));
 const providerIssues=artifact.issues.filter(n=>n.path===base+'/m3u8-player/' && ((n.category==='structure' && n.current==='实际 2 个') || (n.category==='uaui' && n.problem.includes('小触控目标'))));
 const themeIssues=artifact.issues.filter(n=>!providerIssues.includes(n));
 const result={status:themeIssues.length===0?'PASS':'FAIL',meaning:'BOUNDED_THEME_AND_ACTUAL_DEPENDENCY_PROOF_PROVIDER_DEFECTS_PRESERVED_NOT_OWNER_PRODUCT_PASS',provider_issues:providerIssues,theme_issues:themeIssues,head_contract:'UNPAIRED_PUBLISHED_OBJECTS_EMIT_NO_HREFLANG',headProof,routes,runId:artifact.runId,engine_status:artifact.status,issue_count:artifact.issues.length,issues:artifact.issues,focused_issues:focused,rows:artifact.rows.length,production:'NOT_EXECUTED'};
 fs.writeFileSync('proof/dependency-regression.json',JSON.stringify(result,null,2));console.log('VF_DEPENDENCY_RESULT_BEGIN');console.log(JSON.stringify({status:result.status,issue_count:result.issue_count,theme_issues:result.theme_issues,provider_issues:result.provider_issues}));console.log('VF_DEPENDENCY_RESULT_END');assert.equal(themeIssues.length,0,'Theme-owned or unclassified issues remain with dependencies installed');
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
