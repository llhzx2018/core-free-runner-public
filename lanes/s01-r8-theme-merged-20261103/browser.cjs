'use strict';
const {chromium}=require('playwright');
const cp=require('node:child_process');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const base='http://127.0.0.1:18880';
const report={theme:'84fcd264da22b7d5e77127f6b7b952accc8362a1',m3:'c1a69da4c5c6c40954a3319cc0976065324c77ed',ops:'3f22e61339f7c76eea2c4524885819b10ee59057',isolated:true,results:[]};
function locale(l){
 cp.execFileSync('php',['/tmp/wp-cli-r8.phar','config','set','WPLANG',l,'--path=/tmp/s01-r8-business-wp'],{timeout:30000});
 const actual=cp.execFileSync('php',['/tmp/wp-cli-r8.phar','eval','echo get_locale();','--path=/tmp/s01-r8-business-wp'],{encoding:'utf8',timeout:30000}).trim();
 assert.equal(actual,l,'WordPress locale not active');
}
(async()=>{
 const b=await chromium.launch({headless:true});
 try{
 for(const [l,label] of [['en_US','en'],['zh_CN','zh']]){
  locale(l);
  // WordPress config is rewritten between phases; avoid stale CLI-server opcode cache.
  await new Promise(resolve=>setTimeout(resolve,3200));
  for(const width of [768,1440]){
   const context=await b.newContext({viewport:{width,height:900},acceptDownloads:true});
   const p=await context.newPage(),errors=[];
   p.on('pageerror',e=>errors.push(e.message));
   p.on('response',r=>{if(r.status()>=400&&r.url().includes('wp-content'))errors.push('HTTP '+r.status()+' '+r.url());});
   const response=await p.goto(base+'/m3u8-backup-restore/',{waitUntil:'networkidle',timeout:30000});
   assert.equal(response.status(),200,'backup page HTTP 200');
   const root=p.locator('[data-vf-module="backup-restore"]').first();
   await root.waitFor({timeout:18000});
   const pageInfo=await p.evaluate(()=>({
     lang:document.documentElement.lang,
     heading:document.title,
     width:document.documentElement.scrollWidth,
     viewport:document.documentElement.clientWidth,
     backupModules:document.querySelectorAll('[data-vf-module="backup-restore"]').length,
     bodyText:document.body.innerText.slice(0,1600)
   }));
   assert.equal(pageInfo.backupModules,1);
   const diag=await p.evaluate(()=>({
     path:location.pathname,
     htmlLang:document.documentElement.lang,
     toolLang:document.querySelector('[data-vf-module="backup-restore"]')?.getAttribute('data-vf-tool-lang'),
     moduleLocale:document.querySelector('[data-vf-module="backup-restore"]')?.getAttribute('data-vf-locale'),
     bodyClass:document.body.className,
     alternates:[...document.querySelectorAll('link[rel="alternate"][hreflang]')].map(x=>({lang:x.hreflang,url:x.href})).slice(0,5),
     rootText:document.querySelector('[data-vf-module="backup-restore"]')?.innerText.slice(0,350),
     htmlStart:document.documentElement.outerHTML.slice(0,350)
   }));
   console.log('S01_R8_LOCALE_DIAGNOSTIC_'+label.toUpperCase()+'_'+width+'='+JSON.stringify(diag));
   assert.ok(pageInfo.lang.toLowerCase().startsWith(label),'wrong page locale '+pageInfo.lang);
   assert.equal(diag.toolLang,label,'backup runtime tool-language mismatch');
   assert.equal(diag.moduleLocale,label,'backup runtime locale mismatch');
   const action=root.locator('[data-vf-backup-action="preview-workspace"]').first();
   await action.waitFor({timeout:12000});
   await action.click();
   await p.waitForFunction(()=>{const e=document.querySelector('[data-vf-module="backup-restore"]');return e&&e.dataset.vfBackupBusy==='0'&&e.dataset.vfBackupLastAction==='preview-workspace';},null,{timeout:20000});
   assert.deepEqual(errors,[],'browser page errors');
   report.results.push({language:label,width,status:response.status(),htmlLang:pageInfo.lang,preview:'PASS',pageErrors:errors,viewport:pageInfo.viewport,scrollWidth:pageInfo.width});
   console.log('S01_R8_THEME_BACKUP_'+label.toUpperCase()+'_'+width+'=PASS');
   await context.close();
  }
 }
 fs.writeFileSync('s01-r8-theme-merged-evidence.json',JSON.stringify(report,null,2));
 assert.equal(report.results.length,4,'expected EN/ZH by 768/1440');
 console.log('S01_R8_THEME_BACKUP_EN_ZH_DESKTOP=PASS 4/4');
 }catch(e){fs.writeFileSync('s01-r8-theme-merged-evidence.json',JSON.stringify({...report,failed:String(e.stack||e)},null,2));throw e}finally{await b.close()}
})().catch(e=>{console.error(e);process.exit(1)});
