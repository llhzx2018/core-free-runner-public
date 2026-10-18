'use strict';
const fs=require('fs'),{chromium}=require('playwright');
const cases=JSON.parse(fs.readFileSync('proof/cases.json','utf8')).cases;
(async()=>{
 const browser=await chromium.launch({headless:true}),checks=[];
 try{
  const page=await browser.newPage();
  for(const lang of ['en','zh'])for(const width of [1440,1024]){
   await page.setViewportSize({width,height:900});
   for(const family of ['about_page','contact_page','basic_page','legal']){
    const url=cases[lang][family];
    if(!url)throw Error('Missing fixture '+lang+':'+family);
    const response=await page.goto(url);await page.waitForLoadState('networkidle');
    const observed=await page.evaluate(()=>{
     const main=document.querySelector('main');
     return {heading:main?.querySelectorAll('h1').length||0,overflow:document.documentElement.scrollWidth>innerWidth+1,visible:!!main};
    });
    const pass=response.status()===200&&observed.heading===1&&!observed.overflow&&observed.visible;
    checks.push({lang,width,family,pass,status:response.status(),...observed});
   }
  }
  const passed=checks.every(item=>item.pass);
  fs.writeFileSync('proof/r08-content-pages.json',JSON.stringify({status:passed?'PASS':'FAIL',checks,mobile:'DEFERRED',production:'UNTOUCHED'},null,2));
  if(!passed)throw Error('R08 page-family checks failed');
  process.stdout.write('R08 bilingual desktop content families: '+checks.length+'/'+checks.length+' PASS\n');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
