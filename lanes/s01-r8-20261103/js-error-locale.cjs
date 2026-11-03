'use strict';
const {chromium}=require('playwright');
const cp=require('node:child_process');
const fs=require('node:fs');
const assert=require('node:assert/strict');
const base='http://127.0.0.1:18880/m3u8-playlist-checker/';
const result={source:'S01 R8 M3U8 #178 3ab0992fb4788b8b9d15d0e338040189b6fcdd8f',checks:[],origin:'isolated WordPress/MariaDB only'};
function setLocale(locale){
  cp.execFileSync('php',['/tmp/wp-cli-r8.phar','option','update','WPLANG',locale,'--path=/tmp/s01-r8-business-wp'],{stdio:'pipe',timeout:30000});
}
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
 for(const [locale,desired] of [['en_US','en'],['zh_CN','zh']]){
   setLocale(locale);
   const page=await browser.newPage({viewport:{width:1440,height:900}});
   const network=[];
   const errors=[];
   await page.addInitScript(()=>{
     window.__vfSyntaxErrors=[];
     window.addEventListener('error',e=>{
       window.__vfSyntaxErrors.push({
         message:String(e.message||''),
         filename:String(e.filename||e.target?.src||''),
         line:e.lineno||0,
         col:e.colno||0,
         tag:String(e.target?.tagName||''),
         source:String(e.error?.stack||'').slice(0,400)
       });
     },true);
   });
   page.on('pageerror',e=>errors.push({message:e.message,stack:String(e.stack||'').slice(0,1000)}));
   page.on('console',m=>{if(m.type()==='error')errors.push({message:m.text(),at:m.location()})});
   page.on('requestfailed',req=>network.push({url:req.url(),failure:req.failure()?.errorText}));
   page.on('response',async resp=>{
     if(resp.request().resourceType()!=='script')return;
     const hdr=resp.headers();
     let prefix='';
     try{prefix=(await resp.text()).slice(0,160)}catch(e){prefix='READ_ERROR:'+e.message}
     network.push({url:resp.url(),status:resp.status(),type:hdr['content-type']||'',prefix:prefix.replace(/\s+/g,' ').slice(0,130)});
   });
   const response=await page.goto(base,{waitUntil:'networkidle',timeout:30000});
   await page.waitForTimeout(300);
   const found=await page.evaluate(()=>({
     locale:document.querySelector('[data-vf-module="playlist-checker"]')?.getAttribute('data-vf-tool-lang')||
         document.querySelector('[data-vf-module="playlist-checker"]')?.getAttribute('data-vf-locale')||'',
     htmlLang:document.documentElement.lang,
     visible:document.querySelector('[data-vf-playlist-action="analyze"]')?.textContent?.trim()||'',
     ready:document.querySelector('[data-vf-module="playlist-checker"]')?.getAttribute('data-vf-playlist-checker-ready')||'',
     errors:window.__vfSyntaxErrors||[],
     scripts:[...document.querySelectorAll('script[src]')].map(x=>({src:x.src,type:x.type||'classic'}))
   }));
   const summary={wanted:desired,status:response.status(),...found,network,errors};
   result.checks.push(summary);
   console.log('S01_R8_LOCALE_AND_JS_DIAGNOSTIC_'+desired.toUpperCase()+'='+JSON.stringify(summary));
   await page.close();
 }
 fs.writeFileSync('s01-r8-js-locale-evidence.json',JSON.stringify(result,null,2));
 const en=result.checks[0],zh=result.checks[1];
 assert.equal(en.status,200);assert.equal(zh.status,200);
 assert.ok(en.ready&&zh.ready,'runtime must be ready in both languages');
 assert.equal(en.locale,'en','en locale must be en');
 assert.equal(zh.locale,'zh','zh locale must be zh');
 console.log('S01_R8_EN_ZH_PLAYLIST_RUNTIME=PASS');
 const bad=result.checks.flatMap(x=>x.network.filter(n=>n.type?.includes('text/html')&&n.prefix?.startsWith('<')));
 if(bad.length){console.log('S01_R8_NON_JS_AS_SCRIPT='+JSON.stringify(bad));}
 }finally{await browser.close();}
})().catch(e=>{fs.writeFileSync('s01-r8-js-locale-evidence.json',JSON.stringify({...result,error:String(e.stack||e)},null,2));console.error(e);process.exit(1)});
