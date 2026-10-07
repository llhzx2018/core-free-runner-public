'use strict';
const fs=require('fs'),assert=require('assert/strict'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true}),anon=await browser.newContext(),context=await browser.newContext(),page=await context.newPage(),base='http://127.0.0.1:18880';
 const publicResponse=await anon.request.get(base+'/?vf_public_links_proof=1'),publicBody=await publicResponse.json();assert.equal(publicResponse.status(),200);
 const fragment=await anon.newPage();await fragment.setContent(publicBody.filtered);
 const links=await fragment.locator('a[href]').evaluateAll(ns=>ns.map(n=>n.getAttribute('href')));
 assert.deepEqual(links,['/tools/?q=one&sort=title#list','https://example.org/guide?x=1&y=2','#section','mailto:reader@example.invalid']);
 assert((await fragment.textContent('body')).includes('Dashboard'));assert(publicBody.source.includes('/wp-admin/'));
 const feed=await (await anon.request.get(base+'/?vf_public_links_proof=1&feed=1')).json();assert.equal(feed.filtered,feed.source);assert.equal(feed.source_sha256,publicBody.source_sha256);
 await page.goto(base+'/wp-login.php');await page.locator('#user_login').fill('admin');await page.locator('#user_pass').fill('Synthetic-Only-Update-54!');await Promise.all([page.waitForURL(/wp-admin/),page.locator('#wp-submit').click()]);
 await page.goto(base+'/wp-admin/themes.php?page=vf-theme-modules&tab=preview');const nonce=await page.evaluate(()=>VFThemePreview.probeNonce);assert(nonce);
 const probe=route=>base+route+'?vf_probe=1&vf_probe_nonce='+encodeURIComponent(nonce);
 const missing=await page.goto(probe('/m3u8-player/'));assert.equal(missing.status(),404);await page.waitForFunction(()=>typeof vfToolSiteRunBrowserProbe==='function');
 const unavailable=await page.evaluate(()=>({error404:document.body.classList.contains('error404'),container:vfToolSiteRunBrowserProbe().checks['m3u8-tool-container-width-contract']}));assert(unavailable.error404);assert.equal(unavailable.container.status,'N_A');
 fs.writeFileSync('proof/public-links-route-baseline.json',JSON.stringify({status:'PASS',links,private_targets_removed:5,source_preserved:true,feed_preserved:true,unavailable,production:'NOT_EXECUTED'},null,2));
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
