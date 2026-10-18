'use strict';
const fs=require('fs'),{chromium}=require('playwright');
const cases=JSON.parse(fs.readFileSync('proof/cases.json','utf8')).cases;
(async()=>{
const browser=await chromium.launch({headless:true});
const checks=[];
try{
const page=await browser.newPage();
for(const lang of ['en','zh'])for(const width of [1440,1024]){
await page.setViewportSize({width,height:950});
for(const family of ['home','tool_hub','blog_index','guide_index','problem_index','faq_page','about_page','contact_page','legal','search','not_found']){
const response=await page.goto(cases[lang][family]);await page.waitForLoadState('networkidle');
const metrics=await page.evaluate(()=>{
const header=document.querySelector('header[data-vf-frontend-design]');
const footer=document.querySelector('footer[data-vf-frontend-design]');
const main=document.querySelector('main');
return {header:!!header,footer:!!footer,main:!!main,h1:main?.querySelectorAll('h1').length||0,overflow:document.documentElement.scrollWidth>innerWidth+1,brokenImages:[...document.querySelectorAll('main img')].filter(x=>!x.complete||x.naturalWidth===0).length};
});
const pass=!!response&&[200,404].includes(response.status())&&metrics.header&&metrics.footer&&metrics.main&&metrics.h1===1&&!metrics.overflow&&metrics.brokenImages===0;
checks.push({lang,width,family,pass,status:response?.status(),...metrics});
}
}
const ok=checks.every(x=>x.pass);
fs.writeFileSync('proof/r11-shared-shell.json',JSON.stringify({status:ok?'PASS':'FAIL',scope:'ISOLATED_DESKTOP',checks,mobile:'DEFERRED'},null,2));
if(!ok)throw Error('R11 failed '+JSON.stringify(checks.filter(x=>!x.pass)));
console.log('R11 shared header/footer and geometry '+checks.length+'/'+checks.length+' PASS');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
