const fs=require('fs'),assert=require('assert/strict'),{chromium}=require('playwright');
(async()=>{
 const phase=process.argv.find(x=>x.startsWith('--phase='))?.split('=')[1]||'after',fixed=phase==='after';
 const urls=JSON.parse(fs.readFileSync('proof/search-fixtures.json')),b=await chromium.launch(),c=await b.newContext(),p=await c.newPage();
 const errors=[],writes=[],rows=[];let checks=0;
 p.on('pageerror',e=>errors.push(e.message));c.on('request',r=>{if(r.url().startsWith('http://127.0.0.1:18880')&&!['GET','HEAD','OPTIONS'].includes(r.method()))writes.push(r.method());});
 const go=async url=>{assert.equal((await p.goto(url,{waitUntil:'networkidle'})).status(),200);await p.evaluate(()=>document.fonts.ready);};
 const cards=()=>p.locator('.vf-theme-search-results-grid .vf-directory-card--search:visible');
 const snap=()=>p.evaluate(()=>({title:document.title,h1:[...document.querySelectorAll('h1')].map(x=>x.textContent),head:[...document.head.querySelectorAll('meta:not([name^="vf-"]),link[rel="canonical"],link[rel="alternate"],script[type="application/ld+json"]')].map(x=>x.outerHTML),cards:[...document.querySelectorAll('.vf-theme-search-results-grid>a')].map(x=>({href:x.getAttribute('href'),title:x.querySelector('h3').textContent,description:x.querySelector('p')?.textContent})),pagination:[...document.querySelectorAll('.vf-theme-pagination a')].map(x=>x.getAttribute('href'))}));
 const noOverflow=async()=>{assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);checks++;};
 const shot=async(name)=>{await p.screenshot({path:`proof/${name}.png`,fullPage:true});};
 for(const lang of ['en','zh']){
  await p.setViewportSize({width:1440,height:1000});await go(urls[lang].search);
  assert.equal(await cards().count(),3);assert.equal(await p.locator('h1').count(),1);assert.equal(await p.locator('main form[role="search"]').count(),1);checks+=3;
  const s=await snap(),f=`proof/baseline-search-${lang}.json`;if(phase==='before')fs.writeFileSync(f,JSON.stringify(s));else assert.deepEqual(s,JSON.parse(fs.readFileSync(f)),lang+' native content/head/query links');checks++;
  assert.ok((await cards().allTextContents()).every(t=>t.includes(lang)),lang+' current language');checks++;
  if(fixed){
   assert.equal(await p.locator('.vf-theme-search-workspace-head').count(),0);assert.equal(await p.locator('.vf-theme-search-results-grid .vf-directory-card-action').count(),0);assert.equal(await p.locator('.vf-theme-search-list-head h2').count(),1);checks+=3;
   for(const width of [1440,1024]){
    await p.setViewportSize({width,height:1000});await go(urls[lang].search);await noOverflow();
    const metrics=await p.locator('.vf-theme-search-workspace').evaluate(e=>{const s=getComputedStyle(e),form=e.querySelector('form').getBoundingClientRect(),hero=document.querySelector('.vf-family-hero .container-wide').getBoundingClientRect(),r=e.getBoundingClientRect();return{border:s.borderWidth,padding:s.padding,shadow:s.boxShadow,heroX:hero.x,workspaceX:r.x,formX:form.x,formY:form.y,heroBottom:hero.bottom,heading:e.closest('main').querySelector('h1').getBoundingClientRect().x};});
    fs.writeFileSync(`proof/metrics-${lang}-${width}.json`,JSON.stringify(metrics));await shot(`search-${lang}-${width}`);assert.equal(metrics.border,'0px');assert.equal(metrics.padding,'0px');assert.equal(metrics.shadow,'none');assert.ok(Math.abs(metrics.heading-metrics.formX)<=2);assert.ok(metrics.formY-metrics.heroBottom<=50);checks+=5;
    const nav=await p.locator('.vf-theme-pagination').evaluate(e=>{const s=getComputedStyle(e.querySelector('ul'));return{border:s.borderWidth,background:s.backgroundColor,height:e.querySelector('.current').getBoundingClientRect().height};});assert.equal(nav.border,'0px');assert.equal(nav.background,'rgba(0, 0, 0, 0)');assert.ok(nav.height>=44);checks+=3;
    fs.writeFileSync(`proof/metrics-${lang}-${width}.json`,JSON.stringify(metrics));await shot(`search-${lang}-${width}`);
   }
   const first=await cards().allTextContents();await p.locator('.vf-theme-pagination a.next').click();await p.waitForLoadState('networkidle');assert.equal(new URL(p.url()).searchParams.get('s'),'Search205');assert.notDeepEqual(await cards().allTextContents(),first);checks+=2;
   await p.locator('.vf-theme-pagination .page-numbers').filter({hasText:/^\d+$/}).last().click();await p.waitForLoadState('networkidle');assert.equal(await p.locator('.vf-theme-pagination a.next').count(),0);assert.equal(await p.locator('.vf-theme-pagination a.prev').count(),1);checks+=2;
   await go(urls[lang].search+'&type=guide');assert.ok((await cards().allTextContents()).every(t=>t.includes('vf_guide')));const filter=p.locator('[data-vf-search-type-filters] [aria-current="page"]');assert.equal(await filter.count(),1);assert.equal(await p.locator('main form input[name="type"]').inputValue(),'guide');checks+=3;
   await p.locator('.vf-theme-pagination a.next').click();await p.waitForLoadState('networkidle');assert.equal(new URL(p.url()).searchParams.get('type'),'guide');assert.equal(await cards().count(),1);checks+=2;
   const box=p.locator('main input[type="search"]');await box.fill('Search205 01');await box.press('Enter');await p.waitForLoadState('networkidle');assert.equal(await cards().count(),1);assert.equal(await p.locator('.vf-theme-pagination').count(),0);checks+=2;
   await go(urls[lang].search.replace('Search205','M3U8')+'&type=tool');assert.ok(await cards().count()>0);assert.ok((await p.locator('.vf-theme-search-results-grid a').first().getAttribute('href')).includes(lang==='zh'?'/zh/':'/'));checks+=2;
   await go(urls[lang].search.replace('Search205','NoMatch205'));assert.equal(await cards().count(),0);assert.equal(await p.locator('.vf-theme-search-empty-state h2').count(),1);assert.equal(await p.locator('[data-vf-theme-system-recovery="search"]').count(),1);assert.equal(await p.locator('main form[role="search"]').count(),1);checks+=4;await shot(`search-empty-${lang}`);
   await p.locator('.vf-theme-search-clear').click();await p.waitForLoadState('networkidle');assert.equal(await p.locator('main input[type="search"]').inputValue(),'');checks++;
   const nativeNoJS=await b.newContext({javaScriptEnabled:false,viewport:{width:1024,height:1000}}),np=await nativeNoJS.newPage();await np.goto(urls[lang].search+'&type=article');assert.equal(await np.locator('.vf-theme-search-results-grid>a').count(),3);await np.locator('.vf-theme-pagination a.next').click();assert.equal(new URL(np.url()).searchParams.get('type'),'article');assert.equal(await np.locator('.vf-theme-search-results-grid>a').count(),3);checks+=3;await nativeNoJS.close();
   await go(urls[lang].blog);const summary=await p.locator('.vf-content-list-summary').innerText();assert.ok(summary.includes(lang==='zh'?'第 10 篇，共 10 篇文章':'Article 10 of 10'),summary);checks++;
  }
  await go(urls[lang].entry);const total=await p.locator('[data-vf-static-search-item]').count(),hiddenVisible=await p.locator('[data-vf-static-search-item][hidden]:visible').count();assert.ok(total>3);checks++;
  if(phase==='before'){assert.ok(hiddenVisible>0);fs.writeFileSync(`proof/reproduced-hidden-${lang}.json`,JSON.stringify({total,hiddenVisible,visible:await cards().count()}));}
  if(fixed){
   assert.equal(hiddenVisible,0);assert.equal(await cards().count(),3);checks+=2;await shot(`search-entry-${lang}`);
   const tools=p.locator('[data-vf-search-type-button="tool"]');await tools.click();assert.equal(await tools.getAttribute('aria-pressed'),'true');assert.equal(await p.locator('[data-vf-static-search-item][hidden]:visible').count(),0);assert.ok(await cards().count()>0);assert.ok((await cards().evaluateAll(es=>es.map(e=>e.dataset.vfSearchType))).every(t=>t==='tool'));checks+=4;
   const query=p.locator('main input[type="search"]');await query.fill('NoMatch205');await query.press('Enter');await p.waitForLoadState('networkidle');assert.equal(await cards().count(),0);assert.equal(await p.locator('[data-vf-static-search-recovery]:visible').count(),1);checks+=2;await shot(`search-static-empty-${lang}`);
   await go(urls[lang].entry+'?q=Search205&type=article');assert.equal(await cards().count(),10);assert.equal(await p.locator('[data-vf-static-search-recovery]:visible').count(),0);assert.equal(await p.locator('[data-vf-static-search-item][hidden]:visible').count(),0);checks+=3;
   const selected=p.locator('[data-vf-search-type-button="article"]');await selected.focus();await p.keyboard.press('Tab');await p.keyboard.press('Shift+Tab');assert.ok(await selected.evaluate(e=>e.matches(':focus-visible')&&parseFloat(getComputedStyle(e).outlineWidth)>=2));checks++;await shot(`search-focus-${lang}`);
   const special='<img src=x onerror=alert(205)>';await go(urls[lang].search.replace('Search205',encodeURIComponent(special)));assert.equal(await p.locator('main input[type="search"]').inputValue(),special);assert.equal(await p.locator('main img[onerror]').count(),0);assert.equal(await p.locator('main script').count(),0);checks+=3;
  }
  rows.push({lang,status:'PASS'});
 }
 assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);
 fs.writeFileSync(`proof/search-${phase}.json`,JSON.stringify({status:'PASS',phase,checks,rows,errors,writes,operationalAcceptance:'OWNER_REVIEW_REQUIRED_AFTER_MANUAL_UPGRADE'}));console.log(`SEARCH_${phase.toUpperCase()}_PASS ${checks}`);await b.close();
})().catch(e=>{console.error(e);process.exit(1)});
