'use strict';
const fs=require('fs');
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
const source=fs.readFileSync('target/assets/js/admin-o11-source.js','utf8');
const html='<!doctype html><html><head><meta charset="utf-8"></head><body>'
+'<main data-vf-acceptance-overview-root><section id="vf-quality-task">'
+'<div data-vf-source-page data-ajax-url="https://fixture.example/wp-admin/admin-ajax.php" data-nonce="good" data-job-status="COMPLETED" data-job-revision="7" data-has-state="1" data-batch-ready="1" data-source-pass="0" data-snapshot-current="0">'
+'<div data-source-feedback hidden></div>'
+'<button data-source-open-start>开始源站验收</button>'
+'<b data-source-summary-status>已完成</b><b data-source-summary-count>6/6</b>'
+'<h2 data-job-stage>已完成</h2><p data-job-message>old evidence</p>'
+'<strong data-job-progress>100%</strong><i data-job-bar></i><b data-job-current>/</b>'
+'<b data-job-count>6 / 6</b><b data-job-failed>0</b><b data-job-elapsed>10秒</b>'
+'<button data-source-action="continue" hidden>继续检查</button>'
+'<button data-source-action="pause" hidden>暂停任务</button>'
+'<button data-source-action="resume" hidden>恢复并继续</button>'
+'<button data-source-open-cancel hidden>取消当前任务</button>'
+'<button data-source-open-reset>复位任务与结果</button>'
+'<span data-source-control-hint></span>'
+'<div class="vf-source-modal" data-source-start-modal hidden><input type="radio" name="vf_source_mode" value="quick" checked><button data-source-close>关闭</button><button data-source-start-confirm>开始验收</button></div>'
+'<div class="vf-source-modal" data-source-cancel-modal hidden><span data-source-cancel-message></span><button data-source-close>关闭</button><button data-source-cancel-confirm>确认取消任务</button></div>'
+'<div class="vf-source-modal" data-source-reset-modal hidden><input data-source-reset-phrase><span data-source-reset-message></span><button data-source-close>关闭</button><button data-source-reset-confirm>复位任务与结果</button></div>'
+'</div></section>'
+'<details class="vf-qc-disclosure" data-vf-qc-disclosure="issues"><summary>问题明细</summary><p>issue</p></details>'
+'<details class="vf-qc-disclosure" data-vf-qc-disclosure="advanced"><summary>高级信息</summary><p>advanced</p></details>'
+'</main>'
+'<script>window.__softRefreshes=0;window.vfOpsSoftRefresh=function(){window.__softRefreshes++;return Promise.resolve()};</script>'
+'<script>'+source+'</script></body></html>';

