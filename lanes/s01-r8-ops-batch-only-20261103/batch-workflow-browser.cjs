'use strict';
/**
 * Real WP admin UI, version-snapshot and exact readback, disposable posts only.
 * No synthetic DOM, no direct SQL writes, no destructive/deploy/remote actions.
 */
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
const origin=process.env.S01_R8_ORIGIN||'http://127.0.0.1:18880';
const dir='/tmp/s01-r8-ops-save-evidence';
const fixture=JSON.parse(fs.readFileSync(path.join(dir,'fixture.json'),'utf8'));
const routes=JSON.parse(fs.readFileSync('/tmp/s01-r8-ops-admin-evidence/ops-targets.json','utf8'));
const admin=routes.find(x=>x.key==='content_articles');
assert(admin && new URL(admin.url).origin===origin,'Must use canonical isolated Ops content URL');
async function main(){
 const browser=await chromium.launch({headless:true}),cases=[],failures=[];
 try{
  for(const width of [1440,768]){
   const page=await browser.newPage({viewport:{width,height:940},acceptDownloads:false});
   const targetId=fixture.ids[String(width)],title='R8 Ops Core Save Fixture '+width;
   const canonical=new URL(admin.url);
   canonical.searchParams.set('vf_content_q',title);
   const url=canonical.toString();
   const writes=[];
   let loginDone=false;
   await page.route('**/*',async r=>{
    const q=r.request(),u=new URL(q.url()),method=q.method();
    if(loginDone && u.origin===origin && !['GET','HEAD','OPTIONS'].includes(method)){
     const approved=method==='POST'&&u.pathname==='/wp-admin/admin.php'&&
       u.searchParams.get('page')==='vf-toolsite-content'&&u.searchParams.get('tab')==='workflow';
     if(!approved){writes.push({status:'BLOCKED',method,path:u.pathname});await r.abort('blockedbyclient');return;}
     writes.push({status:'ALLOW_CONTENT_FORM',method,path:u.pathname});
    }
    await r.continue();
   });
   const row=()=>page.locator('.vf-content-manager-row').filter({hasText:title});
   const state=async()=>({core:await row().evaluate(e=>e.classList.contains('is-core')),
     text:(await row().textContent()).replace(/\s+/g,' ').slice(0,750),
     workflow:await row().locator('.vf-content-manager-cell.is-content-health strong').first().textContent()});
   const load=async()=>{
    const res=await page.goto(url,{waitUntil:'domcontentloaded',timeout:40000});
    assert.equal(res.status(),200,'Independent GET did not return HTTP200');
    assert.equal(await page.locator('[data-vf-v13-route="content_articles"]').count(),1,'Wrong Ops route');
    assert.equal(await row().count(),1,'Target row not found');
   };
   const post=async selector=>{
    // Actual Ops bulk UI requires a real first-party confirmation. The
    // previous harness clicked Submit but never accepted the modal, so
    // it sent zero POSTs and timed out. Exercise that actual control.
    const navigationPromise=page.waitForNavigation({waitUntil:'domcontentloaded',timeout:30000});
    await selector.click();
    const modal=page.locator('dialog.vf-saas-confirm-modal');
    if(await modal.isVisible()){
      assert(await modal.locator('#vf-saas-confirm-title').textContent(),'Confirmation title missing');
      await modal.locator('.vf-saas-confirm-submit').click();
    }
    const navigation=await navigationPromise;
    assert.equal(navigation.status(),200,'Real Ops POST/PRG did not return a valid page');
   };
   try{
    await page.goto(origin+'/wp-login.php',{waitUntil:'domcontentloaded'});
    await page.locator('#user_login').fill('synthetic');
    await page.locator('#user_pass').fill('synthetic-only-password');
    await Promise.all([page.waitForURL(u=>u.pathname.startsWith('/wp-admin/'),{timeout:30000}),page.locator('#wp-submit').click()]);
    assert(await page.locator('#wpadminbar').count()>0,'Real admin session absent');
    loginDone=true;
    await load();
    assert.equal((await state()).workflow.trim(),'草稿','Initial workflow is not draft');
    const bulk=page.locator('#vf-content-manager-bulk-form');
    assert.equal(await row().locator('input.vf-content-manager-row-check').count(),1,'Not an eligible isolated row');
    await row().locator('input.vf-content-manager-row-check').check();
    await bulk.locator('select[name="vf_ops_content_management_action"]').selectOption('bulk_workflow_refining');
    assert(!(await bulk.locator('button[type="submit"]').isDisabled()),'Bulk action remains disabled');
    await post(bulk.locator('button[type="submit"]'));
    await load();
    assert.equal((await state()).workflow.trim(),'精修中','Actual bulk save did not persist workflow');
    cases.push({width,action:'real_bulk_draft_to_refining',result:'PASS'});

    // Simulate another stale browser tab using a previously captured original
    // draft snapshot with a still-valid WordPress nonce. Rejected on server.
    const staleBulk=page.locator('#vf-content-manager-bulk-form');
    await row().locator('input.vf-content-manager-row-check').check();
    await staleBulk.locator('select[name="vf_ops_content_management_action"]').selectOption('bulk_workflow_refining');
    await staleBulk.locator('input[name^="expected_workflows"]').evaluate(e=>{e.value='draft';});
    await post(staleBulk.locator('button[type="submit"]'));
    await load();
    assert.equal((await state()).workflow.trim(),'精修中','Stale submission overwrote current workflow');
    const pageText=await page.locator('main.vf-v6-shell-main').innerText();
    assert(/失败\s*1|版本已变化|重新操作|版本冲突/.test(pageText),'Stale conflict not visible to owner');
    cases.push({width,action:'stale_revision_rejected_unchanged_state',result:'PASS'});

    // Return the same isolated post to original draft via current legitimate
    // workflow form, providing required high-risk reason; no trash/delete.
    await row().locator('[data-vf-content-more]').click();
    const workflow=row().locator('form.vf-content-manager-row-workflow');
    assert.equal(await workflow.count(),1,'Ops workflow control absent');
    await workflow.locator('select[name="target_workflow"]').selectOption('draft');
    await workflow.locator('input[name="transition_reason"]').fill('R8 isolated reversible workflow rollback verification');
    await post(workflow.locator('button[type="submit"]'));
    await load();
    assert.equal((await state()).workflow.trim(),'草稿','Rollback to draft not persisted');
    cases.push({width,action:'real_controlled_workflow_rollback_to_draft',result:'PASS'});
    assert.equal(writes.filter(x=>x.status==='BLOCKED').length,0,'Unexpected non-content write attempted');
    await page.screenshot({path:path.join(dir,'batch-'+width+'-roundtrip.png'),fullPage:true});
   }catch(e){failures.push({width,error:String(e.stack||e),requests:writes});}
   finally{await page.close();}
  }
 }finally{await browser.close();}
 const report={scope:'Ops actual administrator bulk state change/stale revision/controlled rollback, no Production',total:6,passed:cases.length,failed:failures.length,cases,failures};
 fs.writeFileSync(path.join(dir,'batch-browser-results.json'),JSON.stringify(report,null,2));
 console.log('S01_R8_OPS_REAL_BATCH_REVISION_ROLLBACK '+JSON.stringify(report));
 assert.equal(failures.length,0,'Ops batch/revision/rollback failed');
 assert.equal(cases.length,6,'Missing real browser proof');
}
main().catch(e=>{console.error(e.stack||e);process.exitCode=1;});
