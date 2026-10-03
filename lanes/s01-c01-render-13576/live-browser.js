'use strict';
const fs=require('fs'),path=require('path'),assert=require('assert/strict'),{execFileSync}=require('child_process'),{chromium}=require('playwright');
const check=require('../target/tests/render-controls-browser-check'),base='http://127.0.0.1:18880',url=base+'/wp-admin/themes.php?page=vf-theme-modules&tab=render';
const cli=php=>execFileSync('docker',['exec','--user','www-data','vf-v8-'+process.env.GITHUB_RUN_ID+'-wp','php','/usr/local/bin/wp','eval',php,'--path=/var/www/html'],{encoding:'utf8',stdio:['ignore','pipe','pipe']});
(async()=>{
 const browser=await chromium.launch({headless:true}),context=await browser.newContext(),page=await context.newPage(),errors=[];
 page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
 await page.goto(base+'/wp-login.php');await page.locator('#user_login').fill('admin');await page.locator('#user_pass').fill('Synthetic-Only-Update-54!');await Promise.all([page.waitForURL(/wp-admin/),page.locator('#wp-submit').click()]);
 const checks=[];
 for(const width of [1920,1440,1319,1024,768,390]){
  await page.setViewportSize({width,height:1000});await page.goto(url);await page.locator('[data-vf-render-enhanced]').waitFor();
  assert.equal(await page.locator('[data-vf-render-status]').getAttribute('data-status'),'pass','native canonical runtime is falsely blocked');
  checks.push(await check(page,{width,out:path.resolve('proof'),screenshots:true}));
 }
 await page.setViewportSize({width:1440,height:1000});await page.goto(url);
 const root=page.locator('[data-vf-render-page]'),form=root.locator('form'),save=root.locator('[data-vf-render-save]'),advanced=root.locator('[data-vf-render-advanced]');
 await form.locator('[name="renderer[defaultMode]"]').selectOption('HYBRID');
 await form.locator('[name="renderer[inputLayout]"]').selectOption('SPLIT_WHEN_SAFE');
 await form.locator('[name="renderer[parameterLayout]"]').selectOption('VISIBLE');
 await form.locator('[name="renderer[progressPresentation]"]').selectOption('STAGE_ONLY');
 await form.locator('[name="renderer[mobileFallback]"]').selectOption('BLOCK_UNSUPPORTED_WIDGET');
 await form.locator('input[type=checkbox]').uncheck();
 await advanced.locator('summary').click();
 await form.locator('[name="renderer[primitiveProfile]"]').fill('VF_TOOLS_STANDARD_V1_TEST');
 let release;const gate=new Promise(r=>release=r);
 await page.route('**/admin-ajax.php',async route=>{await gate;await route.continue();});
 const response=page.waitForResponse(r=>r.url().includes('admin-ajax.php')&&r.request().method()==='POST');
 await save.click();await page.waitForFunction(()=>document.querySelector('[data-vf-render-page]').getAttribute('aria-busy')==='true');
 assert.equal(await form.locator('select:not(:disabled),input[type=text]:not(:disabled),input[type=checkbox]:not(:disabled)').count(),0,'fields remain editable during save');
 assert(await save.isDisabled());await page.screenshot({path:'proof/render-saving-1440.png',fullPage:true});release();
 const saved=await response,payload=await saved.json();assert(saved.ok()&&payload.success&&payload.data.ok,'native AJAX save failed');
 await page.waitForFunction(()=>!document.querySelector('[data-vf-render-page]').classList.contains('is-dirty'));
 assert.equal(await save.isVisible(),false);assert.equal(await root.locator('[data-vf-render-status]').getAttribute('data-status'),'pass');
 assert.equal(await form.locator('select:disabled,input[type=text]:disabled,input[type=checkbox]:disabled').count(),0,'controls not restored after save');
 await page.unroute('**/admin-ajax.php');await page.reload();
 assert.equal(await form.locator('[name="renderer[defaultMode]"]').inputValue(),'HYBRID');
 assert.equal(await form.locator('[name="renderer[inputLayout]"]').inputValue(),'SPLIT_WHEN_SAFE');
 assert.equal(await form.locator('[name="renderer[mobileFallback]"]').inputValue(),'BLOCK_UNSUPPORTED_WIDGET');assert.equal(await form.locator('input[type=checkbox]').isChecked(),false);
 await advanced.locator('summary').click();assert.equal(await form.locator('[name="renderer[primitiveProfile]"]').inputValue(),'VF_TOOLS_STANDARD_V1_TEST');
 assert.equal(await root.locator('[data-vf-render-contract-revision]').innerText(),payload.data.state.revision.slice(0,12),'visible revision stale after reload');
 // A transport failure must keep the typed draft, all status locations and controls usable.
 const profile=form.locator('[name="renderer[primitiveProfile]"]');await profile.fill('UNSAVED_NETWORK_DRAFT');
 await page.route('**/admin-ajax.php',route=>route.abort('failed'));await save.click();await root.locator('[data-vf-render-save-feedback][data-tone=error]').waitFor();
 assert.equal(await profile.inputValue(),'UNSAVED_NETWORK_DRAFT');assert.equal(await root.locator('[data-vf-render-status]').getAttribute('data-status'),'error');assert(await save.isVisible()&&!await save.isDisabled());assert.equal(await profile.isDisabled(),false);
 await page.screenshot({path:'proof/render-network-error-1440.png',fullPage:true});await page.unroute('**/admin-ajax.php');
 await root.locator('[data-vf-render-discard]').click();assert.equal(await profile.inputValue(),'VF_TOOLS_STANDARD_V1_TEST');
 // Actual revision rejection through the UI keeps the new draft.
 await profile.fill('UNSAVED_CONFLICT_DRAFT');await form.locator('[name=revision]').evaluate(n=>n.value='0'.repeat(64));
 const conflictResponse=page.waitForResponse(r=>r.url().includes('admin-ajax.php')&&r.request().method()==='POST');await save.click();const conflict=await conflictResponse;assert.equal(conflict.status(),409);
 await root.locator('[data-vf-render-save-feedback][data-tone=error]').waitFor();assert((await root.locator('[data-vf-render-save-feedback]').innerText()).includes('刷新本页'));
 assert.equal(await profile.inputValue(),'UNSAVED_CONFLICT_DRAFT');await page.screenshot({path:'proof/render-conflict-1440.png',fullPage:true});await page.reload();
 const cfg=await page.evaluate(()=>({ajaxUrl:window.VFThemeRender.ajaxUrl,nonce:window.VFThemeRender.nonce}));
 const fields=await form.evaluate(n=>Object.fromEntries(new FormData(n)));fields.action='vf_theme_render_save';fields.nonce=cfg.nonce;
 const invalid=await context.request.post(cfg.ajaxUrl,{form:{...fields,'renderer[unknownField]':'1'}});assert.equal(invalid.status(),422);assert.equal((await invalid.json()).data.failureCode,'VALIDATION_FAILED');
 const csrf=await context.request.post(cfg.ajaxUrl,{form:{...fields,nonce:'invalid-nonce'}});assert(csrf.status()>=400,'invalid nonce accepted');
 const anon=await browser.newContext();const denied=await anon.request.post(cfg.ajaxUrl,{form:fields});assert(denied.status()>=400||await denied.text()==='0','guest save accepted');await anon.close();
 cli('vf_theme_bootstrap_require_many(["services/renderer-config-service.php"]);$r=vf_tools_theme_renderer_readback()["renderer"];if($r["defaultMode"]!=="HYBRID"||$r["parameterLayout"]!=="VISIBLE"||$r["progressPresentation"]!=="STAGE_ONLY"||$r["mobileFallback"]!=="BLOCK_UNSUPPORTED_WIDGET"||$r["lazyLoadRuntime"]!==false||$r["primitiveProfile"]!=="VF_TOOLS_STANDARD_V1_TEST"||$r["widgetIsolation"]!==true||$r["noJsProductContent"]!==true){throw new Exception("persisted values or failure preservation mismatch");}');
 // No-JS progressive fallback uses the unchanged native admin-post handler.
 const native=await browser.newContext({javaScriptEnabled:false,storageState:await context.storageState()}),np=await native.newPage();
 await np.goto(url);await np.locator('[name="renderer[defaultMode]"]').selectOption('STANDARD');
 await Promise.all([np.waitForURL(/vf_theme_notice=render-saved/),np.locator('[data-vf-render-save]').click()]);assert.equal(await np.locator('[name="renderer[defaultMode]"]').inputValue(),'STANDARD');await native.close();
 // Canonical incomplete result types stay visibly blocked; no success text or suppression.
 cli('vf_theme_bootstrap_require_many(["services/renderer-config-service.php"]);$r=vf_tools_theme_renderer_readback()["renderer"];update_option("vf_render_good_state",$r);$r["resultKinds"]=["SUMMARY"];update_option(vf_tools_theme_renderer_option_key(),$r,false);');
 await page.goto(url);assert.equal(await root.locator('[data-vf-render-status]').getAttribute('data-status'),'blocked');assert((await root.locator('[data-vf-render-status-summary]').innerText()).includes('需要检查'));
 await page.screenshot({path:'proof/render-true-blocked-1440.png',fullPage:true});
 cli('vf_theme_bootstrap_require_many(["services/renderer-config-service.php"]);update_option(vf_tools_theme_renderer_option_key(),get_option("vf_render_good_state"),false);');
 await page.reload();assert.equal(await root.locator('[data-vf-render-status]').getAttribute('data-status'),'pass');
 assert.equal(errors.length,0,JSON.stringify(errors));
 fs.writeFileSync('proof/live-browser.json',JSON.stringify({status:'PASS',wordpress_integration:'REAL_ISOLATED_WORDPRESS',checks,persistence:'PASS',invalid_contract:'PASS',csrf:'PASS',guest:'PASS',revision_conflict:'PASS',network_failure:'PASS',busy_lock:'PASS',native_post:'PASS',true_blocked_state:'PASS',errors},null,2));
 await browser.close();console.log('RENDER_NATIVE_BROWSER=PASS');
})().catch(e=>{console.error(e);process.exit(1);});

