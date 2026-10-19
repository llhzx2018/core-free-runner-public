const {chromium}=require('playwright');
const fs=require('fs');
const checks=[],inventory=[];
function check(name,pass,detail){checks.push({name,pass:!!pass,detail});if(!pass)throw new Error(name+': '+JSON.stringify(detail));}
const origin='http://127.0.0.1:18880';
const tabs=['overview','brand','layout','navigation','render','seo','preview','recovery'];
const contexts=['home','tool','tool_hub','blog_index','article_detail','guide_index','guide_detail','problem_index','problem_detail','archive_list','faq_page','glossary_index','glossary_detail','legal','contact_page','about_page','basic_page','search','not_found','html_sitemap'];
const base=host=>origin+'/wp-admin/'+(host==='embedded'?'admin.php?page=synthetic-theme-host&component=theme':'themes.php?page=vf-theme-modules');
const url=(host,tab,extra={})=>base(host)+'&'+new URLSearchParams({tab,...extra});
(async()=>{
 let completed=false;
 const browser=await chromium.launch();
 try{
  const context=await browser.newContext({viewport:{width:1440,height:1000}});
  const page=await context.newPage();page.on('dialog',dialog=>dialog.accept());
  await page.goto(origin+'/wp-login.php');await page.locator('#user_login').fill('admin');await page.locator('#user_pass').fill('Synthetic-Only-Update-54!');await page.locator('input[name=redirect_to]').evaluate((e,value)=>e.value=value,url('appearance','layout'));await page.locator('#wp-submit').click();await page.waitForURL('**/wp-admin/**');
  const tailOnly=process.env.VF_NAV_TAIL_ONLY==='1';
  if(!tailOnly){
  for(const host of ['appearance','embedded']){
   for(const tab of tabs){
    const response=await page.goto(url(host,tab),{waitUntil:'networkidle'});
    check(`${host}/${tab} reachable`,response.status()===200&&await page.locator(`[data-vf-admin-workspace][data-vf-admin-tab="${tab}"]`).count()===1);
    check(`${host}/${tab} heading`,await page.locator('.vf-theme-admin h1').count()===1);
    const nav=page.locator(host==='embedded'?'.vf-admin-component-nav':'.vf-admin-topbar-main');
    const hrefs=await nav.locator('a').evaluateAll(xs=>xs.map(x=>x.href));
    check(`${host}/${tab} all 8 menu destinations`,tabs.every(t=>hrefs.some(h=>new URL(h).searchParams.get('tab')===t)));
    check(`${host}/${tab} host retained`,hrefs.every(h=>new URL(h).searchParams.get('page')===(host==='embedded'?'synthetic-theme-host':'vf-theme-modules')));
    check(`${host}/${tab} desktop no page overflow`,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    inventory.push({surface_id:tab,host,status:'canonical',discoverable:true,reachable:true,title:await page.locator('.vf-theme-admin h1').innerText()});
    if(tab==='overview'){
     for(const t of ['overview','brand','layout','navigation','render','seo']){check(`${host} main menu ${t} visible`,await nav.locator(`a[data-vf-admin-tab="${t}"]`).isVisible());}
     await nav.locator('.vf-theme-maintenance-menu>summary').click();
     for(const t of ['preview','recovery']){check(`${host} maintenance menu ${t} discoverable`,await nav.locator(`a[href*="tab=${t}"]`).isVisible());}
     await nav.locator('.vf-theme-maintenance-menu>summary').click();
     const links=await page.locator('[data-workspace-id]').evaluateAll(xs=>xs.map(x=>x.href));
     check(`${host} dashboard links stay in host`,links.length===5&&links.every(h=>new URL(h).searchParams.get('page')===(host==='embedded'?'synthetic-theme-host':'vf-theme-modules')),links);
    }
   }
   await page.goto(url(host,'layout'),{waitUntil:'networkidle'});
   check(`${host} directory identity`,await page.locator('.vf-theme-admin h1').innerText()==='前台页面总览');
   check(`${host} no misleading saved status`,await page.locator('.vf-admin-page-head [data-vf-unsaved-indicator]').count()===0);
   const rows=page.locator('[data-vf-page-context]');check(`${host} 20 page types visible`,await rows.count()===20);
   const editorLinks=await rows.locator('.vf-frontend-pages__actions a.button').evaluateAll(xs=>xs.map(x=>x.href));
   for(const c of contexts){
    const href=editorLinks.find(h=>new URL(h).searchParams.get('context')===c);check(`${host}/${c} discoverable`,!!href);
    const r=await page.goto(href,{waitUntil:'networkidle'});
    check(`${host}/${c} editor reached`,r.status()===200&&await page.locator(`[data-vf-layout-context="${c}"]`).count()===1);
    check(`${host}/${c} editor identified`,(await page.locator('.vf-theme-admin h1').innerText()).endsWith(' · 布局设置'));
    check(`${host}/${c} breadcrumb and return`,await page.locator('.vf-layout-location a').count()===1&&await page.locator('[data-vf-layout-directory-link]').innerText()==='返回页面总览');
    const ret=new URL(await page.locator('[data-vf-layout-directory-link]').getAttribute('href'));
    check(`${host}/${c} return host and directory`,ret.searchParams.get('page')===(host==='embedded'?'synthetic-theme-host':'vf-theme-modules')&&ret.searchParams.get('view')==='pages');
    inventory.push({surface_id:'layout/'+c,host,status:'canonical',discoverable:true,reachable:true,return_path:ret.pathname+ret.search});
   }
   await page.goto(url(host,'layout',{vf_pages_q:'指南',vf_pages_group:'content',vf_pages_language:'zh',vf_review_device:'desktop'}),{waitUntil:'networkidle'});
   check(`${host} native directory filters`,await rows.count()===2);
   await page.locator('[data-vf-page-context="guide_detail"] a.button').click();await page.waitForLoadState('networkidle');
   await page.locator('[data-vf-layout-directory-link]').click();await page.waitForLoadState('networkidle');
   check(`${host} return restores filter inputs`,await page.locator('input[name=vf_pages_q]').first().inputValue()==='指南'&&await page.locator('select[name=vf_pages_language]').first().inputValue()==='zh'&&await rows.count()===2);
   await page.goto(url(host,'layout',{view:'edit',context:'missing-page-type'}),{waitUntil:'networkidle'});
   check(`${host} invalid editor recovers honestly`,await rows.count()===20&&await page.locator('[role=alert]').filter({hasText:'未找到这个页型'}).count()===1);
   await page.goto(url(host,'layout',{view:'edit',context:'home'}),{waitUntil:'networkidle'});
   await page.locator('[data-vf-layout-context-catalog-open]').click();
   const catalog=page.locator('[data-vf-layout-context-catalog-dialog]');check(`${host} page switcher visible`,await catalog.isVisible());
   const switchLinks=await catalog.locator('[data-vf-layout-context-card]').evaluateAll(xs=>xs.map(x=>x.href));
   check(`${host} 20 switcher targets retain host`,switchLinks.length===20&&switchLinks.every(h=>new URL(h).searchParams.get('page')===(host==='embedded'?'synthetic-theme-host':'vf-theme-modules')));
   await page.keyboard.press('Escape');check(`${host} page switcher closes`,!await catalog.isVisible());
  }
  // Directory desktop presentation and native read-only content operations.
  for(const width of [1440,1024]){
   await page.setViewportSize({width,height:1000});await page.goto(url('appearance','layout'),{waitUntil:'networkidle'});
   check(`${width} directory no page overflow`,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   check(`${width} records compact by default`,await page.locator('.vf-frontend-pages__row .vf-frontend-pages__progress-record details[open]').count()===0);
   await page.screenshot({path:`proof/admin-directory-${width}.png`,fullPage:true});
  }
  await page.setViewportSize({width:1440,height:1000});
  const finder=page.locator('[data-vf-frontend-content-form]');await finder.locator('input[name=vf_content_q]').fill('Directory Fixture');await finder.locator('select[name=vf_content_type]').selectOption('vf_guide');await finder.locator('select[name=vf_pages_language]').selectOption('en');await finder.locator('[data-vf-content-submit]').click();await page.waitForLoadState('networkidle');
  check('native content finder first page',await page.locator('.vf-frontend-pages__content-list li').count()===20);
  await page.locator('.vf-frontend-pages__pagination button').filter({hasText:'下一页'}).click();await page.waitForLoadState('networkidle');
  check('native content finder second page',await page.locator('.vf-frontend-pages__content-list li').count()===6);
  await page.locator('.vf-frontend-pages__content-list li').first().getByRole('link',{name:'调整布局',exact:true}).click();await page.waitForLoadState('networkidle');
  check('actual content has layout route',await page.locator('[data-vf-layout-context="guide_detail"]').count()===1);
  // Representative auxiliary navigation. Open/cancel only, never confirm writes.
  const dialogs=[
   ['brand','[data-vf-brand-preview-open]','[data-vf-brand-preview-dialog]','[data-vf-brand-dialog-close]'],
   ['seo','[data-vf-seo-open-picker]','[data-vf-seo-picker-dialog]','[data-vf-seo-dialog-close]'],
   ['seo','[data-vf-seo-add-route]','[data-vf-seo-add-dialog]','[data-vf-seo-dialog-close]'],
   ['preview','[data-vf-preview-target-open]','[data-vf-preview-target-dialog]','[data-vf-preview-target-close]'],
  ];
  for(const [tab,trigger,dialog,close] of dialogs){await page.goto(url('appearance',tab),{waitUntil:'networkidle'});await page.locator(trigger).first().click();const panel=page.locator(dialog);check(`${tab} ${dialog} discoverable and opens`,await panel.isVisible());await panel.locator('button'+close).first().click();check(`${tab} ${dialog} closes`,!await panel.isVisible());}
  }
  await page.goto(url('appearance','recovery'),{waitUntil:'networkidle'});
  for(const task of ['status','export','import','restore']){await page.locator(`[data-vf-recovery-workflow-step="${task}"]`).click();check(`recovery task ${task} reachable`,await page.locator(`[data-vf-recovery-workflow-section="${task}"]`).isVisible());}
  await page.locator('.vf-recovery-danger-zone summary').click();await page.locator('[data-vf-recovery-default-open]').click();check('recovery defaults confirmation reachable',await page.locator('[data-vf-recovery-dialog="defaults"]').isVisible());await page.locator('[data-vf-recovery-dialog="defaults"] button[data-vf-recovery-dialog-close]').first().click();check('recovery defaults closes without writing',!await page.locator('[data-vf-recovery-dialog="defaults"]').isVisible());
  await page.goto(url('appearance','ads'),{waitUntil:'networkidle'});check('legacy ads successor visible',await page.locator('[data-vf-admin-workspace][data-vf-admin-tab="render"]').count()===1);
  const nojs=await browser.newContext({javaScriptEnabled:false,storageState:await context.storageState(),viewport:{width:1440,height:1000}});const native=await nojs.newPage();await native.goto(url('appearance','layout',{vf_pages_q:'指南'}));check('directory remains navigable without JavaScript',await native.locator('[data-vf-page-context]').count()===2);await native.locator('[data-vf-page-context="guide_index"] a.button').click();check('native editor and return path',await native.locator('[data-vf-layout-context="guide_index"]').count()===1&&await native.locator('[data-vf-layout-directory-link]').count()===1);await nojs.close();
  completed=true;
  console.log('ADMIN_NAVIGATION_PASS',checks.length);
 }finally{fs.writeFileSync('proof/admin-navigation.json',JSON.stringify({status:completed&&checks.every(x=>x.pass)?'PASS':'FAIL',checks,inventory,mobile:'NOT_RUN_OWNER_DEFERRED',scope:'Theme navigation/discoverability, not all business actions'},null,2));await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
