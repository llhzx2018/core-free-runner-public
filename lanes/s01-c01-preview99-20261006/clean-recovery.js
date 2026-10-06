'use strict';
const fs=require('fs'),assert=require('assert/strict'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch(),context=await browser.newContext({acceptDownloads:true}),page=await context.newPage(),errors=[];page.on('pageerror',error=>errors.push(error.message));
 const base='http://127.0.0.1:18880';await page.goto(base+'/wp-login.php');await page.locator('#user_login').fill('admin');await page.locator('#user_pass').fill('Synthetic-Only-Update-54!');await Promise.all([page.waitForURL(/wp-admin/),page.locator('#wp-submit').click()]);
 for(const method of ['get','post']){const response=await context.request[method](base+'/wp-admin/install.php?step=2');assert(/Already Installed|已安装/.test(await response.text()));}
 await page.goto(base+'/wp-admin/themes.php?page=vf-theme-modules&tab=recovery');const root=page.locator('[data-vf-recovery-page]'),primary=root.locator('[data-vf-recovery-primary]');assert.equal(await root.getByRole('tab').count(),4);assert(await primary.isEnabled());assert.equal(await root.locator('[data-vf-recovery-record-count]').textContent(),'0');
 const response=page.waitForResponse(r=>r.url().includes('admin-ajax.php'));await primary.click();assert.equal((await (await response).json()).success,true);await page.waitForFunction(()=>document.querySelector('[data-vf-recovery-page]').getAttribute('aria-busy')==='false');assert.equal(await root.locator('[data-vf-recovery-record-count]').textContent(),'1');assert.equal(await root.locator('[data-vf-recovery-toast]').getAttribute('data-tone'),'success');
 await page.reload();assert.equal(await root.locator('[data-vf-recovery-record-count]').textContent(),'1');await root.locator('[data-vf-recovery-workflow-step=export]').click();const [download]=await Promise.all([page.waitForEvent('download'),primary.click()]);const payload=JSON.parse(fs.readFileSync(await download.path(),'utf8'));assert.equal(payload.version,process.env.TARGET_VERSION);assert.equal(Object.keys(payload.stores).length,7);assert.equal(errors.length,0);
 await page.screenshot({path:'proof/recovery-clean-install-1440.png',fullPage:true});fs.writeFileSync('proof/clean-install.json',JSON.stringify({status:'PASS',environment:'fresh synthetic WordPress database; exact ZIP native installation and activation',version:payload.version,first_login:'PASS',reinstall_guard_get_post:'PASS',four_tasks:'PASS',first_point:'PASS',persisted_point:'PASS',actual_download:'PASS',production:'NOT_EXECUTED',errors},null,2));await browser.close();
})().catch(error=>{console.error(error);process.exit(1)});



