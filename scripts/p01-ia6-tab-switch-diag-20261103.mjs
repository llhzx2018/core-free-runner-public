import assert from 'node:assert/strict';
import {chromium} from 'playwright';

const origin=process.env.P01_TEST_ORIGIN,password=process.env.P01_TEST_PASSWORD;
if(!/^http:\/\/127\.0\.0\.1:\d+$/.test(origin||'')||!password)throw Error('ISOLATED_LOCALHOST_REQUIRED');
const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
try{
 const context=await browser.newContext({viewport:{width:1440,height:900}});
 const login=await context.request.post(origin+'/api.php?action=login',{data:{password}});
 assert.equal(login.status(),200);
 assert.equal((await login.json()).ok,true);
 const page=await context.newPage();
 const errors=[];
 page.on('pageerror',error=>errors.push(String(error.message||error).slice(0,260)));
 await page.goto(origin+'/start.php',{waitUntil:'domcontentloaded'});
 await page.locator('[data-vf-local-manage-open]').first().click();
 const dialog=page.locator('#vf-local-management');
 const all=['home','start','inbox','channels','watch','music','topics','courses','projects','tools','software','global'];
 const reports=[];
 for(const key of all){
   const tab=dialog.locator('[data-vf-management-tab="'+key+'"]');
   await tab.click();
   let state=await page.evaluate(()=>({
     active:[...document.querySelectorAll('#vf-local-management [data-vf-management-tab][aria-selected="true"]')]
       .map(n=>n.dataset.vfManagementTab),
     remote:document.querySelector('[data-vf-management-remote]')?.dataset.vfManagementRemote||'',
     statuses:[...document.querySelectorAll('#vf-local-management [role="alert"],#vf-local-management [role="status"]')]
       .map(n=>n.textContent?.trim()||'').filter(s=>/请先|正在处理|不能|拒绝|未知|正在读取|尚未确认|已取消|没有执行|无法离开/.test(s))
       .slice(-10).map(s=>s.slice(0,110)),
     watchHidden:document.querySelector('[data-vf-remote-watch-root]')?.hidden,
     musicHidden:document.querySelector('[data-vf-remote-music-root]')?.hidden
   }));
   if(state.active[0]!==key){
     reports.push({key,attempt:0,state,errors:errors.slice(-5)});
     for(let i=1;i<=4&&state.active[0]!==key;i++){
       await page.waitForTimeout(500*i);
       await tab.click();
       state=await page.evaluate(()=>({
         active:[...document.querySelectorAll('#vf-local-management [data-vf-management-tab][aria-selected="true"]')]
          .map(n=>n.dataset.vfManagementTab),
         statuses:[...document.querySelectorAll('#vf-local-management [role="alert"],#vf-local-management [role="status"]')]
          .map(n=>n.textContent?.trim()||'').filter(s=>/请先|正在处理|不能|拒绝|未知|正在读取|尚未确认|已取消|没有执行|无法离开/.test(s))
          .slice(-10).map(s=>s.slice(0,110))
       }));
       reports.push({key,attempt:i,state,errors:errors.slice(-5)});
     }
   }
 }
 console.log('P01_TAB_SWITCH_FOCUSED_DIAGNOSTICS='+JSON.stringify({
   reports:reports.slice(0,35),pageerrors:errors.slice(0,12)
 }));
 const final=await dialog.locator('[data-vf-management-tab="global"]').getAttribute('aria-selected');
 assert.equal(final,'true','Must finish on Global after protected switches');
 console.log('P01_TAB_SWITCH_FOCUSED_SAFETY_STATE=PASS');
 await context.close();
}finally{await browser.close();}
