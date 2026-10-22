'use strict';
const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch();
 try{
  const page=await browser.newPage();
  const base='http://127.0.0.1:18880';
  page.on('dialog',d=>d.accept());
  await page.goto(base+'/wp-login.php');
  await page.locator('#user_login').fill('admin');
  await page.locator('#user_pass').fill('Synthetic-Only-Update-54!');
  await page.locator('#wp-submit').click();
  await page.goto(base+'/wp-admin/themes.php?page=vf-theme-modules&tab=seo',{waitUntil:'networkidle'});
  const root=page.locator('[data-vf-seo-form-shell]');
  await root.waitFor({timeout:15000});
  await page.waitForFunction(()=>document.querySelector('[data-vf-seo-form-shell]')?.dataset.vfSeoEnhanced==='1');
  assert.equal(await root.getAttribute('data-vf-seo-stored'),'1');
  const rev=await root.locator('[data-vf-seo-revision]').inputValue();
  assert.equal(rev.length,64);
  const verify=root.locator('[data-vf-seo-verify]');
  assert.equal(await verify.isHidden(),false);
  const response=page.waitForResponse(r=>r.url().includes('/admin-ajax.php')&&(r.request().postData()||'').includes('vf_theme_seo_verify'));
  await verify.click();
  const data=await(await response).json();
  assert.equal(data.success,true,JSON.stringify(data.data).slice(0,400));
  assert.equal(data.data.stages.execute,'skipped');
  assert.equal(data.data.revision,rev);
  await page.waitForFunction(()=>document.querySelector('[data-vf-seo-save-feedback]').textContent.includes('未执行保存'));
  console.log('NATIVE_SEO167_READONLY_INTEGRATION_PASS');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
