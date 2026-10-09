'use strict';
const fs=require('fs'),{execFileSync}=require('child_process'),{chromium}=require('playwright');
const base='http://127.0.0.1:18880',url=base+'/wp-admin/admin.php?page=vf-tool-m3u8-runtime-v6';
const state=s=>JSON.parse(execFileSync('docker',['exec','--user','www-data','-e','RUNTIME_SCENARIO='+s,process.env.WP,'php','/usr/local/bin/wp','eval-file','/tmp/runtime-fixture.php','--path=/var/www/html'],{encoding:'utf8',maxBuffer:12e6}));
const assert=(c,m)=>{if(!c)throw Error(m)};
async function login(p){await p.goto(base+'/wp-login.php');await p.locator('#user_login').fill('admin');await p.locator('#user_pass').fill('Synthetic-Only-Update-54!');await Promise.all([p.waitForURL(/wp-admin/),p.locator('#wp-submit').click()]);}
async function submit(p,s){const started=Date.now();console.log('SUBMIT',s);await Promise.all([p.waitForNavigation({waitUntil:'load'}),p.locator(s).click()]);await p.locator('[data-vf-provider-runtime]').waitFor();console.log('SUBMIT_DONE',s,Date.now()-started);}
async function geometry(p){return p.locator('[data-vf-runtime-seal] input[type="checkbox"]').evaluate(e=>{let r=e.getBoundingClientRect();return {rect:{x:r.x,y:r.y,width:r.width,height:r.height},scrollY,innerWidth,innerHeight,visualViewport:{width:visualViewport.width,height:visualViewport.height,offsetTop:visualViewport.offsetTop,pageTop:visualViewport.pageTop},body:document.body.getBoundingClientRect().toJSON(),hit:document.elementsFromPoint(r.x+r.width/2,r.y+r.height/2).slice(0,5).map(x=>({tag:x.tagName,cls:x.className})),checked:e.checked};});}
(async()=>{
 const browser=await chromium.launch(),cases=[],failures=[];state('original');
 try{
  for(const mode of ['normal','viewport-screenshot','fullpage-screenshot']){
   for(const width of [1440]){
    const trials=1;
    for(let trial=0;trial<trials;trial++){
     console.log('START',mode,width,trial);state('reset');const before=state('state');const ctx=await browser.newContext({javaScriptEnabled:false,viewport:{width,height:1100}}),p=await ctx.newPage();
     try{
      await login(p);await p.goto(url);await submit(p,'[data-vf-runtime-begin] button');await p.locator('[data-vf-runtime-editor] summary').click();await submit(p,'[data-vf-runtime-save] button');
      const row={mode,width,trial,status:'OBSERVED',beforeScreenshot:await geometry(p)};
      if(mode!=='normal')await p.screenshot({path:`proof/${mode}-${width}-before.png`,fullPage:mode==='fullpage-screenshot'});
      row.afterScreenshot=await geometry(p);
      const cb=p.locator('[data-vf-runtime-seal] input[type="checkbox"]');
      try{
       await cb.check({timeout:3500});assert(await cb.isChecked(),'native mouse checkbox did not change');
       await submit(p,'[data-vf-runtime-seal] button');const sealed=state('state');assert(sealed.current_version==='1.25.1'&&sealed.runtime_drafts===0&&sealed.foreign_hash===before.foreign_hash,'actual seal or foreign preservation');
       await p.reload();assert(state('state').all_hash===sealed.all_hash,'refresh changed native sealed state');row.status='PASS';row.native_seal='PASS';
      }catch(e){row.status='FAIL';row.error=e.message.slice(0,2500);row.afterFailure=await geometry(p);failures.push(row);}
      console.log('RESULT',mode,width,row.status,row.error||'');cases.push(row);fs.writeFileSync('proof/CLICK_PROGRESS.json',JSON.stringify({status:'OBSERVED',cases},null,2));
     }finally{await ctx.close();}
    }
   }
  }
  // Verify the default scripted path separately, without a capture between save and click.
  for(const width of [1440,390]){
   state('reset');const ctx=await browser.newContext({viewport:{width,height:1100}}),p=await ctx.newPage();try{await login(p);await p.goto(url);await submit(p,'[data-vf-runtime-begin] button');await p.locator('[data-vf-runtime-editor] summary').click();await submit(p,'[data-vf-runtime-save] button');await p.locator('[data-vf-runtime-seal] input[type="checkbox"]').check({timeout:3500});await submit(p,'[data-vf-runtime-seal] button');assert(state('state').current_version==='1.25.1','default native seal');cases.push({mode:'javascript-normal',width,status:'PASS',native_seal:'PASS'});}finally{await ctx.close();}
  }
  const normal=cases.filter(c=>c.mode==='normal'||c.mode==='javascript-normal');const result={status:normal.every(c=>c.status==='PASS')?'PASS':'FAIL',source_sha:process.env.TARGET_SHA,source_tree:process.env.TARGET_TREE,version:process.env.TARGET_VERSION,cases,normal_cases:normal.length,normal_failures:normal.filter(c=>c.status==='FAIL').length,screenshot_failures:failures.filter(c=>c.mode!=='normal').length,production:'NOT_EXECUTED',owner_acceptance:'NOT_CLAIMED',workarounds:'NONE_NO_HOME_NO_FORCE_NO_SCROLL_MUTATION'};
  fs.writeFileSync('proof/CLICK_DIAGNOSTIC.json',JSON.stringify(result,null,2));console.log(JSON.stringify({status:result.status,normal_cases:result.normal_cases,normal_failures:result.normal_failures,screenshot_failures:result.screenshot_failures}));assert(result.status==='PASS','real no-script path failed');
 }finally{state('restore-original');await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
