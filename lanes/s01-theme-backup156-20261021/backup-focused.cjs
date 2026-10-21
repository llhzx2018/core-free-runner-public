const {chromium}=require('playwright');
const fs=require('fs');
(async()=>{
 const browser=await chromium.launch({headless:true});
 const checks=[];
 function ck(name,pass,detail){checks.push({name,pass:!!pass,detail});}
 try{
  for(const lang of ['en','zh']){
   const ctx=await browser.newContext({viewport:{width:1440,height:950},colorScheme:'light'});
   const page=await ctx.newPage();
   const url='http://127.0.0.1:18880/'+(lang==='zh'?'zh/':'')+'m3u8-backup-restore/';
   const response=await page.goto(url,{waitUntil:'load',timeout:25000});
   ck(lang+' route returns 200',response?.status()===200,{url:page.url(),status:response?.status()});
   const root=page.locator('.vf-backup-restore[data-vf-module="backup-restore"]');
   await root.waitFor({state:'visible',timeout:15000});
   await page.evaluate(()=>document.fonts.ready);
   const css=await root.evaluate(el=>{
     function info(selector){const e=el.querySelector(selector);if(!e)return null;const s=getComputedStyle(e);return{fontSize:parseFloat(s.fontSize),height:e.getBoundingClientRect().height,color:s.color,display:s.display,visible:e.getClientRects().length>0};}
     const stage=el.closest('[data-vf-tool-runtime-stage="1"]');
     return{stage:!!stage,body:parseFloat(getComputedStyle(el).fontSize),title:info('.vf-bak-product-context strong'),switch:info('.vf-bak-task-switch button'),description:info('.vf-bak-boundary p'),status:info('.vf-bak-storage-overview strong'),primary:info('[data-vf-backup-action="preview-workspace"]'),wide:document.documentElement.scrollWidth>innerWidth+2,mode:el.dataset.vfBackupTask};
   });
   ck(lang+' installed runtime scoped Theme CSS',css.stage && css.body>=15,css);
   ck(lang+' readable title and guidance',css.title?.fontSize>=22&&css.description?.fontSize>=15,css);
   ck(lang+' task buttons readable and accessible',css.switch?.fontSize>=15&&css.switch?.height>=44,css);
   ck(lang+' primary task distinct and touch-size',css.primary?.height>=44,css);
   ck(lang+' desktop horizontal layout safe',!css.wide,css);
   ck(lang+' defaults to nondestructive backup',css.mode==='backup',css);
   const restore=page.locator('[data-vf-backup-task-toggle="restore"]');
   await restore.click();
   ck(lang+' restore switch works without automatic restore',await root.getAttribute('data-vf-backup-task')==='restore',await root.getAttribute('data-vf-backup-task'));
   ck(lang+' restore confirmation initially protected',await page.locator('[data-vf-backup-action="restore-backup"]').isDisabled());
   await page.locator('[data-vf-backup-task-toggle="backup"]').click();
   ck(lang+' safe backup task restored',await root.getAttribute('data-vf-backup-task')==='backup');
   await page.screenshot({path:'proof/'+lang+'-backup156-desktop.png',fullPage:true});
   await ctx.close();
  }
 }finally{await browser.close();}
 fs.writeFileSync('proof/backup156-browser.json',JSON.stringify({status:checks.every(x=>x.pass)?'PASS':'FAIL',checks},null,2));
 console.log('BACKUP156_DESKTOP_CHECKS',checks.length,'FAILURES',JSON.stringify(checks.filter(x=>!x.pass)).slice(0,12000));
 if(checks.some(x=>!x.pass))process.exitCode=1;
})().catch(e=>{console.error(e);process.exitCode=1;});
