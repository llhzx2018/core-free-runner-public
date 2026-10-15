'use strict';
const assert=require('node:assert/strict'),fs=require('fs'),{chromium}=require('playwright');
const base='http://127.0.0.1:18880',path='/wp-admin/themes.php?page=vf-theme-modules&tab=layout',checks=[],errors=[];
function gate(value,label,detail){checks.push({label,pass:!!value,detail});assert(value,label+' '+JSON.stringify(detail));}
async function login(page,user='admin',password='Synthetic-Only-Update-54!'){
  await page.goto(base+'/wp-login.php');await page.locator('#user_login').fill(user);await page.locator('#user_pass').fill(password);await page.locator('#wp-submit').click();await page.waitForURL('**/wp-admin/**');
}
(async()=>{
 const browser=await chromium.launch({headless:true}),context=await browser.newContext(),page=await context.newPage();
 page.on('pageerror',error=>errors.push(error.message));await login(page);
 await page.goto(base+path);await page.waitForLoadState('networkidle');
 gate(await page.locator('[data-vf-frontend-pages]').count()===1,'layout opens permanent frontend page directory');
 gate(await page.locator('[data-vf-page-context]').count()===20,'all 20 page types present');
 gate((await page.content()).includes('s01-directory-queries:0'),'ordinary GET does not query content');
 for(const width of [1920,1440,1319,1024]){
  await page.setViewportSize({width,height:1000});await page.goto(base+path);await page.waitForLoadState('networkidle');
  const size=await page.locator('[data-vf-frontend-pages]').evaluate(el=>({width:el.getBoundingClientRect().width,font:getComputedStyle(el).fontSize,overflow:document.documentElement.scrollWidth>innerWidth+1}));
  gate(!size.overflow && size.width>400,'desktop directory is usable without overflow',{width,...size});
  const summary=page.locator('[data-vf-page-context="search"] summary');await summary.focus();await page.keyboard.press('Enter');
  gate(await summary.locator('..').getAttribute('open')!==null,'keyboard opens state checks',{width});await page.keyboard.press('Enter');
  gate(await summary.locator('..').getAttribute('open')===null,'keyboard closes state checks',{width});
 }
 const filters=page.locator('form[method="get"]');await filters.locator('[name="vf_pages_q"]').fill('搜索结果');await filters.getByRole('button',{name:'查看',exact:true}).click();await page.waitForLoadState('networkidle');
 gate(await page.locator('[data-vf-page-context]').count()===1 && await page.locator('[data-vf-page-context="search"]').count()===1,'native keyword search isolates matching type');
 await page.goto(base+path+'&vf_pages_q=does-not-exist');gate(await page.getByRole('heading',{name:'没有匹配的页型'}).count()===1,'filter empty state');
 await page.getByRole('link',{name:'恢复全部页型'}).click();gate(await page.locator('[data-vf-page-context]').count()===20,'reset restores directory');
 await page.goto(base+path+'&vf_pages_group=core&vf_pages_language=zh');
 gate(await page.locator('[data-vf-page-context]').count()===4,'native group filter');
 const href=await page.locator('[data-vf-page-context="home"] .vf-frontend-pages__actions a[target="_blank"]').getAttribute('href');gate(new URL(href).pathname==='/zh/','language-specific home link');
 await page.goto(base+path);const guide=page.locator('[data-vf-page-context="guide_detail"]');
 gate(await guide.locator('.vf-frontend-pages__actions a[target="_blank"]').count()===0,'unqueried historical detail example is not a real frontend link');
 await page.locator('[data-vf-page-context="search"] summary').click();
 const searchLinks=await page.locator('[data-vf-page-context="search"] details a').evaluateAll(es=>es.map(e=>e.href));
 gate(searchLinks.length===3&&searchLinks.every(u=>new URL(u).searchParams.has('s')),'real search state URLs preserve query');
 const content=page.locator('[data-vf-frontend-content-form]');await content.locator('[name="vf_content_type"]').selectOption('vf_guide');await content.locator('[name="vf_content_q"]').fill('Directory Fixture');await content.getByRole('button',{name:'加载已发布内容'}).click();await page.waitForLoadState('networkidle');
 gate(await page.locator('.vf-frontend-pages__content-list li').count()===20,'explicit read loads only 20 published guides');
 gate(!(await page.locator('.vf-frontend-pages__content-list').innerText()).includes('HIDDEN'),'draft and private content excluded');
 gate((await page.content()).includes('s01-directory-queries:1'),'one bounded explicit content query');
 const firstIds=await page.locator('.vf-frontend-pages__content-list a').filter({hasText:'编辑内容'}).evaluateAll(es=>es.map(e=>new URL(e.href).searchParams.get('post')));
 await page.getByRole('button',{name:'下一页',exact:true}).click();await page.waitForLoadState('networkidle');
 gate(await page.locator('.vf-frontend-pages__content-list li').count()===6,'real next page has remaining six guides');
 gate(await page.locator('[name="vf_content_q"]').inputValue()==='Directory Fixture' && await page.locator('[name="vf_content_type"]').inputValue()==='vf_guide','pagination preserves search and content type');
 const lastIds=await page.locator('.vf-frontend-pages__content-list a').filter({hasText:'编辑内容'}).evaluateAll(es=>es.map(e=>new URL(e.href).searchParams.get('post')));
 gate(!lastIds.some(id=>firstIds.includes(id)),'no duplicate records across pages');
 await page.getByRole('button',{name:'上一页',exact:true}).click();await page.waitForLoadState('networkidle');gate(await page.locator('.vf-frontend-pages__content-list li').count()===20,'previous page works');
 await page.locator('[name="vf_content_q"]').fill('no-title-matches-7a91');await page.getByRole('button',{name:'加载已发布内容'}).click();await page.waitForLoadState('networkidle');gate((await page.locator('.vf-frontend-pages__content').innerText()).includes('没有匹配的已发布内容'),'honest content empty state');
 await page.locator('[name="vf_content_q"]').fill('Directory Fixture');await page.locator('[data-vf-frontend-content-form] [name="vf_pages_language"]').selectOption('zh');await page.getByRole('button',{name:'加载已发布内容'}).click();await page.waitForLoadState('networkidle');
 gate(await page.locator('.vf-frontend-pages__content-list li').count()===3 && (await page.locator('.vf-frontend-pages__content-list').innerText()).includes('中文'),'actual Polylang Chinese content query');
 const firstLink=await page.locator('.vf-frontend-pages__content-list a[target="_blank"]').first().getAttribute('href');gate(new URL(firstLink).pathname.startsWith('/zh/'),'published content points to its actual language URL');
 const editUrl=await page.locator('.vf-frontend-pages__content-list a').filter({hasText:'编辑内容'}).first().getAttribute('href');const edit=await page.request.get(editUrl);gate(edit.status()===200&&(await edit.text()).includes('wp-admin'),'native edit target is reachable');
 await page.locator('[name="vf_content_q"]').fill('synthetic-read-failure');await page.getByRole('button',{name:'加载已发布内容'}).click();await page.waitForLoadState('networkidle');
 gate((await page.locator('[role="alert"]').innerText()).includes('重试')&&await page.locator('[name="vf_content_q"]').inputValue()==='synthetic-read-failure','injected read failure preserves input with retry feedback');
 gate(!(await page.content()).includes('SYNTHETIC_INTERNAL_ERROR_DO_NOT_EXPOSE'),'exception detail is not exposed');
 await page.locator('[name="vf_content_q"]').fill('Directory Fixture');await page.getByRole('button',{name:'加载已发布内容'}).click();await page.waitForLoadState('networkidle');gate(await page.locator('.vf-frontend-pages__content-list li').count()===3,'retry recovers after failure');
 await page.setViewportSize({width:1440,height:1000});await page.screenshot({path:'proof/frontend-pages-content.png',fullPage:true});
 await page.goto(base+path);await page.screenshot({path:'proof/frontend-pages-directory.png',fullPage:true});
 await page.locator('[data-vf-page-context="home"] a').filter({hasText:'调整布局'}).click();await page.waitForLoadState('networkidle');gate(await page.locator('[data-vf-layout-context-catalog-open]').count()===1,'existing layout editor remains reachable');
 const checkbox=page.locator('[data-vf-layout-page] input[type="checkbox"]:enabled:visible').first();
 await checkbox.click();await page.waitForFunction(()=>document.querySelector('[data-vf-layout-page]')?.classList.contains('is-dirty'));
 await page.getByRole('link',{name:'前台页面',exact:true}).click();
 gate(await page.locator('[data-vf-layout-navigation-dialog]:visible').count()===1,'returning to directory reuses existing unsaved-change dialog');
 await page.locator('[data-vf-layout-navigation-cancel]').last().click();gate(await page.locator('[data-vf-layout-page].is-dirty').count()===1,'cancel keeps unsaved layout input');
 await page.locator('[data-vf-layout-discard]').click();
 await page.getByRole('link',{name:'前台页面',exact:true}).click();gate(await page.locator('[data-vf-frontend-pages]').count()===1,'layout editor returns to permanent directory');
 const nojs=await browser.newContext({javaScriptEnabled:false}),native=await nojs.newPage();await login(native);await native.goto(base+path);await native.locator('[data-vf-frontend-content-form] [name="vf_content_type"]').selectOption('vf_guide');await native.getByRole('button',{name:'加载已发布内容'}).click();await native.waitForLoadState('domcontentloaded');gate(await native.locator('.vf-frontend-pages__content-list li').count()===20,'native content query works without JavaScript');await nojs.close();
 const denied=await browser.newContext(),sub=await denied.newPage();await login(sub,'subscriber','Synthetic-Subscriber-47!');const res=await sub.goto(base+path);gate(res.status()===403,'unprivileged browser denied theme workspace');await denied.close();
 gate(errors.length===0,'no uncaught browser errors',errors);fs.writeFileSync('proof/browser.json',JSON.stringify({status:'PASS',checks,mobile:'NOT_RUN_OWNER_DEFERRED',production:'NOT_EXECUTED'},null,2));await browser.close();
})().catch(error=>{fs.writeFileSync('proof/browser-failure.json',JSON.stringify({status:'FAIL',error:error.message,checks,errors},null,2));console.error(error);process.exit(1);});
