const fs=require('fs'),assert=require('assert/strict'),{chromium}=require('playwright');
(async()=>{
 const phase=process.argv.find(x=>x.startsWith('--phase='))?.split('=')[1]||'after',fixed=phase==='after';
 const urls=JSON.parse(fs.readFileSync('proof/search-fixtures.json')),b=await chromium.launch(),c=await b.newContext(),p=await c.newPage();
 const rows=[],errors=[],writes=[];let checks=0;
 p.on('pageerror',e=>errors.push(e.message));c.on('request',r=>{if(r.url().startsWith('http://127.0.0.1:18880')&&!['GET','HEAD','OPTIONS'].includes(r.method()))writes.push(r.method());});
 const go=async u=>{assert.equal((await p.goto(u,{waitUntil:'networkidle'})).status(),200);await p.evaluate(()=>document.fonts.ready);};
 const cards=()=>p.locator('.vf-theme-search-results-grid .vf-directory-card--search:visible');
 const home=()=>p.locator('header [data-vf-nav-location="header"][data-vf-nav-route=""]');
 const snap=()=>p.evaluate(()=>({title:document.title,h1:[...document.querySelectorAll('h1')].map(x=>x.textContent),head:[...document.head.querySelectorAll('meta:not([name^="vf-"]),link[rel="canonical"],link[rel="alternate"],script[type="application/ld+json"]')].map(x=>x.outerHTML),cards:[...document.querySelectorAll('.vf-theme-search-results-grid>a')].map(x=>[x.getAttribute('href'),x.querySelector('h3').textContent]),pagination:[...document.querySelectorAll('.vf-theme-pagination a')].map(x=>x.getAttribute('href'))}));
 const screenshot=async name=>p.screenshot({path:'proof/'+name+'.png',fullPage:true});
 for(const lang of ['en','zh']){
  await p.setViewportSize({width:1440,height:1050});await go(urls[lang].search);
  assert.equal(await cards().count(),3);assert.equal(await home().count(),1);checks+=2;
  const data=await snap(),file='proof/baseline-'+lang+'.json';if(phase==='before')fs.writeFileSync(file,JSON.stringify(data));else assert.deepEqual(data,JSON.parse(fs.readFileSync(file)));checks++;
  const excerpt=await cards().first().locator('p').innerText(),active=await home().getAttribute('aria-current');
  if(phase==='before'){assert.notEqual(excerpt,urls[lang].authored);assert.equal(active,'page');checks+=2;fs.writeFileSync('proof/reproduced-'+lang+'.json',JSON.stringify({excerpt,expected:urls[lang].authored,homeActive:active}));}
  if(fixed){
   assert.equal(excerpt,urls[lang].authored);assert.equal(active,null);assert.equal(await p.locator('header a.is-active').count(),0);checks+=3;
   for(const width of [1440,1024]){
    await p.setViewportSize({width,height:1050});await go(urls[lang].search);
    assert.equal(await cards().first().locator('p').innerText(),urls[lang].authored);assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);assert.equal(await p.locator('.vf-directory-card-action').count(),0);checks+=3;
    const nav=await p.locator('.vf-theme-pagination').evaluate(e=>({border:getComputedStyle(e.querySelector('ul')).borderWidth,height:e.querySelector('.current').getBoundingClientRect().height}));assert.equal(nav.border,'0px');assert.ok(nav.height>=44);checks+=2;
    await screenshot(`search-${lang}-${width}`);
   }
   await p.locator('.vf-theme-pagination a.next').click();await p.waitForLoadState('networkidle');assert.equal(await home().getAttribute('aria-current'),null);assert.equal(await cards().first().locator('p').innerText(),urls[lang].authored);checks+=2;
   await p.locator('.vf-theme-pagination .page-numbers').filter({hasText:/^\d+$/}).last().click();await p.waitForLoadState('networkidle');const fallback=await cards().first().locator('p').innerText();
   assert.equal(await cards().count(),1);assert.ok(fallback.endsWith('…'));assert.equal(await p.locator('.vf-theme-pagination a.next').count(),0);assert.equal(await home().getAttribute('aria-current'),null);assert.ok(!fallback.includes('EXECUTED_SUMMARY_PROBE'));checks+=5;
   if(lang==='zh'){assert.ok(fallback.length>60&&fallback.length<=90,fallback);checks++;}
   await go(urls[lang].entry);assert.equal(await cards().count(),10);assert.equal(await p.locator('[data-vf-static-search-item][hidden]:visible').count(),0);assert.equal(await cards().first().locator('p').innerText(),urls[lang].authored);assert.equal(await home().getAttribute('aria-current'),null);assert.equal(await p.locator('main script').count(),0);checks+=5;await screenshot('search-static-'+lang);
   const nc=await b.newContext({javaScriptEnabled:false}),np=await nc.newPage();await np.goto(urls[lang].search);assert.equal(await np.locator('.vf-theme-search-results-grid>a p').first().innerText(),urls[lang].authored);assert.equal(await np.locator('header [data-vf-nav-route=""][aria-current]').count(),0);checks+=2;await nc.close();
   await go(urls[lang].home);assert.equal(await home().getAttribute('aria-current'),'page');checks++;
   await go(urls[lang].tools);assert.equal(await home().getAttribute('aria-current'),null);assert.equal(await p.locator('header [data-vf-nav-route="tools"]').getAttribute('aria-current'),'page');checks+=2;
   await go(urls[lang].search.replace('Search206','NoMatch206'));assert.equal(await cards().count(),0);assert.equal(await home().getAttribute('aria-current'),null);assert.equal(await p.locator('.vf-theme-search-empty-state h2').count(),1);checks+=3;
  }
  await go(urls[lang].blog);const blog=await p.locator('.vf-theme-post-list--blog_index .vf-directory-card p').allTextContents(),bf='proof/baseline-blog-'+lang+'.json';if(phase==='before')fs.writeFileSync(bf,JSON.stringify(blog));else assert.deepEqual(blog,JSON.parse(fs.readFileSync(bf)));checks++;
  rows.push({lang,status:'PASS'});
 }
 assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);
 fs.writeFileSync(`proof/search-${phase}.json`,JSON.stringify({status:'PASS',phase,checks,rows,errors,writes,operationalAcceptance:'OWNER_REVIEW_REQUIRED_AFTER_MANUAL_UPGRADE'}));console.log(`SEARCH_${phase.toUpperCase()}_PASS ${checks}`);await b.close();
})().catch(e=>{console.error(e);process.exit(1)});
