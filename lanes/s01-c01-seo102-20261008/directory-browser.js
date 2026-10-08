'use strict';
const fs=require('fs'),assert=require('assert/strict'),{chromium}=require('playwright'),{base}=require('./seo-common');
(async()=>{
 const browser=await chromium.launch(),rows=[],cases=[];
 for(const width of [1920,1440,1319,1024,768,390]){
  const page=await browser.newPage({viewport:{width,height:1000}});
  await page.goto(base+'/tools/');await page.waitForLoadState('networkidle');
  const module=page.locator('[data-vf-theme-module=content_matrix]');
  assert.equal(await module.getByRole('heading',{name:'Recommended next steps',exact:true}).count(),1);
  assert.equal(await module.locator('.vf-content-matrix-grid a').count(),6);
  const geometry=await page.evaluate(()=>({width:innerWidth,client:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth,mains:document.querySelectorAll('main').length}));
  assert(geometry.scroll<=geometry.client+4);assert.equal(geometry.mains,1);
  if(width===1440||width===390)await page.screenshot({path:'proof/tools-'+width+'.png',fullPage:true});
  rows.push({...geometry,heading_count:1,recommendation_links:6});await page.close();
 }
 const p=await browser.newPage({viewport:{width:1440,height:1000}});
 const wait=()=>p.waitForLoadState('networkidle'), query=()=>p.locator('[data-vf-directory-query]'), visible=()=>p.locator('[data-vf-directory-item]:visible'), btn=value=>p.locator('[data-vf-directory-filter-button='+value+']');
 async function checkCount(n,name){assert.equal(await visible().count(),n,name);cases.push(name);}
 async function clickFilter(value){await Promise.all([p.waitForURL(u=>u.searchParams.get('vf_filter')===value),btn(value).click()]);await wait();assert.equal(await btn(value).getAttribute('aria-pressed'),'true');}
 await p.goto(base+'/tools/');await wait();await query().fill('encryption');
 await checkCount(1,'live keyword finds exact tool');assert.equal(await visible().getAttribute('data-vf-directory-route'),'m3u8-encryption-detector');
 await query().fill('');await clickFilter('play');await checkCount(2,'category click survives actual server navigation');
 await p.reload();await wait();await checkCount(2,'reload preserves category');
 await query().fill('encryption');await checkCount(0,'live category keyword intersection');
 await clickFilter('inspect');assert.equal(new URL(p.url()).searchParams.get('vf_q'),'encryption');assert.equal(await query().inputValue(),'encryption');
 await checkCount(1,'category navigation preserves current typed keyword');
 await p.reload();await wait();await checkCount(1,'reload preserves category and keyword');
 await Promise.all([p.waitForURL(u=>!u.searchParams.has('vf_filter')&&!u.searchParams.has('vf_q')),p.locator('[data-vf-directory-reset]').click()]);await wait();await checkCount(9,'clear restores full pool');
 await Promise.all([p.waitForURL(u=>u.searchParams.get('vf_filter')==='manage'),p.locator('[data-vf-directory-filter-select]').selectOption('manage')]);await wait();await checkCount(3,'native select changes persisted category');
 await query().fill('no-match-synthetic');await checkCount(0,'empty state has zero cards');assert(await p.locator('[data-vf-directory-empty]').isVisible());
 await Promise.all([p.waitForURL(u=>!u.searchParams.has('vf_filter')&&!u.searchParams.has('vf_q')),p.locator('[data-vf-directory-reset]').click()]);await wait();await checkCount(9,'empty state clears and recovers');
 await query().fill('encryption');await Promise.all([p.waitForURL(u=>u.searchParams.get('vf_q')==='encryption'),query().press('Enter')]);await wait();await checkCount(1,'native GET search survives server navigation');
 await query().fill('');await checkCount(9,'clearing keyword restores hidden pool without reload');
 const c=await browser.newContext({javaScriptEnabled:false}),np=await c.newPage();
 await np.goto(base+'/tools/?vf_filter=play');assert.equal(await np.locator('[data-vf-directory-item]:visible').count(),2);cases.push('server category result without JavaScript');
 await np.goto(base+'/tools/?vf_filter=inspect&vf_q=encryption');assert.equal(await np.locator('[data-vf-directory-item]:visible').count(),1);cases.push('server combined result without JavaScript');
 await np.goto(base+'/tools/?vf_filter=play&vf_q=encryption');assert.equal(await np.locator('[data-vf-directory-item]:visible').count(),0);assert(await np.locator('[data-vf-directory-empty]').isVisible());cases.push('server empty result without JavaScript');
 await np.goto(base+'/tools/?vf_filter=unregistered');assert.equal(await np.locator('[data-vf-directory-item]:visible').count(),9);cases.push('unknown URL category returns all');
 fs.writeFileSync('proof/directory-browser.json',JSON.stringify({status:'PASS',rows,cases,search_and_filter:'PASS',scope:'THEME_DIRECTORY_REAL_NAVIGATION_NO_MEDIA_REQUESTS'},null,2));await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
