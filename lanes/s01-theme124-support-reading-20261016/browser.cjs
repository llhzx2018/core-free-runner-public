'use strict';
const fs=require('node:fs'),assert=require('node:assert/strict'),{chromium}=require('playwright');
const phase=process.argv[2]||'candidate',base='http://127.0.0.1:18880',seed=JSON.parse(fs.readFileSync('proof/seed.json')),checks=[],errors=[];
function gate(ok,label,detail){checks.push({pass:!!ok,label,detail});}
const search=(lang,q='Searchwork Atlas',type='article',page=1)=>base+(lang==='zh'?'/zh/':'/')+'?'+new URLSearchParams({s:q,type,paged:String(page),vf_fixture_count:'1'});
(async()=>{
 const browser=await chromium.launch({headless:true}),ctx=await browser.newContext(),p=await ctx.newPage();p.on('pageerror',e=>errors.push(e.message));p.setDefaultTimeout(8000);
 const scenario=async(label,fn)=>{const before=checks.length;try{await fn();}catch(e){gate(false,label+' flow',{error:e.message,url:p.url()});}if(checks.slice(before).some(c=>!c.pass)){const html=await p.content();const m=html.match(/search-archive-diag:(.+) -->/);checks.push({pass:true,label:label+' failure diagnostic',detail:{url:p.url(),diagnostic:m?JSON.parse(m[1]):null}});await p.screenshot({path:'proof/failure-'+phase+'-'+label.replace(/[^a-z0-9_-]/gi,'-')+'.png',fullPage:true});}};
 for(const lang of ['en','zh']){
  await p.goto(search(lang));await p.waitForLoadState('networkidle');
  if(phase==='warm'||phase==='rollback'){
   await p.goto(seed.languages[lang].category);await p.goto(base+(lang==='zh'?'/zh/':'/')+'blog/');for(const route of ['about/','contact/','privacy-policy/','terms/','vf-owner-missing-124/'])await p.goto(base+(lang==='zh'?'/zh/':'/')+route);continue;
  }
  await scenario(lang+'-native',async()=>{
  const grid=p.locator('.vf-theme-search-results-grid');
  gate(await grid.locator('a').count()===3,'saved native count enforced',{lang});
  const text=await grid.innerText();gate(text.includes(lang.toUpperCase())&&!text.includes(lang==='en'?' ZH ':' EN ')&&!text.includes('HIDDEN')&&!text.includes(' Guide '),'native search type language and publication isolation',{lang});
  gate(await p.locator('.vf-theme-search-results').count()===1&&await p.locator('main h1').count()===1,'one search result surface and H1',{lang});
  const form=p.locator('form[data-vf-theme-search-form="wordpress"]');gate(await form.locator('[name="type"]').inputValue()==='article','type retained in actual native form',{lang});
  const first=await grid.locator('a').evaluateAll(a=>a.map(x=>x.href));const nav=p.locator('.vf-theme-pagination--search');
  gate(await nav.locator('.current').count()===1&&await nav.locator('.next').count()===1,'current and next page exposed',{lang});
  await nav.locator('.next').click();await p.waitForLoadState('networkidle');
  const next=await p.locator('.vf-theme-search-results-grid a').evaluateAll(a=>a.map(x=>x.href));gate(next.length===Math.min(3,seed.languages[lang].ids.length-3)&&!next.some(x=>first.includes(x)),'actual native next page has no repeated objects',{lang});
  gate(new URL(p.url()).searchParams.get('type')==='article'&&new URL(p.url()).searchParams.get('s')==='Searchwork Atlas','search pagination preserves keyword and type',{lang});
  await p.locator('form[data-vf-theme-search-form="wordpress"] input[type="search"]').fill('Needleword');await p.locator('form[data-vf-theme-search-form="wordpress"] button').click();await p.waitForLoadState('networkidle');
  gate(new URL(p.url()).searchParams.get('type')==='article'&&!new URL(p.url()).searchParams.has('paged')&&(await p.locator('.vf-theme-search-results-grid').innerText()).includes('Needleword'),'resubmit keeps type and returns to first page',{lang});
  await p.goto(search(lang,'Searchwork Atlas','guide'));gate(await p.locator('.vf-theme-search-results-grid a').count()===3&&(await p.locator('.vf-theme-search-results-grid').innerText()).includes('Guide'),'real guide type filter',{lang});
  });
  await scenario(lang+'-public-copy',async()=>{
  await p.goto(search(lang,'Snippetwork','page'));const rows=p.locator('.vf-theme-search-results-grid');gate(await rows.locator('a').count()===2,'passive summary fixture pages returned',{lang});
  const summary=await rows.innerText();gate(!summary.includes('[vf_')&&!summary.includes('secret=')&&summary.includes('Authored public summary')&&summary.includes(lang==='zh'?'打开页面查看完整内容':'Open the page to read the full content'),'shortcode-only fallback and authored summary visible without implementation tokens',{lang});
  const dates=await rows.locator('time').allTextContents();gate(dates.length===2&&dates.every(x=>lang==='zh'?/^\d{4}年\d{1,2}月\d{1,2}日$/.test(x):x.length>0),'actual public date format follows page language',{lang,dates});
  for(const fixture of ['legacy_en','legacy_zh','custom']){await p.goto(base+(lang==='zh'?'/zh/':'/')+'blog/?vf_fixture_copy='+fixture);const copy=await p.locator('.vf-theme-post-list--blog_index .vf-family-section-head p').innerText();gate(fixture==='custom'?copy==='Owner public description 2026':!copy.includes('SEO')&&copy.includes(lang==='zh'?'工具笔记':'Tool notes'),'blog legacy default replacement or authored copy preservation',{lang,fixture,copy});}
  });
  await scenario(lang+'-company-system',async()=>{
  const root=base+(lang==='zh'?'/zh/':'/');
  await p.goto(root+'about/');gate((await p.locator('.vf-support-user-content').innerText()).includes('Owner published text '+lang),'about retains authored current-language body',{lang,url:p.url(),body:(await p.locator('.vf-support-user-content').innerText()).slice(0,300)});
  await p.goto(root+'contact/');const channel=p.locator('#contact-channel');gate(await channel.count()===1&&(await channel.innerText()).includes('Owner contact '+lang),'real contact content retained once',{lang,url:p.url(),body:(await channel.innerText()).slice(0,300)});
  const order=await p.evaluate(()=>document.querySelector('#contact-channel').getBoundingClientRect().top<document.querySelector('.vf-support-operations').getBoundingClientRect().top);gate(order,'contact channel precedes preparation guidance',{lang});
  gate(await channel.locator('a[href="mailto:support@example.invalid"]').count()===1,'authored contact target retained without sending',{lang});
  const primary=p.locator('.vf-support-hero-actions .is-primary');gate((await primary.innerText())===(lang==='zh'?'查看支持选项':'View support options'),'contact hero accurately describes available support options',{lang});await primary.click();gate(new URL(p.url()).hash==='#contact-checklist','support primary action reaches an existing section',{lang});
  await p.goto(root+'contact/?vf_fixture_support=empty');gate(await p.locator('.vf-contact-no-channel').count()===1&&await p.locator('.vf-contact-channel a').count()===0,'unconfigured contact is honest and has no fake submit',{lang});
  const help=p.locator('.vf-contact-no-channel-actions');gate(await help.locator('a').count()===2&&await p.locator('.vf-contact-no-channel input,.vf-contact-no-channel button').count()===0,'empty contact provides help links without an inactive form',{lang});
  await help.locator('a').first().click();gate(new URL(p.url()).pathname===(lang==='zh'?'/zh/faq/':'/faq/'),'empty contact FAQ link reaches the correct language route',{lang});
  await p.goto(root+'contact/?vf_fixture_support=empty');await p.locator('.vf-contact-no-channel-actions a').last().click();gate(new URL(p.url()).pathname===(lang==='zh'?'/zh/tools/':'/tools/'),'empty contact tools link reaches the correct language route',{lang});
  });
  await scenario(lang+'-legal-documents',async()=>{
  const root=base+(lang==='zh'?'/zh/':'/');
  for(const route of (lang==='en'?['privacy-policy','acceptable-use']:['privacy-policy'])){
   await p.goto(root+route+'/');const nav=p.locator('.vf-policy-nav');gate(await nav.locator('[aria-current="page"]').count()===1,'policy navigation marks current document',{lang,route});
   gate(await nav.locator('a[href*="/dmca/"]').count()===0&&await nav.locator('a[href*="/acceptable-use/"]').count()===(lang==='en'?1:0),'policy navigation excludes draft and includes published documents',{lang,route,links:await nav.locator('a').evaluateAll(a=>a.map(x=>({text:x.textContent,href:x.href})))});
   const doc=p.locator('.vf-policy-user-content');gate((await doc.innerText()).includes('Owner published text '+lang),'policy authored text and language retained',{lang,route});
   const toc=p.locator('.vf-policy-section-toc a[href^="#"]');gate(await toc.count()>=2,'policy has real heading navigation',{lang,route});
   if(await toc.count()){const href=await toc.first().getAttribute('href');await toc.first().click();gate(await p.evaluate(id=>!!document.getElementById(id),decodeURIComponent(href.slice(1))),'policy section link targets a real heading',{lang,route});}
  }
  });
  await scenario(lang+'-support-empty-hidden',async()=>{
  const root=base+(lang==='zh'?'/zh/':'/');
  await p.goto(root+'terms/');gate(await p.locator('.vf-policy-missing').count()===1&&!(await p.locator('.vf-policy-missing').innerText()).includes('WordPress'),'missing legal text is visitor-facing and not fabricated',{lang});
  for(const [route,selector] of [['about','.vf-about-principles'],['contact','#contact-channel'],['privacy-policy','.vf-policy-sidebar']]){await p.goto(root+route+'/?vf_fixture_support=hide');gate(await p.locator(selector).count()===0,'saved support visibility controls remain effective',{lang,route});}
  });
  await scenario(lang+'-404-native',async()=>{
  const root=base+(lang==='zh'?'/zh/':'/');
  const missing=root+'vf-owner-missing-124/';const response=await p.goto(missing);gate(response.status()===404&&(response.headers()['x-robots-tag']||'').includes('noindex'),'real 404 keeps HTTP status and noindex',{lang});
  gate(await p.locator('main h1').count()===1&&await p.locator('form[data-vf-theme-search-form="wordpress"] input[name="s"]').count()===1,'404 has one title and native search',{lang});
  const popular=p.locator('.vf-theme-system-query-chips a').first();gate(!!new URL(await popular.getAttribute('href'),base).searchParams.get('s'),'404 popular query uses the same native search',{lang});
  await popular.click();gate(new URL(p.url()).searchParams.has('s')&&await p.locator('.vf-theme-search-results').count()===1,'404 popular query opens actual search results',{lang});
  });
  await scenario(lang+'-company-geometry',async()=>{
  const root=base+(lang==='zh'?'/zh/':'/');
  for(const width of [1920,1440,1319,1024])for(const [route,kind] of [['about/','about'],['contact/','contact'],['privacy-policy/','legal'],['vf-owner-missing-124/','404']]){
   await p.setViewportSize({width,height:1000});await p.goto(root+route);gate(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'company/system desktop has no overflow',{lang,width,kind});
   const shell=p.locator(kind==='404'?'.vf-theme-system-recovery--404':'.vf-support-content--'+(kind==='legal'?'legal':kind));
   const rail=await shell.evaluate(e=>{const c=e.querySelector(':scope>.container-wide'),s=getComputedStyle(e),r=e.getBoundingClientRect(),cr=c.getBoundingClientRect();return {radius:s.borderRadius,shadow:s.boxShadow,border:parseFloat(s.borderTopWidth),inset:cr.left-r.left,right:r.right-cr.right,width:cr.width}});
   gate(rail.radius==='0px'&&rail.shadow==='none'&&rail.border===0&&rail.inset>=23&&rail.right>=23&&rail.width<=1101,'support content has a quiet rail and real edge spacing',{lang,width,kind,...rail});
   if(kind==='about'||kind==='contact'){const heads=await shell.locator('.vf-support-content-head h2').evaluateAll(a=>a.map(e=>parseFloat(getComputedStyle(e).fontSize)));gate(heads.length>0&&heads.every(n=>n<=30),'support section headings stay subordinate to the page title',{lang,width,kind,heads});}
   if(kind==='about'){const ratio=await shell.evaluate(e=>e.querySelector('.vf-support-user-content').getBoundingClientRect().width/e.querySelector(':scope>.container-wide').getBoundingClientRect().width);gate(ratio>=.98,'authored About body uses the content rail without a nested narrow card',{lang,width,ratio});}
   if(kind==='legal'){const g=await p.locator('.vf-policy-document').evaluate(e=>({radius:getComputedStyle(e).borderRadius,shadow:getComputedStyle(e).boxShadow,width:e.getBoundingClientRect().width}));gate(g.radius==='0px'&&g.shadow==='none'&&g.width<=940,'legal document uses a quiet bounded reading rail',{lang,width,...g});}
   if(width===1440)await p.screenshot({path:'proof/company-'+phase+'-'+lang+'-'+kind+'.png',fullPage:true});
  }
  });
  await scenario(lang+'-404-nojs',async()=>{
  const root=base+(lang==='zh'?'/zh/':'/'),missing=root+'vf-owner-missing-124/';
  const nojs=await browser.newContext({javaScriptEnabled:false}),np=await nojs.newPage();await np.goto(missing);await np.locator('input[name="s"]').fill('Snippetwork');await np.locator('form[data-vf-theme-search-form="wordpress"] button').click();gate(await np.locator('.vf-theme-search-results-grid a').count()===2,'404 native search works without JavaScript',{lang});await nojs.close();
  });
  await scenario(lang+'-tools',async()=>{
  await p.goto(search(lang,'m3u8','tool'));await p.waitForLoadState('networkidle');
  const tools=await p.locator('.vf-theme-search-results-grid a').evaluateAll(a=>a.map(x=>x.href));gate(tools.length===3,'route-backed tool search honors page size',{lang,count:tools.length,urls:tools,text:(await p.locator('.vf-theme-search-results').innerText()).slice(0,500)});
  gate(await p.locator('.vf-theme-pagination--search .next').count()===1,'real tool routes expose next page',{lang});
  await p.locator('.vf-theme-pagination--search .next').click();await p.waitForLoadState('networkidle');const tools2=await p.locator('.vf-theme-search-results-grid a').evaluateAll(a=>a.map(x=>x.href));gate(tools2.length>0&&!tools2.some(x=>tools.includes(x)),'tool page two slices the route set',{lang});
  gate(await p.locator('[data-vf-theme-system-recovery="search"]').count()===0,'matching tools do not show contradictory recovery',{lang});
  await p.goto(search(lang,'zz-no-match-8349','tool'));gate(await p.locator('.vf-theme-search-empty-state').count()===1&&await p.locator('.vf-theme-search-results-grid a').count()===0,'tool no-match never falls back to articles',{lang});
  gate(await p.locator('[data-vf-theme-system-recovery="search"]').count()===1,'empty native search offers recovery',{lang});
  });
  await scenario(lang+'-out-of-range',async()=>{
  await p.goto(search(lang,'Searchwork Atlas','article',9999));gate(await p.locator('.vf-theme-search-results-grid a').count()>0&&await p.locator('.vf-theme-pagination--search .current').count()===1,'native out-of-range page recovers',{lang});
  });
  await scenario(lang+'-archive',async()=>{
  await p.goto(seed.languages[lang].category+'?vf_fixture_count=1');await p.waitForLoadState('networkidle');
  const cards=p.locator('[data-vf-post-list-context="archive_list"] .vf-directory-grid a');gate(await cards.count()===3,'native category count bounded',{lang});
  const seen=[];for(let walk=0;walk<10;walk++) {const current=await p.locator('.vf-theme-post-list--archive_list .vf-directory-grid a').evaluateAll(a=>a.map(x=>x.href));seen.push(...current);const more=p.locator('.vf-theme-post-list--archive_list .pagination .next');if(!await more.count())break;await more.click();await p.waitForLoadState('networkidle');}
  gate(seen.length===seed.languages[lang].ids.length&&new Set(seen).size===seen.length,'every native archive object is reachable across all pages',{lang,seen:seen.length,expected:seed.languages[lang].ids.length});
  await p.goto(seed.languages[lang].category+'?vf_fixture_count=1');await p.waitForLoadState('networkidle');
  gate((await p.locator('.vf-archive-context-description').innerText()).includes(lang==='en'?'Owner authored':'作者填写'),'authored category description preserved',{lang});
  gate((await p.locator('.vf-content-list-summary').innerText()).includes(lang==='en'?'On this page':'本页'),'archive count clearly page-scoped',{lang});
  const anav=p.locator('.vf-theme-post-list--archive_list .pagination .nav-links');await anav.locator('.next').click();await p.waitForLoadState('networkidle');
  const action=await p.locator('.vf-theme-post-list--archive_list form').getAttribute('action');gate(!/\/page\/\d/.test(action),'archive page-two form returns to page one',{lang});
  const aform=p.locator('.vf-theme-post-list--archive_list form');await aform.locator('input[type="search"]').fill('Needleword');await aform.locator('.vf-directory-submit').click();await p.waitForLoadState('networkidle');
  gate(!/\/page\/\d/.test(new URL(p.url()).pathname)&&await p.locator('.vf-theme-post-list--archive_list .vf-directory-grid a:visible').count()===1,'whole-archive search finds a result beyond the previous page',{lang,url:p.url(),count:await p.locator('.vf-theme-post-list--archive_list .vf-directory-grid a').count(),visible:await p.locator('.vf-theme-post-list--archive_list .vf-directory-grid a:visible').count()});
  await p.locator('.vf-theme-post-list--archive_list .vf-directory-reset').click();await p.waitForLoadState('networkidle');gate(!new URL(p.url()).searchParams.has('vf_q'),'archive reset clears URL criteria',{lang});
  await p.goto(seed.languages[lang].category+'?vf_fixture_sort=1');gate((await p.locator('.vf-archive-context-facts').innerText()).includes(lang==='en'?'Title A–Z':'标题 A–Z'),'archive sort description matches configured sort',{lang});
  await p.goto(base+(lang==='zh'?'/zh/':'/')+'blog/?vf_q=Needleword');await p.waitForLoadState('networkidle');gate(await p.locator('.vf-theme-post-list--blog_index .vf-directory-grid a:visible').count()===1,'synthetic blog searches full native content',{lang});
  await p.goto(seed.languages[lang].category+'?vf_q=zz-no-match-8349');gate((await p.locator('[data-vf-directory-empty]').innerText()).includes(lang==='en'?'No matching':'没有匹配'),'archive query-empty is distinct from no published content',{lang});
  gate(!(await p.locator('.vf-theme-system-recovery--archive').innerText()).includes(lang==='en'?'no published content':'还没有已发布内容'),'filtered archive recovery stays truthful',{lang});
  await p.goto(seed.languages[lang].category+'?vf_q=zz-no-match-8349&vf_fixture_recovery=1');gate((await p.locator('.vf-theme-system-recovery--archive h2').innerText())==='Owner Recovery Heading'&&(await p.locator('.vf-theme-system-recovery--archive .vf-theme-recovery-workspace-head p').innerText())==='Owner Recovery Description','custom authored recovery copy retained',{lang});
  });
  await scenario(lang+'-desktop',async()=>{
  for(const width of [1920,1440,1319,1024]){
   await p.setViewportSize({width,height:1000});await p.goto(search(lang));await p.waitForLoadState('networkidle');
   const geom=await p.locator('.vf-theme-search-results').evaluate(el=>({columns:getComputedStyle(el.querySelector('.vf-theme-search-results-grid')).gridTemplateColumns.split(' ').length,overflow:document.documentElement.scrollWidth>innerWidth+1,width:el.getBoundingClientRect().width,formY:el.querySelector('form').getBoundingClientRect().top,action:el.querySelector('.vf-directory-card-action').getBoundingClientRect().height}));gate(!geom.overflow&&geom.columns===1&&geom.action>=44&&geom.formY<700,'desktop search geometry and action size',{lang,width,...geom});
   if(width===1440)await p.screenshot({path:'proof/search-'+phase+'-'+lang+'.png',fullPage:true});
   await p.goto(seed.languages[lang].category);gate(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'desktop category has no overflow',{lang,width});
   const cardGeometry=await p.locator('.vf-theme-post-list--archive_list .vf-directory-card').first().evaluate(el=>({height:el.getBoundingClientRect().height,radius:getComputedStyle(el).borderRadius,shadow:getComputedStyle(el).boxShadow}));gate(cardGeometry.height<220&&cardGeometry.radius==='0px'&&cardGeometry.shadow==='none','archive uses compact rows instead of oversized cards',{lang,width,...cardGeometry});
   if(width===1440)await p.screenshot({path:'proof/archive-'+phase+'-'+lang+'.png',fullPage:true});
  }
  await p.goto(base+(lang==='zh'?'/zh/':'/')+'search/?q=m3u8&type=tool');await p.waitForLoadState('networkidle');gate(await p.locator('[data-vf-static-search-catalog] [data-vf-search-type="tool"]:visible').count()>0,'existing static local search remains functional',{lang});
  });
 }
 if(phase!=='warm'&&phase!=='rollback'){
  await scenario('nojs',async()=>{
  const nativeCtx=await browser.newContext({javaScriptEnabled:false}),n=await nativeCtx.newPage();await n.goto(search('en'));
  await n.locator('form[data-vf-theme-search-form="wordpress"] input[type="search"]').fill('Needleword');await n.locator('form[data-vf-theme-search-form="wordpress"] button').click();gate(await n.locator('.vf-theme-search-results-grid a').count()===1,'native search submit works without JavaScript');
  await n.goto(seed.languages.en.category+'?vf_q=Needleword');await n.locator('a.vf-directory-reset').click();gate(!new URL(n.url()).searchParams.has('vf_q'),'native archive clear works without JavaScript');await nativeCtx.close();gate(errors.length===0,'no uncaught browser errors',errors);
  });
 }
 const admin=await ctx.newPage();const dest=base+'/wp-admin/themes.php?page=vf-theme-modules&tab=layout';await admin.goto(base+'/wp-login.php?redirect_to='+encodeURIComponent(dest));await admin.locator('#user_login').fill('admin');await admin.locator('#user_pass').fill('Synthetic-Only-Update-54!');await admin.locator('#wp-submit').click();await admin.waitForURL('**/wp-admin/**');await admin.goto(dest);await admin.waitForLoadState('networkidle');gate(await admin.locator('[data-vf-frontend-pages]').count()===1,'actual administrator login and frontend directory initialization',{url:admin.url(),title:await admin.title()});await admin.close();
 const failed=checks.filter(c=>!c.pass);fs.writeFileSync('proof/browser-'+phase+'.json',JSON.stringify({status:failed.length?'FAIL':'PASS',phase,checks,mobile:'NOT_RUN_OWNER_DEFERRED',production:'NOT_EXECUTED'},null,2));await browser.close();assert(!failed.length,JSON.stringify(failed));
})().catch(e=>{fs.writeFileSync('proof/browser-'+phase+'-failure.json',JSON.stringify({status:'FAIL',error:e.message,checks,errors},null,2));console.error(e);process.exit(1)});
