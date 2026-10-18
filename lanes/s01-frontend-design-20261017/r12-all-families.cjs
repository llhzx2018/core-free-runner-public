'use strict';
const fs=require('fs'),{chromium}=require('playwright');
const cases=JSON.parse(fs.readFileSync('proof/cases.json','utf8')).cases;
(async()=>{const browser=await chromium.launch({headless:true});const checks=[];
try{const page=await browser.newPage();for(const lang of ['en','zh'])for(const width of [1440,1024]){
await page.setViewportSize({width,height:900});
for(const [family,url] of Object.entries(cases[lang])){
const response=await page.goto(url);await page.waitForLoadState('networkidle');
const measure=await page.evaluate(()=>({h1:document.querySelectorAll('main h1').length,main:!!document.querySelector('main'),overflow:document.documentElement.scrollWidth>innerWidth+1,header:document.querySelectorAll('header[data-vf-frontend-design]').length,footer:document.querySelectorAll('footer[data-vf-frontend-design]').length}));
const expected=family==='not_found'?404:200;
const pass=response.status()===expected&&measure.h1===1&&measure.main&&!measure.overflow&&measure.header===1&&measure.footer===1;
checks.push({family,lang,width,pass,status:response.status(),...measure});
}}
const pass=checks.every(c=>c.pass);fs.writeFileSync('proof/r12-all-families.json',JSON.stringify({status:pass?'PASS':'FAIL',checks,mobile:'DEFERRED',production:'UNTOUCHED'},null,2));
if(!pass)throw Error('R12 failed: '+JSON.stringify(checks.filter(c=>!c.pass)));
console.log('R12 integrated family checks '+checks.length+'/'+checks.length+' PASS');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
