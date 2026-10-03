const fs=require('fs'),assert=require('assert/strict'),path=require('path');
const {chromium}=require('playwright');
const checkControls=require('../target/tests/update-center-controls-browser-check');
const {execFileSync}=require('child_process');
const base='http://127.0.0.1:18880',url=base+'/wp-admin/tools.php?page=vf-private-updates';
(async()=>{
 const browser=await chromium.launch({headless:true}),context=await browser.newContext(),page=await context.newPage();
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base+'/wp-login.php');await page.locator('#user_login').fill('admin');await page.locator('#user_pass').fill('Synthetic-Only-Update-54!');
 await Promise.all([page.waitForURL(/wp-admin/),page.locator('#wp-submit').click()]);
 const checks=[];
 for(const width of [1920,1440,1319,1024,768,390]){
  await page.setViewportSize({width,height:1000});await page.goto(url);await page.locator('[data-vf-update-body-v8]').waitFor();await page.evaluate(()=>document.fonts.ready);
  assert.equal(await page.locator('form form').count(),0);
  assert.equal(await page.locator('input[type=password]').evaluateAll(ns=>ns.some(n=>n.value)),false);
  const grouping=await checkControls(page,{width,out:path.resolve('proof'),screenshots:[1440,390].includes(width)});
  if(![1440,390].includes(width))await page.screenshot({path:'proof/update-default-'+width+'.png',fullPage:true});
  checks.push({width,grouping});
 }
 await page.setViewportSize({width:1440,height:1000});await page.goto(url);
 const root=page.locator('[data-vf-update-body-v8]');
 await Promise.all([page.waitForNavigation(),root.getByRole('button',{name:'检查更新',exact:true}).click()]);
 await page.waitForLoadState('load');assert(await root.isVisible());
 await page.locator('#vf-update-credentials>summary').click();
 const form=page.locator('#vf-update-credentials form').filter({has:page.locator('input[name=vf_update_token]')});
 const fields=await form.evaluate(n=>Object.fromEntries(new FormData(n)));const action=await form.getAttribute('action');
 const invalid={...fields,_wpnonce:'invalid-nonce',vf_update_token:'synthetic-wrong-token-rejected'};
 const denied=await context.request.post(action,{form:invalid});assert.equal(denied.status(),403,'invalid nonce accepted');
 const anonymous=await browser.newContext();const loggedOut=await anonymous.request.post(action,{form:{...fields,vf_update_token:'synthetic-wrong-token-rejected'}});
 assert([302,401,403,200,400].includes(loggedOut.status()));await anonymous.close();
 execFileSync('docker',['exec','--user','www-data','vf-v8-'+process.env.GITHUB_RUN_ID+'-wp','php','/usr/local/bin/wp','eval',"if(get_option('vf_private_update_credential_v1')!=='runner-private-token'){throw new Exception('credential negative changed state');}",'--path=/var/www/html'],{stdio:'pipe'});
 await page.locator('#vf_update_token').fill('runner-private-token');
 await Promise.all([page.waitForNavigation(),form.getByRole('button',{name:'保存新凭证',exact:true}).click()]);
 assert.equal(await page.locator('#vf_update_token').inputValue(),'');
 await page.locator('#vf-update-credentials>summary').click();
 const clear=page.locator('#vf-update-credentials form').filter({has:page.locator('input[value=clear_token]')});
 assert.equal(await clear.count(),1);page.once('dialog',d=>d.accept());await Promise.all([page.waitForNavigation(),clear.locator('button,input[type=submit]').click()]);
 assert(await page.locator('.vf-update-center__credential-setup').isVisible(),'credential clear did not enter setup');
 const setup=page.locator('.vf-update-center__credential-setup form');await setup.locator('input[type=password]').fill('runner-private-token');
 await Promise.all([page.waitForNavigation(),setup.locator('button,input[type=submit]').click()]);
 assert(!await page.locator('.vf-update-center__credential-setup').count(),'setup save did not return to configured page');
 await page.locator('.vf-update-center__panel--recovery>summary').click();
 let recoveryDialog=false;page.once('dialog',async d=>{recoveryDialog=true;await d.dismiss();});
 await page.locator('.vf-update-center__panel--recovery form').locator('button,input[type=submit]').click();assert(recoveryDialog,'restore confirmation absent');
 for(const name of ['WordPress 更新','管理主题']){
  await page.goto(url);const link=page.getByRole('link',{name,exact:true});assert.equal(await link.count(),1);
  await Promise.all([page.waitForNavigation(),link.click()]);assert(page.url().includes(name==='管理主题'?'themes.php':'update-core.php'));
 }
 await page.goto(url);assert.equal(await page.locator('input[type=password]').evaluateAll(ns=>ns.some(n=>n.value)),false);
 assert.equal(errors.length,0,JSON.stringify(errors));
 fs.writeFileSync('proof/live-browser.json',JSON.stringify({status:'PASS',wordpress_integration:'REAL_ISOLATED_WORDPRESS',checks,credential_save:'PASS',credential_clear:'PASS',setup_save:'PASS',invalid_nonce:'PASS',logged_out_request:'DENIED_VERIFIED_BY_NATIVE_OPTION_READBACK',check_updates:'PASS',navigation_links:'PASS',restore_confirmation_cancel:'PASS',errors},null,2));
 await browser.close();console.log('UPDATE_CENTER_NATIVE_BROWSER=PASS');
})().catch(e=>{console.error(e);process.exit(1);});
