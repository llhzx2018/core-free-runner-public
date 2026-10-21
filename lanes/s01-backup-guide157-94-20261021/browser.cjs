const { chromium }=require('playwright');
const fs=require('fs');
(async()=>{
 const browser=await chromium.launch({headless:true});
 const checks=[];
 function check(name,ok,detail){checks.push({name,pass:!!ok,detail});}
 try{
  for(const lang of ['zh','en']){
   const context=await browser.newContext({viewport:{width:1440,height:900},acceptDownloads:true});
   const page=await context.newPage();
   const u='http://127.0.0.1:18880/'+(lang==='zh'?'zh/':'')+'m3u8-backup-restore/';
   const response=await page.goto(u,{waitUntil:'load',timeout:30000});
   check(lang+' route returns 200',response?.status()===200,{url:page.url(),status:response?.status()});
   await page.locator('.vf-backup-restore[data-vf-module="backup-restore"]').waitFor();
   const actual=await page.evaluate(()=>{
     const faq=[...document.querySelectorAll('[data-vf-theme-module="faq"] summary')].map(n=>n.textContent.trim());
     const steps=[...document.querySelectorAll('[data-vf-theme-module="steps"] h3')].map(n=>n.textContent.trim());
     const top=[...document.querySelectorAll('.vf-tool-runtime-path li strong')].map(n=>n.textContent.trim());
     const btn=document.querySelector('.vf-backup-restore [data-vf-backup-action="preview-workspace"]');
     const root=document.querySelector('.vf-backup-restore');
     return{faq,steps,top,action:btn?.textContent.trim(),actionName:btn?.getAttribute('data-vf-backup-action'),startTask:root?.dataset.vfBackupTask,overflow:document.documentElement.scrollWidth>innerWidth+2};
   });
   check(lang+' backup route has accurate FAQ questions',actual.faq.length>=3&&(lang==='zh'?actual.faq.some(s=>s.includes('备份的是哪些数据')):actual.faq.some(s=>s.includes('What does this backup include'))),actual.faq);
   check(lang+' FAQ not generic playback or DRM copy',!actual.faq.some(x=>/DRM|M3U8 链接不能播放|下载和转换大文件|stream playable/i.test(x)),actual.faq);
   check(lang+' tool page bottom workflow is backup-specific',actual.steps.length===3&&(lang==='zh'?actual.steps[0].includes('选择备份或恢复'):actual.steps[0].includes('Choose backup or restore')),actual.steps);
   check(lang+' top workspace workflow is backup-specific',actual.top.length===3&&(lang==='zh'?actual.top[0].includes('查看本地数据'):actual.top[0].includes('Review local data')),actual.top);
   check(lang+' primary action names read-only inspect not generic start',!!actual.action&&!(lang==='zh'?['开始','立即开始','开始处理'].includes(actual.action):['Start','Run','Go'].includes(actual.action)),actual);
   check(lang+' action contract unchanged',actual.actionName==='preview-workspace'&&actual.startTask==='backup',actual);
   check(lang+' no desktop overflow',!actual.overflow,actual);
   const b=page.locator('.vf-backup-restore [data-vf-backup-action="preview-workspace"]');
   await b.click();
   await page.locator('.vf-backup-restore [data-vf-backup-report]').waitFor({state:'visible'});
   check(lang+' primary executes real non-destructive workspace review',await page.locator('.vf-backup-restore').getAttribute('data-vf-backup-ready')==='1');
   await page.locator('[data-vf-backup-task-toggle="restore"]').click();
   check(lang+' restore starts safely gated',await page.locator('[data-vf-backup-action="restore-backup"]').isDisabled());
   await page.screenshot({path:'proof/'+lang+'-backup-guide.png',fullPage:true});
   await context.close();
  }
 }finally{await browser.close();}
 const ok=checks.every(x=>x.pass);
 fs.writeFileSync('proof/backup-guide-results.json',JSON.stringify({status:ok?'PASS':'FAIL',count:checks.length,passed:checks.filter(x=>x.pass).length,failures:checks.filter(x=>!x.pass),checks},null,2));
 console.log('BACKUP_GUIDE_RESULT',JSON.stringify({count:checks.length,pass:checks.filter(x=>x.pass).length,fail:checks.filter(x=>!x.pass)}).slice(0,12000));
 if(!ok)process.exitCode=1;
})().catch(e=>{console.error('BACKUP_GUIDE_FATAL',e);process.exitCode=1;});