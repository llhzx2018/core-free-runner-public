'use strict';
const fs=require('fs'),assert=require('assert/strict'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true}),context=await browser.newContext(),page=await context.newPage(),base='http://127.0.0.1:18880';
 await page.goto(base+'/wp-login.php');await page.locator('#user_login').fill('admin');await page.locator('#user_pass').fill('Synthetic-Only-Update-54!');await Promise.all([page.waitForURL(/wp-admin/),page.locator('#wp-submit').click()]);
 await page.goto(base+'/wp-admin/themes.php?page=vf-theme-modules&tab=preview');const nonce=await page.evaluate(()=>VFThemePreview.probeNonce);assert(nonce);
 const url=path=>base+path+'?vf_probe=1&vf_probe_nonce='+encodeURIComponent(nonce),rows=[],actions=[];
 fs.mkdirSync('proof',{recursive:true});
 const save=()=>fs.writeFileSync('proof/touch-progress.json',JSON.stringify({rows,actions},null,2));
 for(const width of [1920,1440,1319,1024,768,390]){
  await page.setViewportSize({width,height:1000});
  for(const path of ['/guides/','/problems/','/glossary/','/about/','/contact/']){
   await page.goto(url(path));await page.evaluate(()=>document.fonts.ready);await page.waitForFunction(()=>typeof vfToolSiteRunBrowserProbe==='function');
   const result=await page.evaluate(()=>{
    const visible=n=>{const r=n.getBoundingClientRect(),s=getComputedStyle(n);return r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden'&&!n.hidden;};
    const targets=[...document.querySelectorAll('.vf-directory-filter-group button,.vf-directory-filter-select select,.vf-glossary-letter-index button,.vf-directory-reset,.vf-support-hero-actions a')].filter(visible).map(n=>{
     const r=n.getBoundingClientRect(),s=getComputedStyle(n),rules=[];
     const walk=rs=>{for(const rule of rs){if(rule.selectorText){try{if(n.matches(rule.selectorText)&&/min-height|min-width|height:|width:/.test(rule.style.cssText))rules.push(rule.cssText.slice(0,420));}catch{}}else if(rule.cssRules)walk(rule.cssRules);}};
     if(r.height<43.99||r.width<43.99)for(const sheet of document.styleSheets){try{walk(sheet.cssRules);}catch{}}
     return {text:n.textContent.trim(),class:n.className,parent:n.parentNode.className,ancestor:n.closest('[class*="vf-theme-post-list"]')?.className,width:r.width,height:r.height,minHeight:s.minHeight,minWidth:s.minWidth,rules:rules.slice(-12)};
    });
    const critical=[...document.querySelectorAll('a.vf-data-btn,.vf-menu-toggle,.vf-mobile-nav-close,.vf-directory-filter-group button,.vf-theme-system-search-box button,.vf-production-footer-col .vf-footer-link,.vf-footer-section-toggle,.vf-footer-partner-link,.vf-footer-legal a,.vf-footer-back-to-top')].filter(visible).map(n=>({tag:n.tagName,text:n.textContent.trim(),cls:n.className,parent:n.parentNode.className,width:n.getBoundingClientRect().width,height:n.getBoundingClientRect().height,minHeight:getComputedStyle(n).minHeight}));return {targets,critical,probe:vfToolSiteRunBrowserProbe().checks['responsive-touch-targets'],overflow:Math.max(document.body.scrollWidth,document.documentElement.scrollWidth)>innerWidth+1};
   });
   rows.push({width,path,...result});save();assert(result.targets.length>0,`missing controls ${path}`);assert(!result.overflow,`overflow ${path} ${width}`);
   for(const n of result.targets)assert(n.width>=43.99&&n.height>=43.99,`undersized ${path} ${width}: ${n.text} ${n.width}x${n.height}`);
   if(width<=768)assert.equal(result.probe.status,'PASS',`actual touch probe ${path} ${width}`);
   if([768,390].includes(width)&&['/guides/','/problems/','/glossary/'].includes(path)){
    const category=page.locator('.vf-directory-filter-group button[data-vf-directory-filter-button]:not([data-vf-directory-filter-button="all"])').first();
    if(await category.isVisible()){
     const value=await category.getAttribute('data-vf-directory-filter-button');await category.focus();await category.press('Enter');
     await page.waitForURL(u=>u.searchParams.get('vf_filter')===value);await page.waitForLoadState('load');assert.equal(await page.locator('.vf-directory-filter-group button[data-vf-directory-filter-button="'+value+'"]').getAttribute('aria-pressed'),'true');
     const reset=page.locator('[data-vf-directory-reset]').first();await reset.waitFor({state:'visible'});const size=await reset.boundingBox();assert(size.width>=43.99&&size.height>=43.99);await reset.click();
     await page.waitForFunction(()=>!new URL(location.href).searchParams.has('vf_filter')&&document.querySelector('.vf-directory-filter-group button[data-vf-directory-filter-button="all"]')?.getAttribute('aria-pressed')==='true');
     actions.push({width,path,category:value,keyboard:'PASS',reset:'PASS'});save();
    }else{
     const select=page.locator('.vf-directory-filter-select select').first();assert(await select.isVisible(),'mobile filter select missing');
     const value=await select.locator('option:not([value="all"])').first().getAttribute('value');await select.selectOption(value);
     await page.waitForURL(u=>u.searchParams.get('vf_filter')===value);await page.waitForLoadState('load');assert.equal(await select.inputValue(),value);
     const reset=page.locator('[data-vf-directory-reset]').first();await reset.waitFor({state:'visible'});const size=await reset.boundingBox();assert(size.width>=43.99&&size.height>=43.99);await reset.click();
     await page.waitForURL(u=>!u.searchParams.has('vf_filter'));await page.waitForLoadState('load');assert.equal(await select.inputValue(),'all');
     actions.push({width,path,category:value,select:'PASS',reset:'PASS'});save();
    }
    await page.goto(url(path));
    if(path==='/glossary/'){
     const letter=page.locator('.vf-glossary-letter-index button:not([data-vf-directory-filter-button="all"])').first();assert(await letter.isVisible());const value=await letter.getAttribute('data-vf-directory-filter-button');await letter.click();
     await page.waitForURL(u=>u.searchParams.get('vf_letter')===value);await page.waitForLoadState('load');assert.equal(await page.locator('.vf-glossary-letter-index button[data-vf-directory-filter-button="'+value+'"]').getAttribute('aria-pressed'),'true');
     actions.push({width,path,letter:value,click:'PASS'});save();
    }
   }
   if(width===390)await page.screenshot({path:'proof/touch-'+path.split('/').filter(Boolean)[0]+'-390.png',fullPage:true});
  }
 }
 assert.equal(rows.length,30);assert(actions.some(x=>x.letter));
 const directoryStates=[],fixturePage=await context.newPage();
 for(const populated of [false,true]){
  const items=populated?'<article data-vf-directory-item data-vf-directory-category="start" data-vf-directory-letter="a" data-vf-directory-search="Alpha"></article><article data-vf-directory-item data-vf-directory-category="inspect" data-vf-directory-letter="b" data-vf-directory-search="Beta"></article>':'';
  await fixturePage.setContent('<html lang="en"><body><section data-vf-directory-filter data-vf-directory-context="guide_index"><input data-vf-directory-query><div><button data-vf-directory-filter-button="all" aria-pressed="true" class="is-active">All</button><button data-vf-directory-filter-button="start" aria-pressed="false">Start</button></div><button data-vf-directory-filter-dimension="letter" data-vf-directory-filter-button="all" aria-pressed="true" class="is-active">All letters</button><button data-vf-directory-filter-dimension="letter" data-vf-directory-filter-button="a" aria-pressed="false">A</button><select data-vf-directory-filter-select="category"><option value="all">All</option><option value="start">Start</option></select><button data-vf-directory-reset hidden>Reset</button><span data-vf-directory-count></span><span data-vf-directory-active-summary></span><div data-vf-directory-empty hidden>Empty</div>'+items+'</section></body></html>');
  await fixturePage.addScriptTag({content:fs.readFileSync('target/src/assets/js/main.js','utf8')});await fixturePage.evaluate(()=>document.dispatchEvent(new Event('DOMContentLoaded')));
  const root=fixturePage.locator('[data-vf-directory-filter]'),start=root.locator('button[data-vf-directory-filter-button="start"]'),reset=root.locator('[data-vf-directory-reset]'),query=root.locator('[data-vf-directory-query]');
  assert.equal(await root.getAttribute('data-vf-directory-matched'),populated?'2':'0');
  await start.focus();await start.press('Enter');assert.equal(await start.getAttribute('aria-pressed'),'true');assert.equal(await root.getAttribute('data-vf-directory-matched'),populated?'1':'0');assert(await reset.isVisible());
  await reset.click();assert.equal(await start.getAttribute('aria-pressed'),'false');assert.equal(await reset.isVisible(),false);
  await root.locator('select').selectOption('start');assert.equal(await start.getAttribute('aria-pressed'),'true');await reset.click();
  await root.locator('button[data-vf-directory-filter-button="a"]').click();assert.equal(await root.getAttribute('data-vf-directory-matched'),populated?'1':'0');await reset.click();
  await query.fill('Beta');assert.equal(await root.getAttribute('data-vf-directory-matched'),populated?'1':'0');assert(await reset.isVisible());await query.press('Escape');assert.equal(await query.inputValue(),'');assert.equal(await root.getAttribute('data-vf-directory-matched'),populated?'2':'0');assert.equal(await reset.isVisible(),false);
  directoryStates.push({populated,keyboard_category:'PASS',select:'PASS',letter:'PASS',reset:'PASS',search_escape:'PASS',matched_count:'PASS'});
 }
 fs.writeFileSync('proof/directory-state-regression.json',JSON.stringify({status:'PASS',cases:directoryStates},null,2));
 fs.writeFileSync('proof/touch-regression.json',JSON.stringify({status:'PASS',rows,actions,production:'NOT_EXECUTED',owner_acceptance:'NOT_CLAIMED'},null,2));await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
