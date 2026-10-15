'use strict';
const fs=require('node:fs'),assert=require('node:assert/strict'),{chromium}=require('playwright');
const phase=process.argv[2]||'candidate',base='http://127.0.0.1:18880',seed=JSON.parse(fs.readFileSync('proof/seed.json')),checks=[],errors=[];
function gate(ok,label,detail){checks.push({pass:!!ok,label,detail});assert(ok,label+' '+JSON.stringify(detail));}
const search=(lang,q='Searchwork Atlas',type='article',page=1)=>base+(lang==='zh'?'/zh/':'/')+'?'+new URLSearchParams({s:q,type,paged:String(page),vf_fixture_count:'1'});
(async()=>{
 const browser=await chromium.launch({headless:true}),ctx=await browser.newContext(),p=await ctx.newPage();p.on('pageerror',e=>errors.push(e.message));
 for(const lang of ['en','zh']){
  await p.goto(search(lang));await p.waitForLoadState('networkidle');
  if(phase==='warm'||phase==='rollback'){
   await p.goto(seed.languages[lang].category);await p.goto(base+(lang==='zh'?'/zh/':'/')+'blog/');continue;
  }
  const grid=p.locator('.vf-theme-search-results-grid');
  gate(await grid.locator('a').count()===3,'saved native count enforced',{lang});
  const text=await grid.innerText();gate(text.includes(lang.toUpperCase())&&!text.includes(lang==='en'?' ZH ':' EN ')&&!text.includes('HIDDEN')&&!text.includes(' Guide '),'native search type language and publication isolation',{lang});
  gate(await p.locator('.vf-theme-search-results').count()===1&&await p.locator('main h1').count()===1,'one search result surface and H1',{lang});
  const form=p.locator('form[data-vf-theme-search-form="wordpress"]');gate(await form.locator('[name="type"]').inputValue()==='article','type retained in actual native form',{lang});
  const first=await grid.locator('a').evaluateAll(a=>a.map(x=>x.href));const nav=p.locator('.vf-theme-pagination--search');
  gate(await nav.locator('.current').count()===1&&await nav.locator('.next').count()===1,'current and next page exposed',{lang});
  await nav.locator('.next').click();await p.waitForLoadState('networkidle');
  const next=await p.locator('.vf-theme-search-results-grid a').evaluateAll(a=>a.map(x=>x.href));gate(next.length===3&&!next.some(x=>first.includes(x)),'actual native next page has no repeated objects',{lang});
  gate(new URL(p.url()).searchParams.get('type')==='article'&&new URL(p.url()).searchParams.get('s')==='Searchwork Atlas','search pagination preserves keyword and type',{lang});
  await p.locator('form[data-vf-theme-search-form="wordpress"] input[type="search"]').fill('Needleword');await p.locator('form[data-vf-theme-search-form="wordpress"] button').click();await p.waitForLoadState('networkidle');
  gate(new URL(p.url()).searchParams.get('type')==='article'&&!new URL(p.url()).searchParams.has('paged')&&(await p.locator('.vf-theme-search-results-grid').innerText()).includes('Needleword'),'resubmit keeps type and returns to first page',{lang});
  await p.goto(search(lang,'Searchwork Atlas','guide'));gate(await p.locator('.vf-theme-search-results-grid a').count()===3&&(await p.locator('.vf-theme-search-results-grid').innerText()).includes('Guide'),'real guide type filter',{lang});
  await p.goto(search(lang,'m3u8','tool'));await p.waitForLoadState('networkidle');
  const tools=await p.locator('.vf-theme-search-results-grid a').evaluateAll(a=>a.map(x=>x.href));gate(tools.length===3,'route-backed tool search honors page size',{lang,count:tools.length,urls:tools,text:(await p.locator('.vf-theme-search-results').innerText()).slice(0,500)});
  gate(await p.locator('.vf-theme-pagination--search .next').count()===1,'real tool routes expose next page',{lang});
  await p.locator('.vf-theme-pagination--search .next').click();const tools2=await p.locator('.vf-theme-search-results-grid a').evaluateAll(a=>a.map(x=>x.href));gate(tools2.length>0&&!tools2.some(x=>tools.includes(x)),'tool page two slices the route set',{lang});
  gate(await p.locator('[data-vf-theme-system-recovery="search"]').count()===0,'matching tools do not show contradictory recovery',{lang});
  await p.goto(search(lang,'zz-no-match-8349','tool'));gate(await p.locator('.vf-theme-search-empty-state').count()===1&&await p.locator('.vf-theme-search-results-grid a').count()===0,'tool no-match never falls back to articles',{lang});
  gate(await p.locator('[data-vf-theme-system-recovery="search"]').count()===1,'empty native search offers recovery',{lang});
  await p.goto(search(lang,'Searchwork Atlas','article',9999));gate(await p.locator('.vf-theme-search-results-grid a').count()>0&&await p.locator('.vf-theme-pagination--search .current').count()===1,'native out-of-range page recovers',{lang});
  await p.goto(seed.languages[lang].category+'?vf_fixture_count=1');await p.waitForLoadState('networkidle');
  const cards=p.locator('[data-vf-post-list-context="archive_list"] .vf-directory-grid a');gate(await cards.count()===3,'native category count bounded',{lang});
  gate((await p.locator('.vf-archive-context-description').innerText()).includes(lang==='en'?'Owner authored':'作者填写'),'authored category description preserved',{lang});
  gate((await p.locator('.vf-content-list-summary').innerText()).includes(lang==='en'?'On this page':'本页'),'archive count clearly page-scoped',{lang});
  const anav=p.locator('.vf-theme-post-list--archive_list .pagination .nav-links');await anav.locator('.next').click();await p.waitForLoadState('networkidle');
  const action=await p.locator('.vf-theme-post-list--archive_list form').getAttribute('action');gate(!/\/page\/\d/.test(action),'archive page-two form returns to page one',{lang});
  const aform=p.locator('.vf-theme-post-list--archive_list form');await aform.locator('input[type="search"]').fill('Needleword');await aform.locator('.vf-directory-submit').click();await p.waitForLoadState('networkidle');
  gate(!/\/page\/\d/.test(new URL(p.url()).pathname)&&await p.locator('.vf-theme-post-list--archive_list .vf-directory-grid a:visible').count()===1,'whole-archive search finds a result beyond the previous page',{lang});
  await p.locator('.vf-theme-post-list--archive_list .vf-directory-reset').click();await p.waitForLoadState('networkidle');gate(!new URL(p.url()).searchParams.has('vf_q'),'archive reset clears URL criteria',{lang});
  await p.goto(seed.languages[lang].category+'?vf_fixture_sort=1');gate((await p.locator('.vf-archive-context-facts').innerText()).includes(lang==='en'?'Title A–Z':'标题 A–Z'),'archive sort description matches configured sort',{lang});
  await p.goto(base+(lang==='zh'?'/zh/':'/')+'blog/?vf_q=Needleword');await p.waitForLoadState('networkidle');gate(await p.locator('.vf-theme-post-list--blog_index .vf-directory-grid a:visible').count()===1,'synthetic blog searches full native content',{lang});
  await p.goto(seed.languages[lang].category+'?vf_q=zz-no-match-8349');gate((await p.locator('[data-vf-directory-empty]').innerText()).includes(lang==='en'?'No matching':'没有匹配'),'archive query-empty is distinct from no published content',{lang});
  for(const width of [1920,1440,1319,1024]){
   await p.setViewportSize({width,height:1000});await p.goto(search(lang));await p.waitForLoadState('networkidle');
   const geom=await p.locator('.vf-theme-search-results').evaluate(el=>({overflow:document.documentElement.scrollWidth>innerWidth+1,width:el.getBoundingClientRect().width,formY:el.querySelector('form').getBoundingClientRect().top,action:el.querySelector('.vf-directory-card-action').getBoundingClientRect().height}));gate(!geom.overflow&&geom.action>=44&&geom.formY<700,'desktop search geometry and action size',{lang,width,...geom});
   if(width===1440)await p.screenshot({path:'proof/search-'+phase+'-'+lang+'.png',fullPage:true});
   await p.goto(seed.languages[lang].category);gate(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'desktop category has no overflow',{lang,width});
   if(width===1440)await p.screenshot({path:'proof/archive-'+phase+'-'+lang+'.png',fullPage:true});
  }
  await p.goto(base+(lang==='zh'?'/zh/':'/')+'search/?q=m3u8&type=tool');await p.waitForLoadState('networkidle');gate(await p.locator('[data-vf-static-search-catalog] [data-vf-search-type="tool"]:visible').count()>0,'existing static local search remains functional',{lang});
 }
 if(phase!=='warm'&&phase!=='rollback'){
  const nativeCtx=await browser.newContext({javaScriptEnabled:false}),n=await nativeCtx.newPage();await n.goto(search('en'));
  await n.locator('form[data-vf-theme-search-form="wordpress"] input[type="search"]').fill('Needleword');await n.locator('form[data-vf-theme-search-form="wordpress"] button').click();gate(await n.locator('.vf-theme-search-results-grid a').count()===1,'native search submit works without JavaScript');
  await n.goto(seed.languages.en.category+'?vf_q=Needleword');await n.locator('a.vf-directory-reset').click();gate(!new URL(n.url()).searchParams.has('vf_q'),'native archive clear works without JavaScript');await nativeCtx.close();gate(errors.length===0,'no uncaught browser errors',errors);
 }
 const admin=await ctx.newPage();const dest=base+'/wp-admin/themes.php?page=vf-theme-modules&tab=layout';await admin.goto(base+'/wp-login.php?redirect_to='+encodeURIComponent(dest));await admin.locator('#user_login').fill('admin');await admin.locator('#user_pass').fill('Synthetic-Only-Update-54!');await admin.locator('#wp-submit').click();await admin.waitForURL('**/wp-admin/**');await admin.goto(dest);await admin.waitForLoadState('networkidle');gate(await admin.locator('[data-vf-frontend-pages]').count()===1,'actual administrator login and frontend directory initialization',{url:admin.url(),title:await admin.title()});await admin.close();
 fs.writeFileSync('proof/browser-'+phase+'.json',JSON.stringify({status:'PASS',phase,checks,mobile:'NOT_RUN_OWNER_DEFERRED',production:'NOT_EXECUTED'},null,2));await browser.close();
})().catch(e=>{fs.writeFileSync('proof/browser-'+phase+'-failure.json',JSON.stringify({status:'FAIL',error:e.message,checks,errors},null,2));console.error(e);process.exit(1)});
