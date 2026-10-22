'use strict';
const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs');
const check=require(process.cwd()+'/target/tests/recovery-fresh-confirmation-browser-check.js');
(async()=>{const b=await chromium.launch();const checks=[];try{
 const p=await b.newPage({viewport:{width:1440,height:1000}}),errors=[],requests=[];
 const url='http://127.0.0.1:18880/wp-admin/themes.php?page=vf-theme-modules&tab=recovery';
 p.on('pageerror',e=>errors.push(e.message));p.on('request',r=>{if(r.url().includes('admin-ajax.php')&&(r.postData()||'').includes('vf_theme_recovery_'))requests.push('recovery-action');});
 await p.goto('http://127.0.0.1:18880/wp-login.php');await p.locator('#user_login').fill('admin');await p.locator('#user_pass').fill('Synthetic-Only-Update-54!');await p.locator('input[name=redirect_to]').evaluate((e,v)=>e.value=v,url);await p.locator('#wp-submit').click();await p.waitForURL('**/wp-admin/**');await p.goto(url,{waitUntil:'networkidle'});
 const root=p.locator('[data-vf-recovery-page]');const revision=await root.getAttribute('data-vf-recovery-revision');
 for(const width of [1440,1024]){
  await p.setViewportSize({width,height:1000});
  for(const task of ['status','export','import','restore']){
   await root.locator('[data-vf-recovery-workflow-step='+task+']').click();
   assert(await root.locator('[data-vf-recovery-workflow-section='+task+']').isVisible());
   assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   if(width===1440)await p.screenshot({path:'proof/recovery-'+task+'-1440.png',fullPage:true});
  }
  await root.locator('.vf-recovery-danger-zone > summary').click();
  await check(p);
  checks.push({width,status:'PASS',dismiss_paths:['cancel','escape','backdrop','close'],fresh_confirmation:true});
  await root.locator('.vf-recovery-danger-zone > summary').click();
 }
 assert.equal(await root.getAttribute('data-vf-recovery-revision'),revision);assert.deepEqual(errors,[]);assert.deepEqual(requests,[]);
 fs.writeFileSync('proof/mounted-results.json',JSON.stringify({status:'PASS',environment:'REAL_ISOLATED_WORDPRESS',checks,recovery_action_requests:0,revision_unchanged:true,production:'UNTOUCHED'},null,2));
 console.log('MOUNTED_RECOVERY_FRESH_CONFIRM_NO_WRITES_PASS');
}catch(e){fs.writeFileSync('proof/mounted-failure.json',JSON.stringify({error:e.message,checks}));throw e;}finally{await b.close();}})().catch(e=>{console.error(e);process.exit(1)});
