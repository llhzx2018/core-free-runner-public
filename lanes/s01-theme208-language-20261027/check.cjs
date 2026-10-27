const {chromium}=require('playwright'),fs=require('fs'),assert=require('node:assert/strict');
const phase=process.argv[2],fixed=phase==='after',base='http://127.0.0.1:18880';
const norm=s=>s.replaceAll('1.35.208','1.35.207');
(async()=>{
 const browser=await chromium.launch(),context=await browser.newContext(),rows=[],parity={},errors=[];
 for(const lang of ['en','zh'])for(const width of [1440,1024])for(const kind of ['404','unavailable-translation','home','paired-tool']){
  const route=(lang==='zh'?'/zh':'')+(kind==='home'?'/':kind==='paired-tool'?'/m3u8-player/':'/vf-page-check-404/')+(kind==='unavailable-translation'?'?vf_unavailable_translation=1':'');
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));await page.setViewportSize({width,height:1000});
  const response=await page.goto(base+route,{waitUntil:'networkidle'});assert.equal(response.status(),kind==='404'||kind==='unavailable-translation'?404:200);await page.evaluate(()=>document.fonts.ready);
  const key=[lang,width,kind].join('-');
  parity[key]=await page.evaluate(()=>({body:document.querySelector('#content').innerHTML,head:[...document.querySelectorAll('link[rel=canonical],link[rel=alternate][hreflang],meta[name=robots]')].map(e=>e.outerHTML),menu:[...document.querySelectorAll('#vf-primary-nav>a:not(.vf-lang-nav-link),#vf-primary-nav>.vf-nav-item>a')].map(e=>[e.textContent.trim(),e.href,e.getAttribute('aria-current')])}));parity[key]=JSON.parse(norm(JSON.stringify(parity[key])));
  const switcher=page.locator('#vf-site-header [data-vf-lang-switcher-context=header]'),guard=page.locator('#vf-site-header [data-vf-lang-guard]');
  const edge=kind==='unavailable-translation';
  if(edge&&!fixed){assert.equal(await switcher.count(),0);assert.equal(await guard.count(),1);assert.match(await guard.innerText(),/Language|语言/);}
  else{
   assert.equal(await switcher.count(),1);assert.equal(await guard.count(),0);
   const current=switcher.locator('summary'),other=lang==='en'?'zh':'en',target=switcher.locator('a[data-vf-lang-target]');
   assert.equal(await current.getAttribute('data-vf-lang-current'),lang);assert.equal(await switcher.locator('span.is-current[aria-current=true]').getAttribute('data-vf-lang-target'),lang);assert.equal(await switcher.locator(`a[data-vf-lang-target=${lang}]`).count(),0);assert.equal(await target.count(),1);assert.equal(await target.getAttribute('data-vf-lang-target'),other);
   const href=await target.getAttribute('href');assert.ok(href.startsWith(base+'/'));assert.ok(!href.includes('vf-page-check-404'));
   const geo=await page.evaluate(()=>{const h=document.querySelector('#vf-site-header'),r=e=>{const b=e.getBoundingClientRect();return{x:b.x,right:b.right,y:b.y,width:b.width,height:b.height}},nav=h.querySelector('#vf-primary-nav'),items=[...nav.children].filter(e=>e.matches('a:not(.vf-lang-nav-link),.vf-nav-item')).map(e=>r(e)),control=r(h.querySelector('[data-vf-lang-switcher-context=header]')),actions=r(h.querySelector('.vf-header-actions')),inner=r(h.querySelector('.vf-header-inner'));return{control,actions,inner,items,overflow:document.documentElement.scrollWidth>innerWidth+1};});
   assert.equal(geo.overflow,false);assert.ok(geo.control.x>=geo.items.at(-1).right+4);assert.ok(geo.actions.x>=geo.control.right+4);assert.ok(geo.actions.right<=geo.inner.right+1);assert.ok(geo.control.height>=40);assert.ok(geo.items.every((x,i)=>!i||x.x>=geo.items[i-1].right+4));
   fs.writeFileSync(`proof/${phase}-geometry-${key}.json`,JSON.stringify(geo,null,2));
   if(fixed&&edge){
    await page.screenshot({path:`proof/404-${lang}-${width}.png`,fullPage:true});
    await current.press('Enter');await page.waitForFunction(()=>{const d=document.querySelector('#vf-site-header [data-vf-lang-switcher-context=header]');return d.open&&d.querySelector('summary').getAttribute('aria-expanded')==='true';});await target.waitFor({state:'visible'});
    const panel=await switcher.locator('.vf-lang-panel').boundingBox();assert.ok(panel.x>=0&&panel.x+panel.width<=width);await target.press('Escape');await page.waitForFunction(()=>{const d=document.querySelector('#vf-site-header [data-vf-lang-switcher-context=header]');return !d.open&&d.querySelector('summary').getAttribute('aria-expanded')==='false';});assert.ok(await current.evaluate(e=>document.activeElement===e));
    await current.click();await page.locator('h1').click();await page.waitForFunction(()=>!document.querySelector('#vf-site-header [data-vf-lang-switcher-context=header]').open);
    await current.click();await page.locator('#vf-site-header').screenshot({path:`proof/language-open-${lang}-${width}.png`});await target.click();assert.equal(page.url(),href);assert.ok((await page.locator('html').getAttribute('lang')).toLowerCase().startsWith(other));
   }
  }
  rows.push({language:lang,width,kind,status:'PASS',expected:edge&&!fixed?'BASELINE_GUARD_REPRODUCED':'CANONICAL_DROPDOWN'});await page.close();
 }
 assert.deepEqual(errors,[]);
 if(fixed){assert.deepEqual(parity,JSON.parse(fs.readFileSync('proof/before-parity.json','utf8')),'unchanged404/home/tool bodies,SEO and authored menus');
  const nojs=await browser.newContext({javaScriptEnabled:false});for(const lang of ['en','zh']){const page=await nojs.newPage({viewport:{width:1440,height:1000}});assert.equal((await page.goto(base+(lang==='zh'?'/zh':'')+'/vf-page-check-404/?vf_unavailable_translation=1')).status(),404);const control=page.locator('#vf-site-header [data-vf-lang-switcher-context=header]');await control.locator('summary').click();assert.equal(await control.getAttribute('open'),'');assert.ok(await control.locator('a[data-vf-lang-target]').isVisible());await page.close();}await nojs.close();
 }
 fs.writeFileSync(`proof/${phase}-parity.json`,JSON.stringify(parity));fs.writeFileSync(`proof/${phase}-results.json`,JSON.stringify({status:'PASS',phase,cases:rows.length,rows,noJavaScript:fixed?'PASS':'NOT_RUN',bodyHeadMenuParity:fixed?'PASS':'BASELINE',production:'UNTOUCHED'},null,2));console.log(`${phase.toUpperCase()}_BILINGUAL_HEADER_16_CASES_PASS`);await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
