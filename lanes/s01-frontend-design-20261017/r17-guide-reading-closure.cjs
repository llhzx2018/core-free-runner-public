'use strict';
const fs=require('node:fs'),{chromium}=require('playwright');
const cases=JSON.parse(fs.readFileSync('proof/cases.json','utf8')).cases;
(async()=>{
 const browser=await chromium.launch({headless:true});
 const checks=[];
 try{
  const page=await browser.newPage({viewport:{width:1440,height:900}});
  for(const lang of ['en','zh'])for(const width of [1440,1024]){
   await page.setViewportSize({width,height:900});
   const response=await page.goto(cases[lang].guide_detail,{waitUntil:'networkidle'});
   const v=await page.evaluate(()=>{
    const el=document.querySelector('.vf-reading-toc nav'),css=el?getComputedStyle(el):null;
    const authored=[...document.querySelectorAll('.vf-reading-article h2')].map(n=>n.textContent.trim());
    const actual=[...document.querySelectorAll('.vf-reading-toc a[href^="#"]')].map(n=>n.getAttribute('href'));
    const relatedTools=document.querySelectorAll('.vf-reading-related-tools a[href]').length;
    const genericCta=[...document.querySelectorAll('.vf-theme-module-frame--cta a[href]')].filter(a=>new URL(a.href).pathname==='/tools/').length;
    return {h1:document.querySelectorAll('main h1').length,authorFAQ:authored.some(x=>/^(FAQ|常见问题)$/.test(x)),authorWorkflow:authored.some(x=>/^(Recommended workflow|建议检查顺序)$/.test(x)),
      tocLinks:actual.length,badTOC:actual.filter(h=>!document.getElementById(decodeURIComponent(h.slice(1)))),
      tocOverflow:css?.overflowY||null,tocMaxHeight:css?.maxHeight||null,
      duplicateFAQ:document.querySelectorAll('.vf-reading-faq-section,.vf-theme-module-frame--faq').length,
      duplicateSteps:document.querySelectorAll('.vf-theme-module-frame--steps,.vf-guide-step-navigation').length,
      relatedTools,relatedGuides:document.querySelectorAll('.vf-reading-related-posts a[href]').length,
      genericCta,ctaTotal:document.querySelectorAll('.vf-theme-module-frame--cta').length,
      articleNav:document.querySelectorAll('.vf-reading-post-navigation a[href]').length,
      titleCount:document.querySelectorAll('title').length,canonical:document.querySelectorAll('link[rel="canonical"]').length,
      horizontalOverflow:document.documentElement.scrollWidth>innerWidth+1};
   });
   const pass=response.status()===200&&v.h1===1&&v.authorFAQ&&v.authorWorkflow&&v.tocLinks>=4&&v.badTOC.length===0&&v.tocOverflow==='visible'&&v.tocMaxHeight==='none'
     &&v.duplicateFAQ===0&&v.duplicateSteps===0&&v.genericCta===0&&v.articleNav>=1&&v.titleCount===1&&v.canonical<=1&&!v.horizontalOverflow;
   const item={lang,width,status:response.status(),pass,...v};
   checks.push(item);
   if(!pass)throw Error('GUIDE_READING_139_FAIL '+JSON.stringify(item));
   await page.locator('.vf-reading-toc a[href^="#"]').first().click();
   if(!new URL(page.url()).hash)throw Error('Guide TOC activation failed '+lang+' '+width);
  }
  fs.writeFileSync('proof/guide-reading-v135139.json',JSON.stringify({status:'PASS',checks,source:'SYNTHETIC_WORDPRESS_MARIADB_CHROMIUM',mobile:'DEFERRED'},null,2));
  console.log('GUIDE_READING_139_DESKTOP_PASS='+checks.length+'/'+checks.length);
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
