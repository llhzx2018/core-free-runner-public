'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const {chromium}=require(path.join(process.env.S01_BROWSER_NODE_MODULES,'playwright'));
let browser;
(async()=>{
 const base=process.env.S01_BROWSER_BASE_URL;
 assert.equal(base,'http://127.0.0.1:18106','Only the disposable local WordPress test origin is allowed');
 const phase=process.env.S01_COVERAGE_PHASE;assert.ok(['clean','issue'].includes(phase));
 const out=process.argv[2];fs.mkdirSync(path.join(out,'browser'),{recursive:true});
 browser=await chromium.launch({headless:true});
 const context=await browser.newContext({viewport:{width:1440,height:960}});
 await context.route('**/*',route=>new URL(route.request().url()).origin===base?route.continue():route.abort());
 const page=await context.newPage();const errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 async function login(p,user,password){
  await p.goto(base+'/wp-login.php',{waitUntil:'domcontentloaded'});
  assert.equal(new URL(p.url()).origin,base);
  await p.locator('#user_login').fill(user);await p.locator('#user_pass').fill(password);
  await Promise.all([p.waitForURL(/\/wp-admin\//),p.locator('#wp-submit').click()]);
  assert.ok(await p.locator('#wpadminbar').count());
 }
 await login(page,'admin','S01-Synthetic-Install-Only!');errors.length=0;
 const proof={result:'PASS',candidate_sha:process.env.TARGET_SHA,phase,widths:[],
  actual_wordpress:true,polylang_pro:'3.8.2',production_write:false,owner_product_acceptance:'PENDING'};
 let nonce='';
 for(const width of [1440,1024,768,390]){
  await page.setViewportSize({width,height:width===390?844:960});
  let postCount=0;const observe=r=>{if(r.method()==='POST')++postCount;};
  page.on('request',observe);
  await page.goto(base+'/wp-admin/tools.php?page=s01-language-guard-fixture',{waitUntil:'networkidle'});
  const root=page.locator('.vf-multilingual-slug-cleaner');await root.waitFor({state:'visible'});
  const coverage=root.locator('.vf-ml-cleaner-scan-coverage');
  assert.match(await coverage.innerText(),/本次已检查 500 个对象.*仍有对象尚未检查/);
  assert.match(await coverage.innerText(),/不能认定全站无异常/);
  assert.equal(await page.locator('#s01-browser-control').getAttribute('data-render-writes'),'0');
  assert.equal(await page.locator('#s01-browser-control').getAttribute('data-preserved'),'1');
  if(phase==='clean'){
   assert.match(await root.innerText(),/本批未发现语言覆盖异常；扫描尚未覆盖全部对象/);
   assert.doesNotMatch(await root.innerText(),/当前没有语言覆盖 异常/);
   assert.equal(await root.locator('[data-vf-action-id="multilingual-slug-cleaner-repair-all"]').count(),0);
  }else{
   const repair=root.locator('[data-vf-action-id="multilingual-slug-cleaner-repair-all"]');
   assert.equal(await repair.count(),1);assert.equal(await repair.isDisabled(),false);
   const form=repair.locator('xpath=ancestor::form');const check=form.locator('[name="vf_ops_confirm_multilingual_write"]');
   assert.equal(await check.isChecked(),false);assert.equal(await check.getAttribute('required'),'');
   nonce=await form.locator('[name="_wpnonce"]').inputValue();
   await repair.click();assert.equal(postCount,0,'HTML confirmation must prevent accidental POST');
   await check.focus();assert.equal(await check.evaluate(x=>x===document.activeElement),true);
   await page.keyboard.press('Space');assert.equal(await check.isChecked(),true);
   await page.keyboard.press('Space');assert.equal(await check.isChecked(),false);
   const table=root.locator('.vf-ml-cleaner-table-wrap');
   await table.focus();assert.equal(await table.evaluate(x=>x===document.activeElement),true);
   assert.match(await table.innerText(),/s01-browser-collision-2/);
  }
  page.off('request',observe);assert.equal(postCount,0,'GET and local controls never start a write request');
  const geometry=await root.evaluate(el=>{
   const r=el.getBoundingClientRect();const c=el.querySelector('.vf-ml-cleaner-scan-coverage').getBoundingClientRect();
   return {x:r.x,right:r.right,width:r.width,viewport:innerWidth,documentWidth:document.documentElement.scrollWidth,
    coverageRight:c.right,coverageHeight:c.height};
  });
  assert.ok(geometry.x>=-1&&geometry.right<=width+2,'root remains inside viewport');
  assert.ok(geometry.documentWidth<=width+2,'no whole-page horizontal overflow');
  assert.ok(geometry.coverageRight<=width+2&&geometry.coverageHeight>0,'coverage notice stays visible');
  await root.screenshot({path:path.join(out,'browser','slug-'+phase+'-'+width+'.png')});
  proof.widths.push({width,geometry,renderer_sql_writes:0,content_preserved:true,confirmation_guard:phase==='issue'});
 }
 if(phase==='issue'){
  const endpoint=base+'/wp-admin/admin-post.php?action=s01_language_guard_fixture';
  function form(payload){const f={action:'s01_language_guard_fixture'};
   for(const[k,v]of Object.entries(payload))f['s01_payload['+k+']']=String(v);return f;}
  let cases=0;
  async function reject(ctx,payload,status){
   const response=await ctx.request.post(endpoint,{form:form(payload),maxRedirects:0});
   assert.equal(response.status(),200);const data=await response.json();
   assert.equal(data.status,status);assert.equal(data.sql_writes,0);
   assert.equal(data.page_write_queries,0);assert.equal(data.content_preserved,true);++cases;
  }
  const getData=await(await context.request.get(endpoint,{maxRedirects:0})).json();
  assert.equal(getData.status,'NULL');assert.equal(getData.sql_writes,0);++cases;
  await reject(context,{vf_ops_multilingual_slug_cleaner_action:'repair_all',_wpnonce:'invalid-synthetic-nonce',vf_ops_confirm_multilingual_write:'1'},'FAIL');
  await reject(context,{vf_ops_multilingual_slug_cleaner_action:'repair_all',vf_ops_confirm_multilingual_write:'1'},'FAIL');
  for(const action of ['repair_selected','repair_all','trash_archived_duplicates','rollback_last_batch'])
   await reject(context,{vf_ops_multilingual_slug_cleaner_action:action,_wpnonce:nonce},'BLOCKED');
  for(const confirm of ['0','true','yes'])
   await reject(context,{vf_ops_multilingual_slug_cleaner_action:'repair_all',_wpnonce:nonce,vf_ops_confirm_multilingual_write:confirm},'BLOCKED');
  const editor=await browser.newContext();
  await editor.route('**/*',r=>new URL(r.request().url()).origin===base?r.continue():r.abort());
  await login(await editor.newPage(),'s01-synthetic-editor','S01-Synthetic-Editor-Only!');
  const editorNonce=(await(await editor.request.get(endpoint+'&phase=nonce')).json()).nonce;
  await reject(editor,{vf_ops_multilingual_slug_cleaner_action:'repair_all',_wpnonce:editorNonce,vf_ops_confirm_multilingual_write:'1'},'FAIL');
  await editor.close();assert.equal(cases,11);proof.native_http_rejection_cases=cases;
 }
 assert.deepEqual(errors,[],'source-owned component raises no browser exceptions');
 fs.writeFileSync(path.join(out,'SLUG_BROWSER_'+phase+'.json'),JSON.stringify(proof,null,2)+'\n');
 await context.close();await browser.close();console.log('S01_SLUG_BROWSER_PASS '+phase);
})().catch(async e=>{console.error('S01_SLUG_BROWSER_FAIL',e.stack);if(browser)await browser.close();process.exitCode=1;});
