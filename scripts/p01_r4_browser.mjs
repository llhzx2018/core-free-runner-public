import { chromium } from 'playwright';
import { readFileSync } from 'node:fs';

const port=process.env.TARGET_PORT || process.env.target_port;
const base='http://127.0.0.1:'+port+'/';
const credential=process.env.P01_R4_TEST_CRED;
const fixture=JSON.parse(readFileSync('/tmp/p01-r4-fixture.json','utf8'));

const browser=await chromium.launch({headless:true});
const failures=[];
const assert=(ok,label)=>{
  if(ok)console.log('R4_BROWSER_PASS '+label);
  else{console.log('R4_BROWSER_FAIL '+label);failures.push(label);}
};
const attachErrors=page=>{
  const errors=[];
  page.on('pageerror',e=>errors.push(String(e)));
  return errors;
};
const noOverflow=async page=>page.evaluate(
  ()=>Math.max(document.documentElement.scrollWidth,document.body?.scrollWidth||0)<=window.innerWidth+4
);

try{
  const publicCtx=await browser.newContext({viewport:{width:1440,height:900}});
  const publicPage=await publicCtx.newPage();
  const publicErrors=attachErrors(publicPage);
  const publicRoutes=[
    '', 'start.php', 'channels.php', 'watch.php', 'topics.php', 'courses.php',
    'projects.php', 'tools.php?q=R4+Browser+SEO+Tool', 'software.php?q=R4+Browser+Search+Software'
  ];
  for(const route of publicRoutes){
    publicErrors.length=0;
    const response=await publicPage.goto(base+route,{waitUntil:'networkidle'});
    assert(Boolean(response)&&response.status()<500,'desktop_status_'+(route||'index'));
    assert(await noOverflow(publicPage),'desktop_no_overflow_'+(route||'index'));
    assert(publicErrors.length===0,'desktop_no_pageerror_'+(route||'index'));
  }
  assert((await publicPage.locator('body').innerText()).includes('R4 Browser Search Software'),'software_fixture_visible');

  const topicResponse=await publicPage.goto(base+'resource-html.php?id='+fixture.topic,{waitUntil:'domcontentloaded'});
  assert(topicResponse?.status()===200,'hosted_html_status');
  assert((await publicPage.locator('body').innerText()).includes('R4 Hosted Browser Body'),'hosted_html_body');
  await publicCtx.close();

  const mobileCtx=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
  const mobilePage=await mobileCtx.newPage();
  const mobileErrors=attachErrors(mobilePage);
  const mobileRoutes=[
    'start.php','channels.php','watch.php','topics.php','courses.php','projects.php',
    'tools.php?q=R4+Browser+SEO+Tool','software.php?q=R4+Browser+Search+Software'
  ];
  for(const route of mobileRoutes){
    mobileErrors.length=0;
    const response=await mobilePage.goto(base+route,{waitUntil:'networkidle'});
    assert(Boolean(response)&&response.status()<500,'mobile_status_'+route);
    assert(await noOverflow(mobilePage),'mobile_no_overflow_'+route);
    assert(mobileErrors.length===0,'mobile_no_pageerror_'+route);
  }
  await mobileCtx.close();

  const adminCtx=await browser.newContext({viewport:{width:1440,height:900}});
  const page=await adminCtx.newPage();
  const adminErrors=attachErrors(page);
  await page.goto(base,{waitUntil:'networkidle'});
  await page.click('[data-vf-auth-login]');
  await page.fill('[data-vf-auth-dialog] input[name="password"]',credential);
  await Promise.all([
    page.waitForNavigation({waitUntil:'networkidle'}),
    page.click('[data-vf-auth-submit]')
  ]);
  assert((await page.locator('[data-vf-auth-logout]').count())>0,'login_ui_success');

  const adminRoutes=['manage.php','surface-manager.php','settings.php','full-governance.php','plugins.php','browser-helper.php','update.php'];
  for(const route of adminRoutes){
    adminErrors.length=0;
    const response=await page.goto(base+route,{waitUntil:'networkidle'});
    assert(Boolean(response)&&response.status()===200,'admin_status_'+route);
    assert(adminErrors.length===0,'admin_no_pageerror_'+route);
  }

  await page.goto(base+'start.php',{waitUntil:'networkidle'});
  const favorite='[data-favorite-id="'+fixture.tool+'"]';
  const row='[data-asset-row="'+fixture.tool+'"]';
  const actionTrigger=row+' .vf-action-menu-trigger';
  assert((await page.locator(favorite).count())===1,'favorite_control_present');
  assert((await page.locator(actionTrigger).count())===1,'secondary_action_menu_present');
  await page.click(actionTrigger);
  await page.locator(favorite).waitFor({state:'visible'});
  await page.click(favorite);
  await page.waitForFunction(sel=>document.querySelector(sel)?.dataset.favorite==='1',favorite);
  assert(await page.locator(favorite).getAttribute('data-favorite')==='1','favorite_mutation_updates_ui');

  const logoutResult=await page.evaluate(async()=>{
    const boot=await fetch('api.php?action=bootstrap',{credentials:'same-origin'}).then(r=>r.json());
    const r=await fetch('api.php?action=logout',{
      method:'POST',
      credentials:'same-origin',
      headers:{'Content-Type':'application/json','X-CSRF-Token':String(boot.csrf||'')},
      body:'{}'
    });
    return {status:r.status,json:await r.json().catch(()=>({}))};
  });
  assert(logoutResult.status===200&&logoutResult.json.ok===true,'logout_api_success');

  await page.click(actionTrigger);
  await page.locator(favorite).waitFor({state:'visible'});
  await page.click(favorite);
  await page.waitForSelector('[data-vf-auth-dialog][open]',{state:'visible',timeout:5000});
  assert(await page.locator('[data-vf-auth-dialog][open]').isVisible(),'expired_session_opens_login_dialog');
  await adminCtx.close();

  const mobileAdminCtx=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
  const m=await mobileAdminCtx.newPage();
  const me=attachErrors(m);
  await m.goto(base,{waitUntil:'networkidle'});
  await m.click('[data-vf-auth-login]');
  await m.fill('[data-vf-auth-dialog] input[name="password"]',credential);
  await Promise.all([
    m.waitForNavigation({waitUntil:'networkidle'}),
    m.click('[data-vf-auth-submit]')
  ]);
  for(const route of ['manage.php','surface-manager.php','settings.php']){
    me.length=0;
    const response=await m.goto(base+route,{waitUntil:'networkidle'});
    assert(Boolean(response)&&response.status()===200,'mobile_admin_status_'+route);
    assert(await noOverflow(m),'mobile_admin_no_overflow_'+route);
    assert(me.length===0,'mobile_admin_no_pageerror_'+route);
  }
  await mobileAdminCtx.close();

  if(failures.length)throw new Error('R4 browser failures: '+failures.join(', '));
  console.log('P01_R4_REAL_BROWSER=PASS');
}finally{
  await browser.close();
}
