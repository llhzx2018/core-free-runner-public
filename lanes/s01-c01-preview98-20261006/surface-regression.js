'use strict';
const fs=require('fs'),assert=require('assert/strict'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true}),context=await browser.newContext(),page=await context.newPage(),base='http://127.0.0.1:18880';
 await page.goto(base+'/wp-login.php');await page.locator('#user_login').fill('admin');await page.locator('#user_pass').fill('Synthetic-Only-Update-54!');await Promise.all([page.waitForURL(/wp-admin/),page.locator('#wp-submit').click()]);
 await page.goto(base+'/wp-admin/themes.php?page=vf-theme-modules&tab=preview');const nonce=await page.evaluate(()=>VFThemePreview.probeNonce);assert(nonce);
 const url=path=>base+path+'?vf_probe=1&vf_probe_nonce='+encodeURIComponent(nonce);
 await page.goto(url('/'));await page.waitForFunction(()=>typeof vfToolSiteRunBrowserProbe==='function');
 const surface=await page.evaluate(()=>{
  const header=document.querySelector('.vf-site-header'),nav=document.querySelector('.vf-primary-nav .vf-nav-link.is-active');
  if(!header||!nav)throw Error('actual header or active navigation missing');
  const run=()=>{const c=vfToolSiteRunBrowserProbe().checks;return {header:c['mature-header-white-surface'],active:c['mature-active-nav-no-color-block']};};
  const restore=(n,s)=>s===null?n.removeAttribute('style'):n.setAttribute('style',s);
  const baseline=run(),saved=header.getAttribute('style');header.style.setProperty('background','#000','important');const black=run();restore(header,saved);
  const body=document.body,root=document.documentElement,bs=body.getAttribute('style'),rs=root.getAttribute('style');
  header.style.setProperty('background','transparent','important');body.style.setProperty('background','#000','important');root.style.setProperty('background','#000','important');const transparentBlack=run();restore(header,saved);restore(body,bs);restore(root,rs);
  const ns=nav.getAttribute('style');nav.style.setProperty('background','#ff00ff','important');const arbitrary=run();restore(nav,ns);
  return {baseline,black,transparentBlack,arbitrary};
 });
 assert.equal(surface.baseline.header.status,'PASS');assert.equal(surface.baseline.active.status,'PASS');assert.equal(surface.black.header.status,'FAIL');assert.equal(surface.transparentBlack.header.status,'FAIL');assert.equal(surface.arbitrary.active.status,'FAIL');
 const labels=[],layout=[];
 const selectors=['.vf-theme-system-query-chips>span','.vf-support-faq-list','.vf-directory-card-meta','.vf-reading-related-card','.vf-reading-entry>a','.vf-theme-empty-grid .vf-family-card','.vf-theme-sitemap-directory'];
 for(const width of [1440,768,390]){
  await page.setViewportSize({width,height:1000});await page.goto(url('/404.html'));await page.evaluate(()=>document.fonts.ready);
  const row=await page.evaluate(()=>{const label=document.querySelector('.vf-theme-recovery-search-step .vf-theme-system-query-chips>span'),step=document.querySelector('.vf-theme-recovery-search-step>div:not(.vf-theme-system-query-chips)>span');if(!label||!step)throw Error('recovery label or step missing');return {text:label.textContent.trim(),width:label.getBoundingClientRect().width,clientWidth:label.clientWidth,scrollWidth:label.scrollWidth,stepWidth:step.getBoundingClientRect().width};});
  assert(row.width>38,'keyword label still has the step circle width');assert(row.scrollWidth<=row.clientWidth+4,'keyword label overflows');assert.equal(Math.round(row.stepWidth),38,'step marker changed');labels.push({width,...row});
  for(const path of ['/faq/','/blog/','/guides/how-to-check-if-m3u8-is-encrypted/','/m3u8-encryption-explained/','/sample-page/','/sitemap/']){
   await page.goto(url(path));await page.evaluate(()=>document.fonts.ready);
   layout.push({width,path,elements:await page.evaluate(selectors=>selectors.flatMap(selector=>[...document.querySelectorAll(selector)].slice(0,3).map(n=>({selector,html:n.outerHTML.slice(0,1200),width:n.getBoundingClientRect().width,clientWidth:n.clientWidth,scrollWidth:n.scrollWidth,display:getComputedStyle(n).display,columns:getComputedStyle(n).gridTemplateColumns,children:[...n.children].slice(0,4).map(c=>({tag:c.tagName,cls:c.className,width:c.getBoundingClientRect().width,scrollWidth:c.scrollWidth,clientWidth:c.clientWidth}))}))),selectors)});
  }
 }
 fs.mkdirSync('proof',{recursive:true});fs.writeFileSync('proof/surface-regression.json',JSON.stringify({status:'PASS',surface,labels,layout,production:'NOT_EXECUTED'},null,2));await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
