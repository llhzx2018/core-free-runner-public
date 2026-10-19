'use strict';
const fs=require('node:fs'), {chromium}=require('playwright');
const cases=JSON.parse(fs.readFileSync('proof/cases.json','utf8')).cases;
(async()=>{
 const browser=await chromium.launch({headless:true}), checks=[];
 try{
  const page=await browser.newPage({viewport:{width:1440,height:900},deviceScaleFactor:1});
  for(const lang of ['en','zh'])for(const width of [1440,1024]){
   await page.setViewportSize({width,height:900});
   const r=await page.goto(cases[lang].tool_hub,{waitUntil:'networkidle'});
   if(r.status()!==200)throw Error(lang+' '+width+' tools not HTTP 200');
   const state=await page.evaluate(()=>{
     const size=s=>{const x=document.querySelector(s);return x?parseFloat(getComputedStyle(x).fontSize):null;};
     const cards=[...document.querySelectorAll('.vf-directory-tool-card')];
     return {
       total:cards.length,h1:document.querySelectorAll('main h1').length,
       cardTitle:size('.vf-directory-tool-card h4'),
       cardCopy:size('.vf-directory-card-purpose'),
       intro:size('.vf-directory-section-head p'),
       groupCopy:size('.vf-directory-task-group-head p'),
       cardDisclosure:size('.vf-directory-card-details>summary'),
       cardsWithActions:cards.filter(c=>{const a=c.querySelector('.vf-directory-card-action');return a && !!a.href && new URL(a.href).origin===location.origin}).length,
       groups:document.querySelectorAll('[data-vf-directory-group]').length,
       overflow:document.documentElement.scrollWidth>innerWidth+1,
       metaDescription:document.querySelector('meta[name="description"]')?.content||'',
       title:document.title
     };
   });
   if(state.total!==11||state.cardsWithActions!==11||state.groups!==4||state.h1!==1||state.overflow)throw Error(lang+' '+width+' directory geometry/links '+JSON.stringify(state));
   if(state.cardTitle!==19||state.cardCopy!==16||state.intro!==16||state.groupCopy!==16||state.cardDisclosure!==15)throw Error(lang+' '+width+' typography '+JSON.stringify(state));
   if(!state.title)throw Error(lang+' no SEO title');
   const count=page.locator('.vf-directory-tool-card:visible');
   const search=page.locator('[data-vf-directory-query]').first();
   await search.fill('zz-404-no-such-tool');await page.waitForTimeout(70);
   if(await count.count()!==0||!await page.locator('[data-vf-directory-empty]').first().isVisible())throw Error(lang+' search empty state');
   const reset=page.locator('[data-vf-directory-reset]').first();
   if(await reset.isVisible())await reset.click();else await search.fill('');
   if(await count.count()!==11)throw Error(lang+' clear search fails');
   const specific=page.locator('[data-vf-directory-filter-button]:not([data-vf-directory-filter-button="all"])').first();
   if(await specific.count()){
     const key=await specific.getAttribute('data-vf-directory-filter-button');
     await specific.click();await page.waitForTimeout(70);
     const visible=await count.count();
     const allMatched=await page.locator('.vf-directory-tool-card:visible').evaluateAll((nodes,k)=>nodes.every(n=>n.getAttribute('data-vf-directory-category')===k),key);
     if(visible<1||visible>=11||!allMatched)throw Error(lang+' category filter '+key+' '+visible);
     await page.locator('[data-vf-directory-filter-button="all"]').first().click();await page.waitForTimeout(70);
     if(await count.count()!==11)throw Error(lang+' All filter restore failed');
   }
   checks.push({lang,width,...state,clientSearch:'PASS',categoryFilter:'PASS',restored:await count.count()});
  }
  console.log('S01_C01_TOOL_DIRECTORY_BROWSER=PASS '+JSON.stringify(checks));
 }finally{await browser.close()}
})().catch(err=>{console.error(err);process.exit(1)});
