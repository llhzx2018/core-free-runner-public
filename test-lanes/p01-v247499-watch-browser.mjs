import assert from 'node:assert/strict';
import {chromium} from 'playwright';
import fs from 'node:fs';

const origin=process.env.P01_TEST_ORIGIN;
const password=process.env.P01_TEST_PASSWORD;
const fixtureFile=process.env.P01_FIXTURE_JSON;
if(!/^http:\/\/127\.0\.0\.1:\d+$/.test(origin||'')||!password||!fixtureFile)
  throw Error('P01_ISOLATED_WATCH_BROWSER_ONLY');
const fixture=JSON.parse(fs.readFileSync(fixtureFile,'utf8'));
const browser=await chromium.launch({headless:true,executablePath:'/usr/bin/google-chrome',args:['--no-sandbox']});
const cards=page=>page.locator('.vf-watch-card[data-asset-row]');
const card= (page,id)=>page.locator('.vf-watch-card[data-asset-row="'+id+'"]');
const noOpenDialogs=async page=>{
  assert.equal(await page.locator('dialog[open]').count(),0,'normal Watch browsing cannot force-open management');
};
let nativeDialogs=[];
try {
  const guest=await browser.newContext({viewport:{width:1440,height:900}});
  await guest.route(/^https?:\/\/(?!127\.0\.0\.1)/,route=>route.abort());
  const visitor=await guest.newPage();
  visitor.on('dialog',dialog=>{nativeDialogs.push(dialog.message());void dialog.dismiss()});
  await visitor.goto(origin+'/watch.php?sort=title',{waitUntil:'domcontentloaded'});
  await noOpenDialogs(visitor);
  assert.equal(await cards(visitor).count(),2,'guest can only see the 2 public films');
  assert.equal(await card(visitor,fixture.privateWatched).count(),0,'guest cannot read private watched film');
  assert.equal(await card(visitor,fixture.privateUnmarked).count(),0,'guest cannot read private unmarked film');
  assert.equal(await visitor.locator('[data-watch-manage="status"]').count(),0,'no Owner-only controls in anonymous detail');
  await visitor.goto(origin+'/watch.php?view=lists&sort=title',{waitUntil:'domcontentloaded'});
  assert.equal(await cards(visitor).count(),2,'guest ?view=lists remains public library, never Owner list');
  assert.equal(await visitor.locator('.vf-watch-hero h1').textContent(),'影视库');
  await noOpenDialogs(visitor);
  await guest.close();
  console.log('P01_WATCH_OWNER_GUEST_REAL_BROWSER_PRIVACY=PASS');

  const owner=await browser.newContext({viewport:{width:1440,height:900}});
  await owner.route(/^https?:\/\/(?!127\.0\.0\.1)/,route=>route.abort());
  const login=await owner.request.post(origin+'/api.php?action=login',{data:{password}});
  assert.equal(login.status(),200);
  assert.match(await login.text(),/"ok":true/);
  const page=await owner.newPage();
  page.on('dialog',dialog=>{nativeDialogs.push(dialog.message());void dialog.dismiss()});
  const libraryUrl=origin+'/watch.php?sort=title';
  await page.goto(libraryUrl,{waitUntil:'domcontentloaded'});
  assert.equal(await cards(page).count(),4,'Owner library contains all four fixture films');
  await noOpenDialogs(page);
  await page.goto(origin+'/watch.php?view=lists&sort=title',{waitUntil:'domcontentloaded'});
  assert.equal(await cards(page).count(),2,'Owner marked list contains only marked fixtures');
  assert.equal(await card(page,fixture.publicMarked).count(),1);
  assert.equal(await card(page,fixture.privateWatched).count(),1);
  assert.equal(await card(page,fixture.publicUnmarked).count(),0);
  assert.equal(await card(page,fixture.privateUnmarked).count(),0);
  const kindNames=await page.locator('.vf-watch-facets').allTextContents();
  assert.equal(kindNames.some(s=>s.includes('纪录片')||s.includes('剧集')),false,
    'list content kind facets cannot leak unmarked film types');
  await noOpenDialogs(page);
  console.log('P01_WATCH_OWNER_LISTS_VIEW_LOCAL_BROWSER=PASS');

  await page.goto(origin+'/watch.php?view=recent',{waitUntil:'domcontentloaded'});
  assert.equal(await cards(page).count(),0,'recent does not fabricate unplayed history');
  await noOpenDialogs(page);
  // Only the disposable isolated site receives a source-open event.
  const opened=await owner.request.get(origin+'/surface-open.php?id='+fixture.publicMarked,{maxRedirects:0});
  assert.equal([301,302,303,307,308].includes(opened.status()),true,'open source safely redirects');
  await page.reload({waitUntil:'domcontentloaded'});
  assert.equal(await card(page,fixture.publicMarked).count(),1,'recent lists only actually opened movie');
  assert.equal(await card(page,fixture.privateWatched).count(),0,'never-opened private movie absent from recent');
  assert.equal(await page.locator('.vf-watch-statuses').count(),0,'recent must not show inapplicable status filter');
  await noOpenDialogs(page);
  console.log('P01_WATCH_RECENT_ACTUAL_SOURCE_BROWSER=PASS');

  await page.goto(libraryUrl,{waitUntil:'domcontentloaded'});
  const chosen=card(page,fixture.publicMarked);
  await chosen.locator('.vf-watch-title-open').click();
  const detail=page.locator('.vf-watch-detail-dialog');
  assert.equal(await detail.evaluate(node=>node.open),true,'single native Watch detail opens');
  await detail.locator('[data-watch-manage="status"]').click();
  const drawer=page.locator('[data-panel="detail"]');
  assert.equal(await drawer.isVisible(),true,'Watch status delegates to existing canonical editor');
  assert.equal(await detail.evaluate(n=>n.open),false,'no nested Watch dialog');
  assert.equal(await drawer.getAttribute('data-vf-return-to-watch-asset'),String(fixture.publicMarked));
  const originalTitle=await drawer.locator('[data-detail-form] [name="title"]').inputValue();
  assert.equal(originalTitle,'Public Marked Film');
  await drawer.locator('[data-detail-form] [name="title"]').fill('Unsaved browser fixture change');
  await drawer.locator('[data-close-panel]').click();
  const feedback=drawer.locator('[data-vf-panel-feedback]');
  assert.match(await feedback.textContent(),/未保存的修改/,'dirty cancel requires inline decision');
  await feedback.getByRole('button',{name:'放弃并关闭'}).click();
  await page.waitForFunction(id=>document.activeElement?.matches(
    '.vf-watch-card[data-asset-row="'+id+'"] .vf-watch-title-open'),fixture.publicMarked);
  assert.equal(await chosen.locator('.vf-watch-title-open').textContent(),'Public Marked Film');
  await noOpenDialogs(page);
  console.log('P01_WATCH_EDITOR_CANCEL_FOCUS_BROWSER=PASS');

  await chosen.locator('.vf-watch-poster-open').click();
  await detail.locator('[data-watch-manage="status"]').click();
  assert.equal(await drawer.isVisible(),true);
  const status=drawer.locator('[data-detail-form] [name="media_status"]');
  assert.equal(await status.count(),1,'single canonical media status field');
  await status.selectOption('watched');
  const beforeUrl=page.url();
  const navigation=page.waitForNavigation({waitUntil:'domcontentloaded',timeout:15000});
  await drawer.locator('[data-detail-form] button[type="submit"]').click();
  await navigation;
  assert.equal(page.url(),beforeUrl,'confirmed edit refreshes same Watch view');
  await page.waitForFunction(id=>document.activeElement?.matches(
    '.vf-watch-card[data-asset-row="'+id+'"] .vf-watch-poster-open'),fixture.publicMarked);
  assert.equal(await card(page,fixture.publicMarked).locator('.vf-watch-state').textContent(),'看过');
  await noOpenDialogs(page);
  console.log('P01_WATCH_EDITOR_SAVE_RETURN_FOCUS_BROWSER=PASS');

  // Hold exactly one synthetic request; a detail close/reopen cannot double-submit.
  let posts=0,unblock=null;
  const held=new Promise(resolve=>{unblock=resolve});
  await page.route('**/watch-metadata-sync.php',async route=>{
    if(route.request().method()!=='POST')return route.continue();
    posts+=1;
    await held;
    await route.fulfill({status:200,contentType:'application/json',
      body:JSON.stringify({ok:true,result:{success:false,id:fixture.publicMarked,error:'synthetic failure'}})});
  });
  await card(page,fixture.publicMarked).locator('.vf-watch-title-open').click();
  await detail.locator('.vf-watch-detail-extra > summary').click();
  await detail.locator('[data-watch-detail-sync]').click();
  await page.waitForTimeout(220);
  assert.equal(posts,1,'Owner triggers one explicit synthetic TMDB request');
  await detail.locator('[data-watch-detail-close]').click();
  await card(page,fixture.publicMarked).locator('.vf-watch-title-open').click();
  await detail.locator('.vf-watch-detail-extra > summary').click();
  assert.equal(await detail.locator('[data-watch-detail-sync]').isDisabled(),true,
    'sync remains locked when detail is reopened during pending POST');
  assert.equal(posts,1,'reopen never double-submits');
  unblock();
  await page.waitForFunction(()=>{const b=document.querySelector('[data-watch-detail-sync]');
    return b && !b.disabled && b.textContent.includes('TMDB')});
  assert.equal(posts,1);
  await detail.locator('[data-watch-detail-close]').click();
  await noOpenDialogs(page);
  assert.deepEqual(nativeDialogs,[],'normal Watch actions must not show browser confirm');
  console.log('P01_WATCH_TMDB_REAL_BROWSER_PENDING_REOPEN=PASS');
  console.log('P01_WATCH_NO_BROWSER_CONFIRM=PASS');
  await owner.close();
} finally {
  await browser.close();
}
