'use strict';
const fs=require('node:fs');
const {chromium}=require('playwright');
const cases=JSON.parse(fs.readFileSync('proof/cases.json','utf8')).cases;
(async()=>{
 const browser=await chromium.launch({headless:true});
 const checked=[];
 try{
  const page=await browser.newPage({viewport:{width:1440,height:900},deviceScaleFactor:1});
  for(const lang of ['en','zh']){
   const base=cases[lang].guide_index;
   for(const width of [1440,1024]){
    await page.setViewportSize({width,height:900});
    const res=await page.goto(base,{waitUntil:'networkidle'});
    if(res.status()!==200)throw Error(lang+' guide index status');
    const facts=await page.evaluate(()=>{
      const rows=[...document.querySelectorAll('.vf-theme-post-list--guide_index .vf-directory-card')];
      const style=(selector)=>{const el=document.querySelector(selector);return el?parseFloat(getComputedStyle(el).fontSize):null;};
      return {count:rows.length,ids:rows.map(el=>el.getAttribute('data-vf-directory-category')),h1:document.querySelectorAll('main h1').length,title:document.title,
        cardCopy:style('.vf-theme-post-list--guide_index .vf-directory-card p'),search:style('.vf-theme-post-list--guide_index .vf-directory-search input'),
        links:rows.filter(el=>!!el.querySelector('a[href]')).length,
        overflow:document.documentElement.scrollWidth>innerWidth+1,
        pager:document.querySelectorAll('.vf-theme-post-list--guide_index .vf-theme-pagination--internal .next').length};
    });
    if(facts.count<9||facts.links!==facts.count||facts.h1!==1||facts.overflow||!facts.title||facts.pager!==1)throw Error(lang+' '+width+' list semantics '+JSON.stringify(facts));
    if(facts.cardCopy!==16||facts.search!==16)throw Error(lang+' '+width+' reading size '+JSON.stringify(facts));
    checked.push({lang,width,...facts});
   }
   await page.goto(base+'?vf_q=Beyondguide',{waitUntil:'networkidle'});
   let ids=await page.locator('.vf-theme-post-list--guide_index .vf-directory-card:visible').count();
   if(ids!==1)throw Error(lang+' cross-page keyword Beyondguide expected one guide, got '+ids);
   await page.goto(base+'?vf_q=never-exists-908170',{waitUntil:'networkidle'});
   ids=await page.locator('.vf-theme-post-list--guide_index .vf-directory-card:visible').count();
   if(ids!==0 || !await page.locator('.vf-theme-post-list--guide_index [data-vf-directory-empty]').first().isVisible())throw Error(lang+' no-results incorrect');
   for(const type of ['start','inspect','play']){
    await page.goto(base+'?vf_filter='+type,{waitUntil:'networkidle'});
    const rows=page.locator('.vf-theme-post-list--guide_index .vf-directory-card:visible');
    const cnt=await rows.count();
    if(cnt<1)throw Error(lang+' task filter '+type+' produced empty despite fixture');
    if(!await rows.evaluateAll((es,v)=>es.every(el=>el.getAttribute('data-vf-directory-category')===v),type))throw Error(lang+' task '+type+' mixed categories');
   }
   await page.goto(base,{waitUntil:'networkidle'});
   const next=page.locator('.vf-theme-post-list--guide_index .vf-theme-pagination--internal .next').first();
   if(!await next.count())throw Error(lang+' missing page2');
   await next.click();await page.waitForLoadState('networkidle');
   const page2=await page.locator('.vf-theme-post-list--guide_index .vf-directory-card:visible').count();
   if(page2<1)throw Error(lang+' page2 no guides');
   checked.push({lang,serverFilter:'PASS',crossPageSearch:'PASS',emptyState:'PASS',paginationPage2:page2});
  }
  console.log('GUIDES_DIRECTORY_EN_ZH_READING_FILTER_SEARCH_PAGINATION=PASS '+JSON.stringify(checked));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
