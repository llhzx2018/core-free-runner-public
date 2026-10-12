'use strict';
const {chromium}=require('playwright'),fs=require('fs'),cp=require('child_process'),path=require('path'),assert=require('assert/strict');
const root=process.env.PRODUCT_DIR;
assert(root && fs.existsSync(path.join(root,'VERSION')));
const view=scene=>cp.execFileSync('php',[path.join(root,'tests/s01-c02-1211092-integrations-state-render.php'),'--emit',scene],{encoding:'utf8',maxBuffer:1024*1024});
const js=fs.readFileSync(path.join(root,'assets/js/v13/system/integrations.js'),'utf8');
const css=fs.readFileSync(path.join(root,'assets/css/v13/system/integrations.css'),'utf8')+'\n'+fs.readFileSync(path.join(root,'assets/css/current/admin-s01-integrations-r4.css'),'utf8');
const html=scene=>'<html><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>*,*:before,*:after{box-sizing:border-box}body{margin:0;padding:16px}.vf-page-canvas{max-width:1060px;margin:auto}</style><style>'+css+'</style></head><body class="vf-page-body-v2 vf-ops-v7-admin"><nav class="vf-ops-admin-shell"><a id="synthetic-next" href="/wp-admin/admin.php?page=vf-toolsite-system-settings&tab=recovery">下一页</a></nav><main class="vf-page-canvas">'+view(scene)+'</main><script>'+js+'</script></body></html>';
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 let checks=0;
 try {
  for(const width of [1440,1024,768,390]) for(const scene of ['ready','configured_fail','not_connected','empty']){
   const p=await browser.newPage({viewport:{width,height:960}});
   await p.route('https://fixture.test/**',r=>r.fulfill({status:200,contentType:'text/html; charset=utf-8',body:html(scene)}));
   await p.goto('https://fixture.test/wp-admin/admin.php?page=vf-toolsite-system-settings&tab=integrations');
   const rootEl=p.locator('[data-vf-in-root]'),form=rootEl.locator('#vf-in-config-form');
   const save=rootEl.locator('[data-vf-in-config-save]');
   assert.equal(await save.count(),1,'single Save CTA');
   assert.equal(await save.isDisabled(),true,'clean Save is nonoperative');
   const button=await rootEl.locator('.vf-in-product-primary button').first().innerText();
   if(scene==='ready')assert(button.includes('同步'));
   if(scene==='configured_fail')assert(button.includes('检查'));
   if(scene==='not_connected')assert(button.includes('连接'));
   assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2),true,'no horizontal overflow');
   await rootEl.locator('input[name=gscProperty]').fill('sc-domain:edited-example.com');
   assert.equal(await save.isEnabled(),true,'existing GSC stays editable');
   assert.equal(await rootEl.locator('[data-vf-in-unsaved-hint]').isVisible(),true);
   const operations=rootEl.locator('.vf-in-operations-disclosure');
   if(!await operations.evaluate(e=>e.open))await operations.locator('summary').click();
   const otherButtons=rootEl.locator('[data-vf-in-action-form]:not([data-vf-in-config-form]) button[type=submit]');
   const otherStates=await otherButtons.evaluateAll(els=>els.map(x=>x.disabled));
   assert(otherStates.length>=3 && otherStates.every(Boolean),'stale evidence actions disabled');
   const blocked=await p.evaluate(()=>{const e=new Event('submit',{bubbles:true,cancelable:true});document.querySelector('[data-vf-in-action-form]:not([data-vf-in-config-form])').dispatchEvent(e);return e.defaultPrevented});
   assert.equal(blocked,true,'direct submit against unsaved config rejected');
   await p.evaluate(()=>{window.confirm=()=>false});
   const nav=await p.evaluate(()=>{const a=document.getElementById('synthetic-next');const e=new MouseEvent('click',{bubbles:true,cancelable:true,button:0});a.dispatchEvent(e);return e.defaultPrevented});
   assert.equal(nav,true,'soft navigation does not discard draft without consent');
   await p.evaluate(()=>document.dispatchEvent(new Event('vfops:soft-readback-complete')));
   assert.equal(await save.isEnabled(),true,'generic readback must not fake persistence');
   if(scene==='ready') {
    const analytics=rootEl.locator('.vf-in-service-config').nth(1);
    if(!(await analytics.evaluate(x=>x.open)))await analytics.locator('summary').click();
    await analytics.locator('input[name=analyticsMeasurementId]').fill('bad-GA4');
    await analytics.locator('input[name=analyticsEnabled]').check();
    const rejected=await p.evaluate(()=>{let e=new Event('submit',{bubbles:true,cancelable:true});document.getElementById('vf-in-config-form').dispatchEvent(e);return {prevented:e.defaultPrevented,valid:document.querySelector('input[name=analyticsMeasurementId]').validity.valid}});
    assert(rejected.prevented && !rejected.valid,'invalid GA4 must block Save');
    await analytics.locator('input[name=analyticsMeasurementId]').fill('G-ABCD1234');
    const accepted=await p.evaluate(()=>{let e=new Event('submit',{bubbles:true,cancelable:true});document.getElementById('vf-in-config-form').dispatchEvent(e);return {prevented:e.defaultPrevented,valid:document.querySelector('input[name=analyticsMeasurementId]').validity.valid}});
    assert(!accepted.prevented && accepted.valid,'corrected GA4 can Save');
   }
   if(scene==='ready' && width===1440) {
    await rootEl.locator('input[name=gsc_client_id]').fill('a&gsc_client_secret=b');
    await rootEl.locator('input[name=gsc_client_secret]').fill('c');
    await rootEl.locator('input[name=gsc_client_id]').fill('a');
    await rootEl.locator('input[name=gsc_client_secret]').fill('b&gsc_client_secret=c');
    assert.equal(await save.isEnabled(),true,'credential delimiters never fake clean state');
   }
   console.log('PASS INTEGRATIONS_CONNECTED_SAVE',width,scene);
   checks++;
   await p.close();
  }
 }finally{await browser.close();}
 assert.equal(checks,16);
 console.log('S01_C02_1097_INTEGRATIONS_16_REAL_BROWSER_STATES_PASS');
})().catch(e=>{console.error(e);process.exitCode=1});
