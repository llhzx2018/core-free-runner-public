'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {chromium}=require(path.join(process.env.S01_BROWSER_NODE_MODULES,'playwright'));
(async()=>{
 const base=process.env.S01_BROWSER_BASE_URL;
 assert.ok(/^http:\/\/vf-s01-install-[0-9]+-wp$/.test(base),'Only disposable synthetic hostname allowed');
 const browser=await chromium.launch({headless:true});
 const proof={status:'PASS',candidate_sha:process.env.PRODUCT_SHA,production_mutated:false,
  scope:'Isolated original component view and real-handler HTTP transport',
  host_is_fixture:true,current_product_route_ui_pass:false,polylang_pro_gate:'NOT_EXECUTED',
  widths:[],http_rejection_cases:0,formal_update_discovery_tested:false,release_ready:false};
 const admin=await browser.newContext({viewport:{width:1440,height:960}});
 const page=await admin.newPage();
 const errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 async function login(p,user,password){
  await p.goto(base+'/wp-login.php',{waitUntil:'domcontentloaded'});
  await p.locator('#user_login').fill(user);
  await p.locator('#user_pass').fill(password);
  await Promise.all([p.waitForURL(/\/wp-admin\//),p.locator('#wp-submit').click()]);
  assert.ok(await p.locator('#wpadminbar').count(),'Native authenticated WordPress session required');
 }
 await login(page,'admin','S01-Synthetic-Install-Only!');
 let adminNonce='';
 for(const width of [1440,768,390]){
  await page.setViewportSize({width,height:width===390?844:960});
  await page.goto(base+'/wp-admin/tools.php?page=s01-language-guard-fixture',{waitUntil:'networkidle'});
  const root=page.locator('.vf-multilingual-slug-cleaner');
  await root.waitFor({state:'visible'});
  fs.mkdirSync('proof/browser',{recursive:true});
  await root.screenshot({path:'proof/browser/language-guard-'+width+'.png'});
  assert.match(await root.innerText(),/只导出规则不会自动安装/);
  assert.match(await root.innerText(),/暂不能自动写库/);
  assert.match(await root.innerText(),/Polylang Pro/);
  const repair=root.locator('[data-vf-action-id="multilingual-slug-cleaner-repair-all"]');
  assert.equal(await repair.count(),1,'Synthetic duplicate must produce repair UI');
  assert.equal(await repair.isDisabled(),true,'Actual no-Pro repair control must be disabled');
  const check=repair.locator('xpath=ancestor::form').locator('[name="vf_ops_confirm_multilingual_write"]');
  await check.focus();
  assert.equal(await check.evaluate(x=>x===document.activeElement),true,'Confirmation is keyboard focusable');
  await page.keyboard.press('Space');
  assert.equal(await check.isChecked(),true);
  assert.equal(await repair.isDisabled(),true,'Confirmation cannot unlock missing Pro');
  await page.keyboard.press('Space');
  assert.equal(await check.isChecked(),false);
  let postCount=0;
  const observe=req=>{if(req.method()==='POST')++postCount;};
  page.on('request',observe);
  await repair.evaluate(x=>x.click());
  page.off('request',observe);
  assert.equal(postCount,0,'Browser disabled control cannot send a write request');
  const control=page.locator('#s01-browser-control');
  assert.equal(await control.getAttribute('data-preserved'),'1');
  assert.equal(await control.getAttribute('data-render-writes'),'0','Actual component PHP GET rendering must be zero-write');
  adminNonce=await repair.locator('xpath=ancestor::form').locator('[name="_wpnonce"]').inputValue();
  const geometry=await root.evaluate(el=>{
   const rect=el.getBoundingClientRect();
   return {x:rect.x,width:rect.width,viewport:innerWidth,documentWidth:document.documentElement.scrollWidth};
  });
  assert.ok(geometry.x>=-1&&geometry.x+geometry.width<=width+2,'Component frame must remain within viewport');
  assert.ok(geometry.documentWidth<=width+2,'Component fixture must not cause page-wide horizontal overflow');
  fs.mkdirSync('proof/browser',{recursive:true});
  await root.screenshot({path:'proof/browser/language-guard-'+width+'.png'});
  proof.widths.push({width,disabled_repair:true,keyboard_confirmation:true,php_render_sql_writes:0,
   content_preserved:true,geometry});
 }
 assert.deepEqual(errors,[],'Original component script must not raise browser exceptions');
 const endpoint=base+'/wp-admin/admin-post.php?action=s01_language_guard_fixture';
 function form(payload){
  const f={action:'s01_language_guard_fixture'};
  for(const [k,v] of Object.entries(payload)){
   if(Array.isArray(v))v.forEach((x,i)=>f['s01_payload['+k+']['+i+']']=String(x));
   else f['s01_payload['+k+']']=String(v);
  }
  return f;
 }
 async function reject(context,payload,status){
  const response=await context.request.post(endpoint,{form:form(payload)});
  assert.equal(response.status(),200,'Fixture transport must execute authenticated real handler');
  const data=await response.json();
  assert.equal(data.status,status);assert.equal(data.sql_writes,0);
  assert.equal(data.page_write_queries,0);assert.equal(data.content_preserved,true);
  ++proof.http_rejection_cases;
 }
 const get=await admin.request.get(endpoint);
 const getData=await get.json();
 assert.equal(getData.status,'NULL');assert.equal(getData.sql_writes,0);assert.equal(getData.content_preserved,true);
 ++proof.http_rejection_cases;
 const editor=await browser.newContext();
 const editorPage=await editor.newPage();
 await login(editorPage,'s01-synthetic-editor','S01-Synthetic-Editor-Only!');
 const nonceResponse=await editor.request.get(endpoint+'&phase=nonce');
 const editorNonce=(await nonceResponse.json()).nonce;
 await reject(editor,{vf_ops_multilingual_slug_cleaner_action:'repair_all',_wpnonce:editorNonce,
  vf_ops_confirm_multilingual_write:'1'},'FAIL');
 await reject(admin,{vf_ops_multilingual_slug_cleaner_action:'repair_selected',_wpnonce:'invalid-synthetic-nonce',
  vf_ops_confirm_multilingual_write:'1'},'FAIL');
 await reject(admin,{vf_ops_multilingual_slug_cleaner_action:'repair_all',
  vf_ops_confirm_multilingual_write:'1'},'FAIL');
 for(const action of ['repair_selected','repair_all','trash_archived_duplicates','rollback_last_batch'])
  await reject(admin,{vf_ops_multilingual_slug_cleaner_action:action,_wpnonce:adminNonce},'BLOCKED');
 for(const confirmation of ['0','true','yes'])
  await reject(admin,{vf_ops_multilingual_slug_cleaner_action:'repair_all',_wpnonce:adminNonce,
   vf_ops_confirm_multilingual_write:confirmation},'BLOCKED');
 const anonymous=await browser.newContext();
 const anonymousResponse=await anonymous.request.post(endpoint,{form:form({vf_ops_multilingual_slug_cleaner_action:'repair_all'})});
 assert.ok([400,401,403].includes(anonymousResponse.status()),'Native unauthenticated admin-post must be rejected');
 proof.anonymous_native_denied=true;
 const authorized=await admin.request.post(endpoint,{form:form({
  vf_ops_multilingual_slug_cleaner_action:'repair_all',_wpnonce:adminNonce,vf_ops_confirm_multilingual_write:'1'})});
 const approvedData=await authorized.json();
 assert.equal(approvedData.status,'BLOCKED');
 assert.equal(approvedData.page_write_queries,0);
 assert.equal(approvedData.content_preserved,true);
 proof.authorized_no_pro_still_blocked=true;
 assert.equal(proof.http_rejection_cases,11);
 await anonymous.close();await editor.close();await admin.close();await browser.close();
 fs.writeFileSync('proof/BROWSER_HTTP.json',JSON.stringify(proof,null,2)+'\n');
 console.log('S01_C02_COMPONENT_BROWSER_HTTP_PASS '+JSON.stringify(proof));
})().catch(e=>{console.error('S01_C02_COMPONENT_BROWSER_HTTP_FAIL',e.message);process.exitCode=1;});
