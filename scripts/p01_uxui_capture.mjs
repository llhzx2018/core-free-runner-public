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
function assert(ok,label,detail=''){
  if(ok)console.log('UXUI_AUDIT_PASS',label);
  else fail(label,detail);
}

async function activeDomainVisible(page){
  return await page.evaluate(()=>{
    const links=document.querySelector('.vf-global-domain-links')||document.querySelector('.vf-public-home-shell nav');
    const active=links?.querySelector('a.active');
    if(!links||!active)return {ok:false,reason:'missing'};
    const lr=links.getBoundingClientRect();
    const ar=active.getBoundingClientRect();
    return {
      ok:ar.left>=lr.left-1&&ar.right<=lr.right+1,
      active:String(active.textContent||'').trim(),
      marker:links.classList.contains('vf-global-domain-links')?(links.dataset.vfActiveDomainVisible||''):'home-shell',
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
      if(viewport.name==='candidate-public-desktop'){
        if(route===''){
          const hero=await page.evaluate(()=>{
            const h1=document.querySelector('.vf-public-home-hero h1');
            return h1?parseFloat(getComputedStyle(h1).fontSize):0;
          });
          assert(hero>0&&hero<=60.5,'r3_public_home_hero_compact',String(hero));
        }
        if(route==='projects.php'){
          const panels=await page.locator('.vf-project-action-panels').count();
          assert(panels===0,'r3_projects_zero_attention_omits_panel',String(panels));
        }
        if(route==='tools.php'){
          const scene=await page.evaluate(()=>{
            const cards=[...document.querySelectorAll('.vf-tool-scene-grid>.vf-tool-scene-card')];
            const widths=cards.map(x=>x.getBoundingClientRect().width);
            return {count:cards.length,max:widths.length?Math.max(...widths):0};
          });
          if(scene.count>0&&scene.count<=3){
            assert(scene.max<=318,'r3_sparse_tool_scene_width',JSON.stringify(scene));
          }
        }
      }
      if(viewport.name==='candidate-public-mobile'){
        const visible=await activeDomainVisible(page);
        record('candidate-mobile-domain',route,visible);
        if(!visible.ok)fail('CANDIDATE_MOBILE_ACTIVE_DOMAIN_'+(route||'index'),JSON.stringify(visible));
        if(route==='software.php'&&visible.marker!=='1')fail('CANDIDATE_SOFTWARE_ACTIVE_DOMAIN_MARKER',JSON.stringify(visible));
        if(route==='start.php'){
          const categoryControl=await page.evaluate(()=>{
            const select=document.querySelector('.vf-mobile-functional-filters select[aria-label="导航分类"]');
            const trigger=document.querySelector('.vf-mobile-category-trigger');
            const isVisible=(el)=>{
              if(!el)return false;
              const style=getComputedStyle(el),rect=el.getBoundingClientRect();
              return style.display!=='none'&&style.visibility!=='hidden'&&rect.width>0&&rect.height>0;
            };
            return {
              enhanced:!!document.querySelector('.vf-mobile-functional-filters.is-picker-enhanced'),
              selectVisible:isVisible(select),
              triggerVisible:isVisible(trigger)
            };
          });
          assert(categoryControl.enhanced&&categoryControl.triggerVisible&&!categoryControl.selectVisible,'r5_mobile_navigation_single_category_control',JSON.stringify(categoryControl));
        }
        if(route==='channels.php'){
          const density=await page.evaluate(()=>{
            const stats=document.querySelector('.vf-channel-stats');
            const card=document.querySelector('.vf-channel-card');
            const sr=stats?.getBoundingClientRect();
            const cr=card?.getBoundingClientRect();
            return {
              statsHeight:sr?Math.round(sr.height):0,
              firstCardTop:cr?Math.round(cr.top):0,
              viewportHeight:window.innerHeight
            };
          });
          assert(density.statsHeight>0&&density.statsHeight<=58,'r4_mobile_channel_stats_compact',JSON.stringify(density));
          assert(density.firstCardTop>0&&density.firstCardTop<=680,'r4_mobile_channel_first_card_early',JSON.stringify(density));
        }
      }
    }
    await ctx.close();
  }

  // Anonymous login dialog is a shared public interaction state.
  const loginCtx=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
  const loginPage=await loginCtx.newPage();
  await loginPage.goto(localBase,{waitUntil:'networkidle'});
  await loginPage.locator('[data-vf-auth-login]').first().click();
  await loginPage.locator('[data-vf-auth-dialog][open]').waitFor({state:'visible',timeout:5000});
  await loginPage.screenshot({path:path.join(out,'candidate-mobile-login-dialog.png'),fullPage:true});
  record('public-interaction','login-dialog',{status:200,screenshot:'candidate-mobile-login-dialog.png'});
  await loginCtx.close();

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
  await admin.keyboard.press('Control+K');
  const quickInput=admin.locator('.vf-global-search input[name="q"]').first();
  await quickInput.fill('Google');
  await admin.locator('.vf-quick-open:not([hidden])').waitFor({state:'visible',timeout:5000});
  await admin.screenshot({path:path.join(out,'owner-desktop-quick-open.png'),fullPage:true});
  record('owner-interaction','quick-open',{status:200,screenshot:'owner-desktop-quick-open.png'});
  await admin.keyboard.press('Escape');
  await admin.goto(localBase+'start.php',{waitUntil:'networkidle'});
  const rowMore=admin.locator('.vf-action-menu-trigger').first();
  if(await rowMore.count()){
    await rowMore.click();
    const popover=admin.locator('.vf-action-menu-popover:popover-open').first();
    await popover.waitFor({state:'visible',timeout:5000});
    await admin.screenshot({path:path.join(out,'owner-desktop-row-more.png'),fullPage:true});
    record('owner-interaction','row-more',{status:200,screenshot:'owner-desktop-row-more.png'});
    await admin.keyboard.press('Escape');
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
    if(route==='start.php'){
      const navigationDensity=await m.evaluate(()=>{
        const filters=document.querySelector('.vf-mobile-functional-filters');
        const canonical=filters?.querySelector('select[aria-label="导航分类"]');
        const trigger=filters?.querySelector('.vf-mobile-category-trigger');
        const first=document.querySelector('.vf-asset-row');
        const isVisible=el=>!!el&&getComputedStyle(el).display!=='none'&&el.getBoundingClientRect().width>0&&el.getBoundingClientRect().height>0;
        return {
          canonicalVisible:isVisible(canonical),
          triggerVisible:isVisible(trigger),
          visibleFilterChildren:filters?[...filters.children].filter(isVisible).length:0,
          firstAssetTop:first?Math.round(first.getBoundingClientRect().top):0,
          viewportHeight:window.innerHeight
        };
      });
      assert(!navigationDensity.canonicalVisible,'r5_mobile_navigation_canonical_select_hidden',JSON.stringify(navigationDensity));
      assert(navigationDensity.triggerVisible,'r5_mobile_navigation_picker_visible',JSON.stringify(navigationDensity));
      assert(navigationDensity.visibleFilterChildren===2,'r5_mobile_navigation_filter_row_deduped',JSON.stringify(navigationDensity));
      assert(navigationDensity.firstAssetTop>0&&navigationDensity.firstAssetTop<=325,'r5_mobile_navigation_first_asset_early',JSON.stringify(navigationDensity));
      const trigger=m.locator('.vf-mobile-category-trigger');
      await trigger.click();
      const overlay=m.locator('.vf-mobile-category-overlay.open');
      await overlay.waitFor({state:'visible',timeout:5000});
      assert(await overlay.locator('.vf-mobile-category-search input').isVisible(),'r5_mobile_navigation_picker_search_visible');
      await m.keyboard.press('Escape');
    }
    if(route==='watch.php'){
      const watchDensity=await m.evaluate(()=>{
        const selects=[...document.querySelectorAll('.vf-watch-selects select')];
        const tops=selects.map(el=>Math.round(el.getBoundingClientRect().top));
        const first=document.querySelector('.vf-watch-library-card');
        return {
          count:selects.length,
          topSpread:tops.length?Math.max(...tops)-Math.min(...tops):999,
          firstCardTop:first?Math.round(first.getBoundingClientRect().top):0,
          viewportHeight:window.innerHeight
        };
      });
      assert(watchDensity.count===3,'r6_mobile_watch_three_advanced_filters_preserved',JSON.stringify(watchDensity));
      assert(watchDensity.topSpread<=4,'r6_mobile_watch_filters_single_row',JSON.stringify(watchDensity));
      assert(watchDensity.firstCardTop>0&&watchDensity.firstCardTop<=825,'r6_mobile_watch_first_card_early',JSON.stringify(watchDensity));
    }
  }

  // Mobile owner account chrome: one persistent More trigger, low-frequency actions inside the menu.
  await m.goto(localBase+'software.php',{waitUntil:'networkidle'});
  const directSettings=m.locator('.vf-global-account-actions > .vf-global-account-settings');
  const directLogout=m.locator('.vf-global-account-actions > .vf-global-account-logout');
  const more=m.locator('[data-vf-global-account-more]');
  assert(await more.isVisible(),'mobile_account_more_visible');
  assert(!(await directSettings.isVisible()),'mobile_direct_settings_hidden');
  assert(!(await directLogout.isVisible()),'mobile_direct_logout_hidden');
  await more.click();
  const accountMenu=m.locator('[data-vf-global-account-menu]:not([hidden])');
  await accountMenu.waitFor({state:'visible',timeout:5000});
  const menuText=(await accountMenu.innerText()).replace(/\s+/g,' ').trim();
  for(const label of ['设置','资源管理','回收站','退出登录']){
    assert(menuText.includes(label),'mobile_account_menu_'+label);
  }
  await m.screenshot({path:path.join(out,'owner-mobile-account-menu.png'),fullPage:true});
  record('owner-interaction','mobile-account-menu',{status:200,screenshot:'owner-mobile-account-menu.png',menuText});

  const mobileAdminRoutes=[
    'manage.php','surface-manager.php','surface-manager.php?advanced=1','links-admin.php',
    'transfer.php','data-safety.php','system-health.php','plugins.php',
    'browser-helper.php','update.php','settings.php'
  ];
  for(const route of mobileAdminRoutes) await capture(m,'admin-mobile',route,localBase,'admin-mobile');
  await m.goto(localBase+'manage.php',{waitUntil:'networkidle'});
  await m.locator('.vf-admin-menu-button').click();
  await m.locator('#vfAdminRail').waitFor({state:'visible',timeout:5000});
  await m.screenshot({path:path.join(out,'admin-mobile-rail-open.png'),fullPage:true});
  record('owner-interaction','admin-mobile-rail',{status:200,screenshot:'admin-mobile-rail-open.png'});
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
    source:{sha:String(process.env.target_sha||''),tree:String(process.env.target_tree||''),version:String(process.env.target_version||'')},
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
