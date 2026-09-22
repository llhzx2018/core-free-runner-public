import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';

const port=process.env.TARGET_PORT || process.env.target_port;
const localBase='http://127.0.0.1:'+port+'/';
const prodBase='https://start.kewaro.com/';
const credential=process.env.P01_UXUI_TEST_CRED;
const out='/tmp/p01-uxui-screens';
mkdirSync(out,{recursive:true});

const browser=await chromium.launch({headless:true});
const results=[];
const failures=[];

const slug=(s)=>s.replace(/^https?:\/\//,'').replace(/[^a-zA-Z0-9_-]+/g,'_').replace(/^_+|_+$/g,'').slice(0,120) || 'index';

function record(kind,route,data){
  results.push({kind,route,...data});
}
function fail(label,detail=''){
  failures.push({label,detail});
  console.log('UXUI_AUDIT_FAIL',label,detail);
}

async function activeDomainVisible(page){
  return await page.evaluate(()=>{
    const links=document.querySelector('.vf-global-domain-links');
    const active=links?.querySelector('a.active');
    if(!links||!active)return {ok:false,reason:'missing'};
    const lr=links.getBoundingClientRect();
    const ar=active.getBoundingClientRect();
    return {
      ok:ar.left>=lr.left-1&&ar.right<=lr.right+1,
      active:String(active.textContent||'').trim(),
      marker:links.dataset.vfActiveDomainVisible||'',
      scrollLeft:links.scrollLeft,
      scrollWidth:links.scrollWidth,
      clientWidth:links.clientWidth
    };
  });
}

async function metrics(page){
  return await page.evaluate(()=>{
    const q=(s)=>document.querySelector(s);
    const rect=(el)=>el?el.getBoundingClientRect():null;
    const cs=(el)=>el?getComputedStyle(el):null;
    const h1=q('h1');
    const header=q('.vf-admin-header');
    const rail=q('.vf-admin-rail');
    const main=q('.vf-admin-main');
    const buttons=[...document.querySelectorAll('button,.btn,a.btn')].filter(el=>{
      const s=getComputedStyle(el); const r=el.getBoundingClientRect();
      return s.display!=='none' && s.visibility!=='hidden' && r.width>0 && r.height>0;
    }).slice(0,40);
    const navItems=[...document.querySelectorAll('.vf-rail-item,.vf-rail-subitem')].map(el=>el.getBoundingClientRect().height);
    return {
      title:document.title,
      bodyText:(document.body?.innerText||'').slice(0,500),
      overflowX:Math.max(document.documentElement.scrollWidth,document.body?.scrollWidth||0)-window.innerWidth,
      viewport:{width:window.innerWidth,height:window.innerHeight},
      h1:h1?{text:h1.textContent?.trim()||'',fontSize:cs(h1)?.fontSize,lineHeight:cs(h1)?.lineHeight,fontWeight:cs(h1)?.fontWeight,height:rect(h1)?.height}:null,
      header:header?{height:rect(header)?.height,marginBottom:cs(header)?.marginBottom,paddingBottom:cs(header)?.paddingBottom}:null,
      rail:rail?{width:rect(rail)?.width}:null,
      main:main?{width:rect(main)?.width,paddingLeft:cs(main)?.paddingLeft,paddingRight:cs(main)?.paddingRight}:null,
      visibleButtonHeights:buttons.map(el=>Math.round(el.getBoundingClientRect().height)),
      navItemHeights:navItems.map(v=>Math.round(v)),
      panelCount:document.querySelectorAll('.panel,.card').length,
      dialogCount:document.querySelectorAll('dialog').length,
      detailsCount:document.querySelectorAll('details').length,
      url:location.href
    };
  });
}

async function capture(page,kind,route,base,namePrefix){
  const errors=[];
  page.removeAllListeners('pageerror');
  page.on('pageerror',e=>errors.push(String(e)));
  let response=null;
  try{
    response=await page.goto(base+route,{waitUntil:'networkidle',timeout:45000});
  }catch(e){
    fail(kind+'_NAV_'+route,String(e));
  }
  const m=await metrics(page).catch(()=>({error:'metrics failed'}));
  const status=response?.status() ?? 0;
  const file=path.join(out,namePrefix+'-'+slug(route||'index')+'.png');
  await page.screenshot({path:file,fullPage:true});
  record(kind,route,{status,errors,metrics:m,screenshot:path.basename(file)});
  if(status>=500 || status===0) fail(kind+'_STATUS_'+route,String(status));
  if(errors.length) fail(kind+'_PAGEERROR_'+route,errors.join(' | '));
  if(typeof m.overflowX==='number' && m.overflowX>4) fail(kind+'_OVERFLOW_'+route,String(m.overflowX));
}

try{
  // Production public surfaces: real content density, no private/admin access.
  for(const viewport of [
    {name:'prod-desktop',opts:{viewport:{width:1440,height:960}}},
    {name:'prod-mobile',opts:{viewport:{width:390,height:844},isMobile:true,hasTouch:true}}
  ]){
    const ctx=await browser.newContext(viewport.opts);
    const page=await ctx.newPage();
    const routes=['','start.php','channels.php','watch.php','topics.php','courses.php','projects.php','tools.php','software.php'];
    for(const route of routes) await capture(page,viewport.name,route,prodBase,viewport.name);
    await ctx.close();
  }

  // Exact-source candidate public surfaces: same page denominator as Production,
  // but rendered from the PR head against synthetic public data.
  for(const viewport of [
    {name:'candidate-public-desktop',opts:{viewport:{width:1440,height:960}}},
    {name:'candidate-public-mobile',opts:{viewport:{width:390,height:844},isMobile:true,hasTouch:true}}
  ]){
    const ctx=await browser.newContext(viewport.opts);
    const page=await ctx.newPage();
    const routes=['','start.php','channels.php','watch.php','topics.php','courses.php','projects.php','tools.php','software.php'];
    for(const route of routes){
      await capture(page,viewport.name,route,localBase,viewport.name);
      if(viewport.name==='candidate-public-mobile'){
        const visible=await activeDomainVisible(page);
        record('candidate-mobile-domain',route,visible);
        if(!visible.ok)fail('CANDIDATE_MOBILE_ACTIVE_DOMAIN_'+(route||'index'),JSON.stringify(visible));
        if(route==='software.php'&&visible.marker!=='1')fail('CANDIDATE_SOFTWARE_ACTIVE_DOMAIN_MARKER',JSON.stringify(visible));
      }
    }
    await ctx.close();
  }

  // Exact-source local runtime admin.
  const adminCtx=await browser.newContext({viewport:{width:1440,height:960}});
  const admin=await adminCtx.newPage();
  await admin.goto(localBase,{waitUntil:'networkidle'});
  await admin.click('[data-vf-auth-login]');
  await admin.fill('[data-vf-auth-dialog] input[name="password"]',credential);
  await Promise.all([
    admin.waitForNavigation({waitUntil:'networkidle'}),
    admin.click('[data-vf-auth-submit]')
  ]);

  const ownerRoutes=['index.php','start.php','channels.php','watch.php','topics.php','courses.php','projects.php','tools.php','software.php'];
  for(const route of ownerRoutes) await capture(admin,'owner-desktop',route,localBase,'owner-desktop');

  // Shared owner interaction states belong to the UX/UI denominator too.
  await admin.goto(localBase+'start.php',{waitUntil:'networkidle'});
  if(await admin.locator('[data-open-add]').count()){
    await admin.locator('[data-open-add]').first().click();
    await admin.locator('[data-panel="add"]:not([hidden])').waitFor({state:'visible',timeout:5000});
    await admin.screenshot({path:path.join(out,'owner-desktop-start-add-dialog.png'),fullPage:true});
    record('owner-interaction','start-add-dialog',{status:200,screenshot:'owner-desktop-start-add-dialog.png'});
    const close=admin.locator('[data-panel="add"] [data-close-panel]').first();
    if(await close.count())await close.click();
  }
  await admin.goto(localBase+'start.php',{waitUntil:'networkidle'});
  await admin.keyboard.press('Control+K').catch(()=>{});
  if(await admin.locator('.vf-quick-open:not([hidden])').count()){
    await admin.screenshot({path:path.join(out,'owner-desktop-quick-open.png'),fullPage:true});
    record('owner-interaction','quick-open',{status:200,screenshot:'owner-desktop-quick-open.png'});
    await admin.keyboard.press('Escape').catch(()=>{});
  }

  const adminRoutes=[
    'manage.php',
    'surface-manager.php',
    'surface-manager.php?advanced=1',
    'links-admin.php',
    'health.php',
    'recycle-bin.php',
    'transfer.php',
    'data-safety.php',
    'full-governance.php',
    'system-health.php',
    'plugins.php',
    'browser-helper.php',
    'update.php',
    'update-credential.php',
    'settings.php',
    'system-info.php',
    'system-baseline.php'
  ];
  for(const route of adminRoutes) await capture(admin,'admin-desktop',route,localBase,'admin-desktop');
  await adminCtx.close();

  // Mobile admin: all first-level destinations plus the densest resource/data/settings surfaces.
  const mobileCtx=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
  const m=await mobileCtx.newPage();
  await m.goto(localBase,{waitUntil:'networkidle'});
  await m.click('[data-vf-auth-login]');
  await m.fill('[data-vf-auth-dialog] input[name="password"]',credential);
  await Promise.all([
    m.waitForNavigation({waitUntil:'networkidle'}),
    m.click('[data-vf-auth-submit]')
  ]);
  for(const route of ['index.php','start.php','channels.php','watch.php','topics.php','courses.php','projects.php','tools.php','software.php']){
    await capture(m,'owner-mobile',route,localBase,'owner-mobile');
  }
  const mobileAdminRoutes=[
    'manage.php','surface-manager.php','surface-manager.php?advanced=1','links-admin.php',
    'transfer.php','data-safety.php','system-health.php','plugins.php',
    'browser-helper.php','update.php','settings.php'
  ];
  for(const route of mobileAdminRoutes) await capture(m,'admin-mobile',route,localBase,'admin-mobile');
  await mobileCtx.close();

  // Compatibility/orphan audit: these should converge, not own a second visual shell.
  const compatCtx=await browser.newContext({viewport:{width:1280,height:800}});
  const cp=await compatCtx.newPage();
  await cp.goto(localBase,{waitUntil:'networkidle'});
  await cp.click('[data-vf-auth-login]');
  await cp.fill('[data-vf-auth-dialog] input[name="password"]',credential);
  await Promise.all([cp.waitForNavigation({waitUntil:'networkidle'}),cp.click('[data-vf-auth-submit]')]);
  const compat=[
    'affiliate.php','governance.php','icons.php','jobs.php','security.php','tags.php',
    'data.php','resources.php','system.php','workbench.php'
  ];
  for(const route of compat){
    const res=await cp.goto(localBase+route,{waitUntil:'networkidle'});
    const finalUrl=cp.url();
    record('compat',route,{status:res?.status()??0,finalUrl});
    if((res?.status()??0)>=500) fail('COMPAT_STATUS_'+route,String(res?.status()));
  }
  await compatCtx.close();

  writeFileSync(path.join(out,'visual-audit.json'),JSON.stringify({
    source:{sha:'73bdfa38310aaabcf6df48810fe8479024a1a819',tree:'516a2d9ec341910859e7777195ace6e8900c6f7d',version:'2.47.40'},
    counts:{
      productionPublicDesktop:results.filter(x=>x.kind==='prod-desktop').length,
      productionPublicMobile:results.filter(x=>x.kind==='prod-mobile').length,
      candidatePublicDesktop:results.filter(x=>x.kind==='candidate-public-desktop').length,
      candidatePublicMobile:results.filter(x=>x.kind==='candidate-public-mobile').length,
      candidateMobileDomainChecks:results.filter(x=>x.kind==='candidate-mobile-domain').length,
      ownerDesktop:results.filter(x=>x.kind==='owner-desktop').length,
      ownerMobile:results.filter(x=>x.kind==='owner-mobile').length,
      ownerInteractions:results.filter(x=>x.kind==='owner-interaction').length,
      adminDesktop:results.filter(x=>x.kind==='admin-desktop').length,
      adminMobile:results.filter(x=>x.kind==='admin-mobile').length,
      compatibility:results.filter(x=>x.kind==='compat').length
    },
    failures,results
  },null,2));

  console.log('P01_UXUI_SCREENSHOT_COUNT='+results.filter(x=>x.screenshot).length);
  console.log('P01_UXUI_COMPAT_COUNT='+results.filter(x=>x.kind==='compat').length);
  console.log('P01_UXUI_VISUAL_BASELINE='+(failures.length?'FAIL':'PASS'));
  if(failures.length) process.exitCode=2;
}finally{
  await browser.close();
}
