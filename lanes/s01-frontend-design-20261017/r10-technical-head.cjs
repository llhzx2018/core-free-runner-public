'use strict';
const fs=require('fs'),{chromium}=require('playwright');
const cases=JSON.parse(fs.readFileSync('proof/cases.json','utf8')).cases;
(async()=>{
 const browser=await chromium.launch({headless:true}),checks=[];
 try{
  const page=await browser.newPage();
  for(const lang of ['en','zh']){
   for(const family of ['home','about_page','contact_page','basic_page','legal','search','not_found']){
    const response=await page.goto(cases[lang][family]);await page.waitForLoadState('networkidle');
    const observed=await page.evaluate(()=>({
     titles:document.querySelectorAll('title').length,
     canonical:document.querySelectorAll('link[rel="canonical"]').length,
     jsonld:[...document.querySelectorAll('script[type="application/ld+json"]')].every(e=>{try{JSON.parse(e.textContent);return true}catch{return false}}),
     robots:[...document.querySelectorAll('meta[name="robots"]')].map(e=>e.content).join(' ').toLowerCase(),
     alternates:[...document.querySelectorAll('link[rel="alternate"][hreflang]')].map(e=>e.getAttribute('hreflang'))
    }));
    const edge=family==='search'||family==='not_found';
    const pass=observed.titles===1&&observed.canonical<=1&&observed.jsonld&&(!edge||observed.robots.includes('noindex'));
    checks.push({lang,family,pass,status:response.status(),...observed});
   }
  }
  const pass=checks.every(x=>x.pass);
  fs.writeFileSync('proof/r10-technical-head.json',JSON.stringify({status:pass?'PASS':'FAIL',checks,scope:'ISOLATED_SYNTHETIC_NON_PRODUCTION',mobile:'DEFERRED'},null,2));
  if(!pass)throw Error('R10 technical head assertions failed: '+JSON.stringify(checks.filter(x=>!x.pass)));
  console.log('R10 bilingual technical SEO head '+checks.length+'/'+checks.length+' PASS');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