let state={status:'COMPLETED',revision:7,processed:6,total:6,progress:100},requests=[];
function respond(data,success=true,status=200){return{status,contentType:'application/json',body:JSON.stringify({success,data})};}
function handle(req){
 const body=new URLSearchParams(req.postData()||'');
 const action=(body.get('action')||'').replace('vf_ops_o11_source_','');
 const expected=body.get('expected_revision'), nonce=body.get('nonce');
 requests.push({action,expected,nonce,status:state.status});
 if(nonce!=='good')return respond({message:'Nonce rejected'},false,403);
 if(expected!==String(state.revision))return respond({message:'页面中的任务版本已过期，请刷新后再操作。',job:{revision:state.revision}},false,409);
 let next=state.status;
 if(action==='start' && !['RUNNING','PAUSED'].includes(next)){state={status:'RUNNING',revision:state.revision+1,processed:0,total:6,progress:0};}
 else if(action==='pause' && next==='RUNNING'){state.status='PAUSED';state.revision++;}
 else if(action==='resume' && next==='PAUSED'){state.status='RUNNING';state.revision++;}
 else if(action==='cancel' && ['RUNNING','PAUSED'].includes(next)){state.status='CANCELLED';state.revision++;}
 else if(action==='step' && next==='RUNNING'){state.processed=Math.min(6,state.processed+2);state.progress=Math.round(state.processed*100/6);state.status=state.processed===6?'COMPLETED':'RUNNING';state.revision++;}
 else if(action==='reset' && !['RUNNING','PAUSED'].includes(next) && body.get('confirmation')==='复位源站验收'){state.status='NOT_STARTED';state.revision++;state.processed=0;state.progress=0;}
 else return respond({status:'NOOP',message:'当前状态不支持该操作。',job:{...state}});
 const job={...state,stage:'分批检查源站',message:'Task '+state.status,elapsedSeconds:1,lastPath:'/',currentPath:'/'};
 return respond({status:'PASS',message:'Task '+state.status,job,...(state.status==='COMPLETED'?{snapshot:{summary:{status:'PARTIAL'}}}:{})});
}
async function status(page){return page.locator('[data-vf-source-page]').getAttribute('data-job-status');}
async function init(browser,width){
 const page=await browser.newPage({viewport:{width,height:850}});
 await page.route('https://fixture.example/**',async route=>{
   if(route.request().url().includes('/admin-ajax.php')){await route.fulfill(handle(route.request()));return;}
   await route.fulfill({status:200,contentType:'text/html',body:html});
 });
 await page.goto('https://fixture.example/wp-admin/admin.php?page=vf-toolsite-online-acceptance');
 return page;
}
(async()=>{
 const browser=await chromium.launch({headless:true});
 const page=await init(browser,1440);
 assert.equal(await status(page),'COMPLETED');
 await page.click('[data-source-open-start]');
 assert.equal(await page.locator('[data-source-start-modal]').evaluate(el=>el.hidden),false);
 await page.click('[data-source-start-confirm]');
 await page.waitForFunction(()=>document.querySelector('[data-vf-source-page]').dataset.jobStatus==='RUNNING');
 assert.equal(requests[0].action,'start');
 assert.equal(requests[0].expected,'7');
 await page.click('[data-source-action="pause"]');
 await page.waitForFunction(()=>document.querySelector('[data-vf-source-page]').dataset.jobStatus==='PAUSED');
 assert.equal(await page.locator('[data-source-open-reset]').isVisible(),false);
 assert.equal(requests.some(x=>x.action==='pause'),true);
 await page.click('[data-source-action="resume"]');
 await page.waitForFunction(()=>document.querySelector('[data-vf-source-page]').dataset.jobStatus==='RUNNING');
 await page.waitForFunction(()=>document.querySelector('[data-vf-source-page]').dataset.jobStatus==='COMPLETED',{timeout:12000});
 assert.equal(state.processed,6);
 assert.equal(state.progress,100);
 assert.equal(await page.evaluate(()=>window.__softRefreshes),1);
 assert.equal(await page.locator('[data-job-count]').innerText(),'6 / 6');
 console.log('PASS desktop completed+outdated -> start -> pause -> resume -> 6/6 -> readback');

 // Another browser tab still holds revision 7; conflict must not silently adopt latest revision.
 const stale=await init(browser,390);
 assert.equal(await stale.locator('[data-vf-source-page]').getAttribute('data-job-revision'),'7');
 await stale.click('[data-source-open-start]');
 await stale.click('[data-source-start-confirm]');
 await stale.waitForFunction(()=>document.querySelector('[data-source-feedback]').textContent.includes('过期'));
 assert.equal(await stale.locator('[data-vf-source-page]').getAttribute('data-job-revision'),'7');
 assert.equal(await stale.locator('[data-source-feedback]').getAttribute('class'),'vf-source-feedback is-error');
 console.log('PASS mobile stale-tab conflict: error visible, revision unchanged');

 await page.click('[data-source-open-start]');
 await page.click('[data-source-start-confirm]');
 await page.waitForFunction(()=>document.querySelector('[data-vf-source-page]').dataset.jobStatus==='RUNNING');
 await page.click('[data-source-open-cancel]');
 await page.click('[data-source-cancel-confirm]');
 await page.waitForFunction(()=>document.querySelector('[data-vf-source-page]').dataset.jobStatus==='CANCELLED');
 assert.equal(state.status,'CANCELLED');
 console.log('PASS completed -> restart -> cancel');

 await page.click('[data-source-open-reset]');
 await page.fill('[data-source-reset-phrase]','bad');
 await page.click('[data-source-reset-confirm]');
 assert.equal(state.status,'CANCELLED');
 assert.equal(requests.filter(x=>x.action==='reset').length,0);
 await page.fill('[data-source-reset-phrase]','复位源站验收');
 await page.click('[data-source-reset-confirm]');
 await page.waitForFunction(()=>window.__softRefreshes>=2);
 assert.equal(state.status,'NOT_STARTED');
 assert.equal(requests.filter(x=>x.action==='reset').length,1);
 console.log('PASS cancel -> invalid reset rejected -> confirmed reset -> readback');
 await browser.close();
 console.log(JSON.stringify({pass:true,requests:requests.length,actions:requests.map(x=>x.action),production:'NOT_TOUCHED'}));
})().catch(e=>{console.error(e);process.exit(1)});
