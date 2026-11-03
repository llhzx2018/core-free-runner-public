'use strict';
/**
 * Actual WordPress admin POST -> PRG -> independent GET -> DB readback proof.
 * Only temporary posts on disposable localhost. No Production, no recovery.
 */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

const origin = process.env.S01_R8_ORIGIN || 'http://127.0.0.1:18880';
const output = '/tmp/s01-r8-ops-save-evidence';
const fixture = JSON.parse(fs.readFileSync(path.join(output,'fixture.json'),'utf8'));
const routes = JSON.parse(fs.readFileSync('/tmp/s01-r8-ops-admin-evidence/ops-targets.json','utf8'));
const admin = routes.find(x=>x.key==='content_articles');
assert(admin, 'canonical Ops content_articles route must exist');

(async()=>{
 const browser = await chromium.launch({headless:true});
 const evidence=[], failures=[];
 try {
  for (const width of [1440,768]) {
    const context = await browser.newContext({viewport:{width,height:900}});
    const page = await context.newPage();
    const requestErrors = [];
    try {
      await page.goto(origin+'/wp-login.php',{waitUntil:'domcontentloaded',timeout:30000});
      await page.locator('#user_login').fill('synthetic');
      await page.locator('#user_pass').fill('synthetic-only-password');
      await Promise.all([
        page.waitForURL(u=>u.pathname.startsWith('/wp-admin/'),{timeout:30000}),
        page.locator('#wp-submit').click()
      ]);
      assert(await page.locator('#wpadminbar').count()>0,'not a real logged-in WordPress admin');
      const targetId=fixture.ids[String(width)];
      const title='R8 Ops Core Save Fixture '+width;
      const url=new URL(admin.url);
      assert.equal(url.origin,origin,'canonical admin must be localhost');
      url.searchParams.set('vf_content_q', title);
      const route=url.toString();
      // Allow actual user-triggered content form submissions only. A request
      // to any other write endpoint is blocked and invalidates this run.
      await context.route('**/*',async r=>{
        const req=r.request(), u=new URL(req.url());
        if(u.origin===origin && !['GET','HEAD','OPTIONS'].includes(req.method())) {
          if(req.method()==='POST' && u.pathname==='/wp-admin/admin.php' && u.searchParams.get('page')==='vf-toolsite-content') {
            await r.continue();return;
          }
          requestErrors.push({method:req.method(),path:u.pathname});
          await r.abort('blockedbyclient');return;
        }
        await r.continue();
      });
      const getRow=()=>page.locator('.vf-content-manager-row').filter({hasText:title});
      const getAction=action=>getRow().locator('form.vf-content-manager-inline-action').filter({
        has:page.locator('input[name="vf_ops_content_management_action"][value="'+action+'"]')
      });
      async function openRowAndGet(action) {
        assert.equal(await getRow().count(),1,'exact isolated post row missing or duplicated');
        await getRow().locator('[data-vf-content-more]').click();
        const form=getAction(action);
        assert.equal(await form.count(),1,'real form '+action+' missing');
        assert.equal(await form.locator('input[name="post_id"]').inputValue(),String(targetId),'form targets wrong post');
        assert(await form.locator('input[name="_vf_ops_content_nonce"]').inputValue(),'real WordPress Nonce missing');
        return form;
      }
      async function readback(expectedCore) {
        await page.goto(route,{waitUntil:'domcontentloaded',timeout:40000});
        assert.equal(await page.locator('[data-vf-v13-route="content_articles"]').count(),1,'wrong Ops page after readback');
        assert.equal(await getRow().count(),1,'target post missing after independent GET');
        assert.equal(await getRow().evaluate(el=>el.classList.contains('is-core')),expectedCore,'independent GET core state mismatch');
        if(expectedCore){
          assert.equal(await getRow().locator('.vf-content-manager-row-lock').count(),1,'core content did not enforce row lock');
          assert.equal(await getRow().locator('.vf-content-manager-row-check').count(),0,'protected core is still eligible for bulk action');
        }else{
          assert.equal(await getRow().locator('.vf-content-manager-row-check').count(),1,'normal content selection not restored');
        }
      }
      await readback(false);
      let mark=await openRowAndGet('mark_core');
      const startStatus=await Promise.all([
        page.waitForNavigation({waitUntil:'domcontentloaded',timeout:40000}),
        mark.locator('button[type="submit"]').click()
      ]);
      assert.equal(startStatus[0]?.status(),200,'mark action must return a valid post-redirect page');
      await readback(true);
      evidence.push({width,step:'mark_core_write_then_independent_GET',status:'PASS'});
      const unmark=await openRowAndGet('unmark_core');
      const unmarkResponse=await Promise.all([
        page.waitForNavigation({waitUntil:'domcontentloaded',timeout:40000}),
        unmark.locator('button[type="submit"]').click()
      ]);
      assert.equal(unmarkResponse[0]?.status(),200,'unmark action must return valid post-redirect page');
      await readback(false);
      evidence.push({width,step:'unmark_core_rollback_then_independent_GET',status:'PASS'});
      mark=await openRowAndGet('mark_core');
      await mark.locator('input[name="_vf_ops_content_nonce"]').evaluate(el=>{el.value='invalid-nonce-r8';});
      const blocked=await Promise.all([
        page.waitForNavigation({waitUntil:'domcontentloaded',timeout:40000}),
        mark.locator('button[type="submit"]').click()
      ]);
      const deniedStatus=blocked[0]?.status();
      assert.equal(deniedStatus,403,'invalid WordPress nonce must produce HTTP 403');
      await readback(false);
      evidence.push({width,step:'invalid_nonce_HTTP_403_zero_write',status:'PASS'});
      assert.deepEqual(requestErrors,[],'unplanned automatic or redirected write requests detected');
      await page.screenshot({path:path.join(output,'content-'+width+'-roundtrip.png'),fullPage:true});
    }catch(e){
      failures.push({width,error:String(e.stack||e),blockedRequests:requestErrors});
    }finally{
      await context.close();
    }
  }
 }finally{await browser.close();}
 const result={scope:'real Ops content form POST, independent GET and nonce denial; isolated fixture only',
    total:6,passed:evidence.length,failed:failures.length,evidence,failures};
 fs.writeFileSync(path.join(output,'content-browser-results.json'),JSON.stringify(result,null,2));
 console.log('S01_R8_OPS_CONTENT_REAL_WRITE_READBACK '+JSON.stringify(result));
 assert.equal(failures.length,0,'actual Ops content write/readback or fail-closed case failed');
 assert.equal(evidence.length,6,'missing one or more real-width workflow readbacks');
})().catch(e=>{console.error(e?.stack||e);process.exitCode=1;});
