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
    const targets=[...document.querySelectorAll('.vf-directory-filter-group button,.vf-glossary-letter-index button,.vf-directory-reset,.vf-support-hero-actions a')].filter(visible).map(n=>{
     const r=n.getBoundingClientRect(),s=getComputedStyle(n),rules=[];
     const walk=rs=>{for(const rule of rs){if(rule.selectorText){try{if(n.matches(rule.selectorText)&&/min-height|min-width|height:|width:/.test(rule.style.cssText))rules.push(rule.cssText.slice(0,420));}catch{}}else if(rule.cssRules)walk(rule.cssRules);}};
     if(r.height<43.99||r.width<43.99)for(const sheet of document.styleSheets){try{walk(sheet.cssRules);}catch{}}
     return {text:n.textContent.trim(),class:n.className,parent:n.parentNode.className,ancestor:n.closest('[class*="vf-theme-post-list"]')?.className,width:r.width,height:r.height,minHeight:s.minHeight,minWidth:s.minWidth,rules:rules.slice(-12)};
    });
    return {targets,probe:vfToolSiteRunBrowserProbe().checks['responsive-touch-targets'],overflow:Math.max(document.body.scrollWidth,document.documentElement.scrollWidth)>innerWidth+1};
   });
   rows.push({width,path,...result});save();assert(result.targets.length>0,`missing controls ${path}`);assert(!result.overflow,`overflow ${path} ${width}`);
   for(const n of result.targets)assert(n.width>=43.99&&n.height>=43.99,`undersized ${path} ${width}: ${n.text} ${n.width}x${n.height}`);
   if(width<=768)assert.equal(result.probe.status,'PASS',`actual touch probe ${path} ${width}`);
   if([768,390].includes(width)&&['/guides/','/problems/','/glossary/'].includes(path)){
    const category=page.locator('.vf-directory-filter-group button[data-vf-directory-filter-button]:not([data-vf-directory-filter-button="all"])').first();
    if(await category.isVisible()){
     const value=await category.getAttribute('data-vf-directory-filter-button');await category.focus();await category.press('Enter');
     await page.waitForFunction(v=>new URL(location.href).searchParams.get('vf_filter')===v||document.querySelector('.vf-directory-filter-group button[data-vf-directory-filter-button="'+v+'"]')?.getAttribute('aria-pressed')==='true',value);
     const reset=page.locator('[data-vf-directory-reset]').first();await reset.waitFor({state:'visible'});const size=await reset.boundingBox();assert(size.width>=43.99&&size.height>=43.99);await reset.click();
     await page.waitForFunction(()=>!new URL(location.href).searchParams.has('vf_filter')&&document.querySelector('.vf-directory-filter-group button[data-vf-directory-filter-button="all"]')?.getAttribute('aria-pressed')==='true');
     actions.push({width,path,category:value,keyboard:'PASS',reset:'PASS'});save();
    }
    await page.goto(url(path));
    if(path==='/glossary/'){
     const letter=page.locator('.vf-glossary-letter-index button:not([data-vf-directory-filter-button="all"])').first();assert(await letter.isVisible());const value=await letter.getAttribute('data-vf-directory-filter-button');await letter.click();
     await page.waitForFunction(v=>new URL(location.href).searchParams.get('vf_letter')===v||document.querySelector('.vf-glossary-letter-index button[data-vf-directory-filter-button="'+v+'"]')?.getAttribute('aria-pressed')==='true',value);
     actions.push({width,path,letter:value,click:'PASS'});save();
    }
   }
   if(width===390)await page.screenshot({path:'proof/touch-'+path.split('/').filter(Boolean)[0]+'-390.png',fullPage:true});
  }
 }
 assert.equal(rows.length,30);assert(actions.some(x=>x.letter));
 fs.writeFileSync('proof/touch-regression.json',JSON.stringify({status:'PASS',rows,actions,production:'NOT_EXECUTED',owner_acceptance:'NOT_CLAIMED'},null,2));await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
