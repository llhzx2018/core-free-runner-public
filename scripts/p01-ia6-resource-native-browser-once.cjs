'use strict';
// Real localhost synthetic Chromium test; no Production traffic or credentials.
const fs=require('node:fs'),path=require('node:path');
const candidate=process.argv[2],idsPath=process.argv[3];
const origin=process.env.P01_TEST_ORIGIN;
if(!/^http:\/\/127\.0\.0\.1:\d+$/.test(origin||'')||
   !candidate||!idsPath||!idsPath.startsWith('/tmp/p01-ia6-native-resource-')||
   !process.env.P01_TEST_PASSWORD)
 throw Error('P01_RESOURCE_BROWSER_LOCAL_SYNTHETIC_ONLY');
const ids=JSON.parse(fs.readFileSync(idsPath,'utf8'));
const {chromium}=require(path.resolve(candidate,'tests/integration/node_modules/playwright'));
const assert=(condition,message)=>{if(!condition)throw Error('IA6 resource browser: '+message);};
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try{
  const ctx=await browser.newContext({viewport:{width:1440,height:900}});
  await ctx.route(/https?:\/\/(?!127\.0\.0\.1)/,route=>route.abort());
  const guest=await browser.newContext();
  const guestRead=await guest.request.get(origin+'/api.php?action=resource_advanced_read&id='+ids.advanced,{maxRedirects:0});
  assert(guestRead.status()===401||guestRead.status()===403||guestRead.status()===302,
    'guest advanced read must be rejected');
  await guest.close();
  const login=await ctx.request.post(origin+'/api.php?action=login',{
   data:{password:process.env.P01_TEST_PASSWORD}
  });
  assert(login.status()===200&&(await login.text()).includes('"ok":true'),'synthetic Owner login failed');
  const page=await ctx.newPage();
  await page.goto(origin+'/start.php',{waitUntil:'domcontentloaded'});
  await page.locator('[data-vf-global-manage-open]').click({timeout:15000});
  const dialog=page.locator('[data-vf-local-management]');
  await dialog.waitFor({state:'visible'});
  const group=dialog.locator('[data-vf-global-group="resources"]');
  await group.click();
  const inv=dialog.locator('[data-vf-global-inventory-root]');
  await inv.evaluate(el=>{el.open=true;});
  await inv.locator('[data-vf-global-inventory-load]').click();
  const selected=inv.locator('[data-vf-global-inventory-select]');
  await selected.locator('option[value="'+ids.advanced+'"]').waitFor({state:'attached',timeout:15000});
  await selected.selectOption(String(ids.advanced));
  const advanced=inv.locator('[data-vf-global-advanced-editor]');
  await inv.locator('[data-vf-global-advanced-open]').click();
  await advanced.waitFor({state:'visible'});
  await advanced.locator('[data-vf-global-advanced-surface]').selectOption('channels');
  await advanced.locator('[data-vf-global-advanced-kind]').fill('IA6 synthetic channel');
  await advanced.locator('[data-vf-global-advanced-note]').fill('Private synthetic note');
  await advanced.locator('[data-vf-global-advanced-prepare]').click();
  await advanced.locator('[data-vf-global-advanced-confirm]').click();
  await advanced.waitFor({state:'hidden',timeout:20000});
  const afterAdvanced=await ctx.request.get(origin+'/api.php?action=resource_advanced_read&id='+ids.advanced);
  const advancedJSON=await afterAdvanced.json();
  assert(advancedJSON.ok===true&&advancedJSON.record?.surface==='channels'&&
    advancedJSON.record?.is_private===1&&advancedJSON.record?.resource_kind==='IA6 synthetic channel',
    'canonical advanced write did not preserve private resource and changed surface');
  console.log('P01_IA6_NATIVE_ADVANCED_RESOURCE_CHROMIUM_WRITE=PASS');
  // The new batch panel reuses the shared 60-row inventory, not the retired backend.
  await inv.locator('[data-vf-global-inventory-load]').click();
  const bulk=inv.locator('[data-vf-global-bulk-root]');
  await bulk.waitFor({state:'visible',timeout:15000});
  const checkbox=bulk.locator('input[type="checkbox"][value="'+ids.bulk+'"]');
  await checkbox.check();
  await bulk.locator('[data-vf-global-bulk-operation]').selectOption('private');
  await bulk.locator('[data-vf-global-bulk-prepare]').click();
  await bulk.locator('[data-vf-global-bulk-commit]').click();
  await page.waitForTimeout(500);
  const verify=await ctx.request.get(origin+'/api.php?action=resource_inventory&surface=all&limit=1&id='+ids.bulk);
  const result=await verify.json();
  assert(result.ok===true&&result.rows?.length===1&&result.rows[0].is_private===1,
    'bulk private mutation did not persist');
  console.log('P01_IA6_NATIVE_BULK_RESOURCE_CHROMIUM_WRITE=PASS');
  // Invalid CSRF is a true-positive protection test.
  const denied=await ctx.request.post(origin+'/api.php?action=resource_bulk_update',{
   data:{operation:'public',confirmation:'BULK_PUBLIC_CONFIRMED',entries:[{id:ids.bulk,updated_at:result.rows[0].updated_at}]},
   headers:{'Content-Type':'application/json','X-CSRF-Token':'invalid'},
   maxRedirects:0
  });
  assert(denied.status()>=400,'CSRF negative write unexpectedly accepted');
  console.log('P01_IA6_NATIVE_RESOURCE_CSRF_DENIAL=PASS');
 }finally{await browser.close();}
})().catch(err=>{console.error(String(err.stack||err));process.exitCode=1;});
