'use strict';
const fs=require('node:fs'),assert=require('node:assert/strict'),{chromium}=require('playwright');
const phase=process.argv[2]||'candidate',base='http://127.0.0.1:18880',seed=JSON.parse(fs.readFileSync('proof/seed.json')),checks=[],errors=[];
function gate(ok,label,detail){checks.push({pass:!!ok,label,detail});}
const search=(lang,q='Searchwork Atlas',type='article',page=1)=>base+(lang==='zh'?'/zh/':'/')+'?'+new URLSearchParams({s:q,type,paged:String(page),vf_fixture_count:'1'});
(async()=>{
 const browser=await chromium.launch({headless:true}),ctx=await browser.newContext(),p=await ctx.newPage();p.on('pageerror',e=>errors.push(e.message));p.setDefaultTimeout(8000);p.setDefaultNavigationTimeout(30000);
 const scenario=async(label,fn)=>{const before=checks.length;try{await fn();}catch(e){gate(false,label+' flow',{error:e.message,url:p.url()});}if(checks.slice(before).some(c=>!c.pass)){const html=await p.content();const m=html.match(/search-archive-diag:(.+) -->/);checks.push({pass:true,label:label+' failure diagnostic',detail:{url:p.url(),diagnostic:m?JSON.parse(m[1]):null}});await p.screenshot({path:'proof/failure-'+phase+'-'+label.replace(/[^a-z0-9_-]/gi,'-')+'.png',fullPage:true});}};
 for(const lang of ['en','zh']){
  await p.goto(search(lang));await p.waitForLoadState('networkidle');
  if(phase==='warm'||phase==='rollback'){
   await p.goto(base+(lang==='zh'?'/zh/':'/')+'sitemap/');await p.goto(seed.basic[lang].basicwork);await p.goto(seed.basic[lang].basicempty);await p.goto(seed.basic[lang].basiclong);
   await p.goto(seed.languages[lang].category);await p.goto(base+(lang==='zh'?'/zh/':'/')+'blog/');for(const route of ['about/','contact/','privacy-policy/','terms/','vf-owner-missing-127/','faq/','problems/?vf_fixture_help=1','glossary/?vf_fixture_help=1'])await p.goto(base+(lang==='zh'?'/zh/':'/')+route);continue;
  }
  await scenario(lang+'-basic-sitemap',async()=>{
   const root=base+(lang==='zh'?'/zh/':'/');
   await p.goto(root+'sitemap/?vf_fixture_pages=1');const d=p.locator('[data-vf-sitemap-directory]');
   const urls=await d.locator('[data-vf-sitemap-item]').evaluateAll(a=>a.map(e=>e.href.replace(/\/$/,'')));
   gate(urls.length>15&&new Set(urls).size===urls.length,'sitemap has unique canonical presentation links across groups',{lang,count:urls.length});
   const text=await d.innerText();gate(!text.includes('HIDDEN'),'sitemap excludes draft/private objects',{lang});
   const legacy=p.locator('#vf-sitemap-problems a').filter({hasText:'Wrong Explained Problem'});gate(await legacy.count()===1&&await p.locator('#vf-sitemap-articles a').filter({hasText:'Wrong Explained Problem'}).count()===0,'legacy Problem route belongs to the Problem section without changing its record',{lang});
   const head=await p.locator('.vf-theme-post-list--html_sitemap>.container-wide>.vf-family-section-head').innerText();gate(!head.includes('not just crawlers')&&head.includes(lang==='zh'?'按分类浏览':'Browse by section'),'legacy sitemap heading and description use visitor copy in current language',{lang,head});
   const summary=await p.locator('.vf-theme-sitemap-summary>div>strong').innerText();gate(parseInt(summary)===urls.length,'sitemap count equals its final unique links',{lang,summary});
   const pathDetails=p.locator('.vf-sitemap-path-disclosure');gate(await pathDetails.count()===1&&!await pathDetails.evaluate(e=>e.open)&&await pathDetails.locator('[data-vf-static-export-path]').count()>=50,'complete multilingual crawl paths remain in HTML under native disclosure',{lang});
   await pathDetails.locator('summary').click();gate(await pathDetails.locator('[data-vf-static-export-path]').first().isVisible(),'full path list can be opened natively',{lang});await pathDetails.locator('summary').click();
   const jumps=await p.locator('.vf-theme-sitemap-jumps a').evaluateAll(a=>a.map(e=>({href:e.getAttribute('href'),exists:!!document.getElementById(e.hash.slice(1))})));gate(jumps.length>=6&&jumps.every(x=>x.exists),'each sitemap jump targets an actual rendered group',{lang,jumps});
   for(const width of [1920,1440,1319,1024]){
    await p.setViewportSize({width,height:1000});await p.goto(root+'sitemap/?vf_fixture_pages=1');
    const g=await d.evaluate(e=>{const a=e.querySelector('.vf-theme-sitemap-summary').getBoundingClientRect(),b=e.querySelector('.vf-theme-sitemap-groups').getBoundingClientRect();return {topA:a.top,topB:b.top,leftA:a.left,rightA:a.right,leftB:b.left,rightB:b.right,columns:getComputedStyle(e).gridTemplateColumns.split(' ').length,overflow:document.documentElement.scrollWidth>innerWidth+1}});
    gate(!g.overflow&&(g.columns===1||Math.abs(g.topA-g.topB)<2&&g.leftB>=g.rightA),'sitemap groups align with navigation without the empty desktop column',{lang,width,...g});
    gate(await p.locator('[data-vf-sitemap-more]:visible').count()===0,'desktop sitemap has no ineffective mobile expand buttons',{lang,width});
    if(width===1440)await p.screenshot({path:'proof/sitemap-'+phase+'-'+lang+'.png',fullPage:true});
    await p.goto(seed.basic[lang].basiclong+'?vf_fixture_pages=1');gate(await p.locator('main h1').count()===1&&await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'ordinary long page keeps one H1 and no desktop overflow',{lang,width});
    gate((await p.locator('.vf-reading-article').innerText()).includes('Owner preserved code')&&await p.locator('.vf-reading-article table').count()===1,'ordinary rich text table and code are preserved',{lang,width});
    if(width===1440)await p.screenshot({path:'proof/basic-long-'+phase+'-'+lang+'.png',fullPage:true});
   }
   await p.goto(seed.basic[lang].basicwork+'?vf_fixture_pages=1');gate((await p.locator('.vf-reading-article').innerText()).includes('Owner basic body '+lang+' retained.'),'ordinary page renders exact authored body',{lang});
   const excerpt=await p.locator('.vf-basic-page-summary').innerText();gate(excerpt==='Owner summary '+lang+' retained.'&&!(await p.locator('main').innerText()).includes('vf_summary_probe'),'page summary is passive and shortcode tokens are absent from hero and summary',{lang,excerpt});
   gate(await p.locator('.vf-basic-page-routes a').count()===3,'saved ordinary-page continue routes are rendered',{lang});
   const read=p.locator('[data-vf-basic-page-hero] .vf-reading-entry>a');gate(await read.getAttribute('href')==='#vf-reading-content'&&await p.locator('#vf-reading-content').count()===1,'ordinary reading action targets its real body',{lang});await read.click();gate(new URL(p.url()).hash==='#vf-reading-content','ordinary reading action reaches actual body',{lang});
   await p.goto(seed.basic[lang].basicwork+'?vf_fixture_pages=default');gate((await p.locator('[data-vf-content-source="theme-default"] .vf-reading-article').innerText()).includes('Owner fallback body retained.')&&await p.locator('.vf-basic-page-routes a').count()===3,'default body retains the saved continue routes',{lang});
   await p.goto(seed.basic[lang].basicempty+'?vf_fixture_pages=1');const empty=await p.locator('.vf-basic-page-empty').innerText();gate(!empty.includes('WordPress')&&!empty.includes('配置')&&empty.includes(lang==='zh'?'暂时没有':'no content'),'empty ordinary page gives an honest visitor-facing state',{lang,empty});const emptyBox=await p.locator('.vf-basic-page-empty').evaluate(e=>({width:e.getBoundingClientRect().width,padding:parseFloat(getComputedStyle(e).paddingTop)}));gate(emptyBox.width<=861&&emptyBox.padding>=24,'empty-page state has the bounded readable rail and real inner spacing',{lang,...emptyBox});const target=await p.locator('[data-vf-basic-page-hero] .vf-reading-entry>a').getAttribute('href');gate(target.endsWith('/tools/'),'ordinary empty page offers a real tool-directory action',{lang,target});const whole=await p.locator('main').innerText();gate(!whole.includes('A VF Tools page')&&!whole.includes('Choose the next route')&&!whole.includes('Continue with a public browser-side tool'),'ordinary page default support copy follows the current language',{lang});await p.screenshot({path:'proof/basic-empty-'+phase+'-'+lang+'.png',fullPage:true});
   await p.goto(seed.basic[lang].basicempty+'?vf_fixture_pages=hide');gate(await p.locator('.vf-basic-page-empty,.vf-basic-page-summary,.vf-basic-page-routes').count()===0,'saved ordinary-page visibility switches are respected',{lang});
   await p.goto(seed.basic[lang].basicwork+'?vf_fixture_pages=basic_custom');const authored=await p.locator('main').innerText();gate(authored.includes('Owner custom continuation')&&authored.includes('Owner custom related tools description'),'ordinary-page customized continuation and related copy are preserved',{lang});
   await p.goto(root+'sitemap/?vf_fixture_pages=custom');gate((await p.locator('.vf-theme-post-list--html_sitemap>.container-wide>.vf-family-section-head').innerText()).includes('Owner sitemap description'),'custom sitemap copy is retained',{lang});
   await p.goto(root+'sitemap/?vf_fixture_pages=no_paths');gate(await p.locator('.vf-sitemap-path-disclosure').count()===0&&await p.locator('[data-vf-static-discovery-seeds] [data-vf-static-export-path]').count()>=50,'existing release-path visibility switch is retained',{lang});
   const nc=await browser.newContext({javaScriptEnabled:false}),np=await nc.newPage();await np.goto(root+'sitemap/?vf_fixture_pages=1');gate(await np.locator('[data-vf-sitemap-more]:visible').count()===0&&await np.locator('[data-vf-sitemap-item]:visible').count()===await np.locator('[data-vf-sitemap-item]').count(),'without scripts all sitemap items remain visible',{lang});await np.locator('.vf-sitemap-path-disclosure>summary').click();gate(await np.locator('.vf-sitemap-path-disclosure [data-vf-static-export-path]').first().isVisible(),'complete path disclosure works without scripts',{lang});const j=np.locator('.vf-theme-sitemap-jumps a').nth(1),hash=await j.getAttribute('href');await j.click();gate(new URL(np.url()).hash===hash,'sitemap section navigation works without scripts',{lang});await nc.close();
  });
  await p.goto(search(lang));await p.waitForLoadState('networkidle');
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
  const missing=root+'vf-owner-missing-127/';const response=await p.goto(missing);gate(response.status()===404&&(response.headers()['x-robots-tag']||'').includes('noindex'),'real 404 keeps HTTP status and noindex',{lang});
  gate(await p.locator('main h1').count()===1&&await p.locator('form[data-vf-theme-search-form="wordpress"] input[name="s"]').count()===1,'404 has one title and native search',{lang});
  const popular=p.locator('.vf-theme-system-query-chips a').first();gate(!!new URL(await popular.getAttribute('href'),base).searchParams.get('s'),'404 popular query uses the same native search',{lang});
  await popular.click();gate(new URL(p.url()).searchParams.has('s')&&await p.locator('.vf-theme-search-results').count()===1,'404 popular query opens actual search results',{lang});
  });
  await scenario(lang+'-company-geometry',async()=>{
  const root=base+(lang==='zh'?'/zh/':'/');
  for(const width of [1920,1440,1319,1024])for(const [route,kind] of [['about/','about'],['contact/','contact'],['privacy-policy/','legal'],['vf-owner-missing-127/','404']]){
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
  const root=base+(lang==='zh'?'/zh/':'/'),missing=root+'vf-owner-missing-127/';
  const nojs=await browser.newContext({javaScriptEnabled:false}),np=await nojs.newPage();await np.goto(missing);await np.locator('input[name="s"]').fill('Snippetwork');await np.locator('form[data-vf-theme-search-form="wordpress"] button').click();gate(await np.locator('.vf-theme-search-results-grid a').count()===2,'404 native search works without JavaScript',{lang});await nojs.close();
  });
  await scenario(lang+'-faq-help',async()=>{
   const root=base+(lang==='zh'?'/zh/':'/');await p.goto(root+'faq/');const faq=p.locator('[data-vf-faq-page]');
   gate(await p.locator('.vf-faq-category-nav').count()===1&&await faq.locator('[data-vf-faq-item]').count()===4,'one FAQ category navigation and all authored current-language questions',{lang});
   gate(!(await faq.locator('.vf-support-content-head p').innerText()).includes('rich results')&&!(await faq.locator('.vf-support-content-head p').innerText()).includes('富结果'),'FAQ default explanation is visitor-facing',{lang});
   const input=faq.locator('[data-vf-faq-query]');gate(await input.isEnabled(),'FAQ keyword search enabled by real enhancement',{lang});await input.fill('uniqueANSWER');gate(await faq.locator('[data-vf-faq-item]:visible').count()===1&&(await faq.locator('[data-vf-faq-count]').innerText())==='1','FAQ search covers authored answer text case-insensitively',{lang});
   await input.fill('zz-no-help-answer-125');gate(await faq.locator('[data-vf-faq-empty]').isVisible()&&(await faq.locator('[data-vf-faq-count]').innerText())==='0','FAQ no-match has truthful count and recovery',{lang});await faq.locator('[data-vf-faq-clear]').click();gate(await input.inputValue()===''&&await faq.locator('[data-vf-faq-item]:visible').count()===4&&await input.evaluate(e=>document.activeElement===e),'FAQ clear restores all answers and keyboard focus',{lang});
   await input.fill('Uniqueanswer');await input.press('Escape');gate(await input.inputValue()===''&&await faq.locator('[data-vf-faq-item]:visible').count()===4,'FAQ Escape reset retained',{lang});
   const items=faq.locator('[data-vf-faq-item]');await items.nth(0).locator('summary').click();await items.nth(1).locator('summary').click();await p.waitForTimeout(100);gate(await faq.locator('details[open]').count()===1,'FAQ single-open setting preserved',{lang});
   const nav=faq.locator('.vf-faq-category-nav a').last();const hash=await nav.getAttribute('href');await nav.click();gate(new URL(p.url()).hash===hash&&await p.evaluate(id=>!!document.getElementById(id),decodeURIComponent(hash.slice(1))),'FAQ category link targets its actual answer group',{lang});
   await p.goto(root+'faq/?vf_fixture_help=faq_multi');await p.locator('[data-vf-faq-item] summary').nth(0).click();await p.locator('[data-vf-faq-item] summary').nth(1).click();await p.waitForTimeout(100);gate(await p.locator('[data-vf-faq-page] details[open]').count()===2,'FAQ saved multiple-open mode remains effective',{lang});
   await p.goto(root+'faq/?vf_fixture_help=faq_hide');gate(await p.locator('[data-vf-faq-query],.vf-faq-category-nav,[data-vf-faq-count]').count()===0,'FAQ saved search/navigation/count visibility retained',{lang});
   await p.goto(root+'faq/?vf_fixture_help=faq_custom');gate((await p.locator('[data-vf-faq-page] .vf-support-content-head').innerText()).includes('Owner custom help description'),'FAQ authored title and description retained',{lang});
  });
  await scenario(lang+'-help-finish',async()=>{
   const root=base+(lang==='zh'?'/zh/':'/');
   await p.goto(root+'faq/?vf_fixture_help=legacy');const fq=await p.locator('[data-vf-faq-page] .vf-support-content-head p').innerText();gate(!fq.includes('页脚模块')&&fq.includes(lang==='zh'?'输入关键词':'Find an answer'),'live legacy FAQ instruction is replaced in the page language',{lang,fq});
   for(const route of ['problems','glossary']){
    await p.goto(root+route+'/?vf_fixture_help=legacy');const shell=p.locator('[data-vf-directory-filter]');
    gate(await shell.locator('[data-vf-content-result-count]').count()===1&&await shell.locator('[data-vf-directory-count]').count()===0,'help results have one page-scoped count',{lang,route});
    gate(!await shell.locator('.vf-directory-toolbar-actions').isVisible()&&!await shell.locator('[data-vf-directory-more]').isVisible(),'inactive help status and desktop mobile-only button are actually hidden',{lang,route});
    const description=await p.locator('.vf-theme-post-list .vf-family-section-head p').innerText();gate(!description.includes('真正的问题修复中心'),'live legacy problem instruction is visitor-facing',{lang,route,description});
    if(route==='glossary'){const d=p.locator('.vf-glossary-letter-disclosure');gate(!await d.evaluate(e=>e.open),'alphabet is initially compact',{lang});await d.locator('summary').click();gate(await d.locator('a[data-vf-directory-filter-button="b"]').isVisible(),'native disclosure exposes the complete alphabet',{lang});}
    await p.goto(root+route+'/?vf_fixture_help=help_custom');gate((await p.locator('.vf-theme-post-list .vf-family-section-head').innerText()).includes('Owner help catalogue description'),'custom help catalogue copy is retained',{lang,route});
   }
   await p.goto(root+'glossary/?vf_fixture_help=1&vf_letter=a');gate(await p.locator('.vf-glossary-letter-disclosure').evaluate(e=>e.open),'active letter navigation opens automatically',{lang});
   await p.locator('input[name="vf_q"]').fill('zz-no-help-result-126');await p.locator('form[data-vf-directory-server-search] button').click();gate(await p.locator('.vf-directory-toolbar-actions').isVisible()&&await p.locator('.vf-directory-reset').isVisible(),'active empty result retains native filter recovery',{lang});await p.locator('.vf-directory-reset').click();gate(!await p.locator('.vf-directory-toolbar-actions').isVisible()&&await p.locator('[data-vf-directory-item]:visible').count()===3,'reset restores results and removes redundant status',{lang});
   await p.goto(root+'glossary/?vf_fixture_help=semantic');const list=p.locator('.vf-theme-post-list--glossary_index');const content=await list.innerText();gate(await list.locator('[data-vf-directory-item]').count()===1&&content.includes('Termwork Glossary '+lang.toUpperCase())&&!content.includes('Wrong Explained Problem'),'semantic glossary keeps real definitions and excludes another owners Problem route',{lang,content});
   const nc=await browser.newContext({javaScriptEnabled:false}),np=await nc.newPage();await np.goto(root+'problems/?vf_fixture_help=legacy');gate(!await np.locator('[data-vf-directory-more]').isVisible()&&!await np.locator('.vf-directory-toolbar-actions').isVisible()&&await np.locator('[data-vf-directory-item]:visible').count()===3,'without scripts all desktop help rows remain available without inactive controls',{lang});await np.goto(root+'glossary/?vf_fixture_help=1');await np.locator('.vf-glossary-letter-disclosure>summary').click();await np.locator('.vf-glossary-letter-index a[data-vf-directory-filter-button="b"]').click();gate(new URL(np.url()).searchParams.get('vf_letter')==='b'&&await np.locator('.vf-glossary-letter-disclosure').evaluate(e=>e.open),'native alphabet disclosure and navigation work without scripts',{lang});await nc.close();
  });
  await scenario(lang+'-help-directory',async()=>{
   const root=base+(lang==='zh'?'/zh/':'/');
   for(const [route,kind] of [['problems','problem'],['glossary','glossary']]){
    await p.goto(root+route+'/?vf_fixture_help=1');const list=p.locator('.vf-theme-post-list--'+kind+'_index'),cards=list.locator('[data-vf-directory-item]');gate(await cards.count()===3&&!(await list.innerText()).includes('HIDDEN')&&(await cards.first().innerText()).includes(lang.toUpperCase()),'help catalogue paginates published current-language objects',{lang,kind});
    gate(await list.locator('form button[type="submit"]').isVisible(),'help search has a visible submit action',{lang,kind});
    fs.writeFileSync('proof/help-pagination-'+phase+'-'+lang+'-'+kind+'.json',JSON.stringify(await p.evaluate(()=>Array.from(document.querySelectorAll('a')).filter(a=>/^(Next|下一页)/.test(a.textContent.trim())).map(a=>({text:a.textContent,href:a.href,parents:[a.parentElement,a.parentElement.parentElement,a.parentElement.parentElement.parentElement].map(e=>({tag:e.tagName,classes:e.className}))}))),null,2));
    const seen=[];for(let walk=0;walk<5;walk++){seen.push(...await p.locator('.vf-theme-post-list--'+kind+'_index [data-vf-directory-item]').evaluateAll(a=>a.map(x=>x.href)));const more=p.locator('nav.vf-theme-pagination--internal a.next');if(!await more.count())break;const destination=await more.getAttribute('href');await more.click();await p.waitForLoadState('networkidle');gate(p.url()===destination,'help next-page control reaches its real native target',{lang,kind,destination,actual:p.url()});}
    gate(seen.length===7&&new Set(seen).size===7,'every help catalogue object is reachable without repeated pages',{lang,kind,seen:seen.length,links:await p.locator('nav.vf-theme-pagination--internal a').evaluateAll(a=>a.map(x=>({href:x.href,classes:x.className})))});
    await p.goto(root+route+'/?vf_fixture_help=1');const input=p.locator('.vf-theme-post-list--'+kind+'_index input[name="vf_q"]');await input.fill(kind==='problem'?'Beyondneedle':'Aliasneedle');await p.locator('.vf-theme-post-list--'+kind+'_index form button[type="submit"]').click();gate(await p.locator('.vf-theme-post-list--'+kind+'_index [data-vf-directory-item]:visible').count()===1,'help search reaches objects beyond the original first page including term aliases',{lang,kind});
    const target=await p.locator('.vf-theme-post-list--'+kind+'_index [data-vf-directory-item]').first().getAttribute('href');await p.locator('.vf-theme-post-list--'+kind+'_index [data-vf-directory-item]').first().click();gate(p.url()===target&&(await p.locator('.vf-reading-article').innerText()).includes('Owner help body '+lang+' retained.'),'help result opens the actual authored current-language detail',{lang,kind});
    await p.goto(root+route+'/?vf_fixture_help=1&vf_q=zz-no-help-result-125');gate(await p.locator('.vf-theme-post-list--'+kind+'_index [data-vf-directory-item]:visible').count()===0,'help query-empty never exposes unrelated fallback cards',{lang,kind});await p.locator('.vf-theme-post-list--'+kind+'_index .vf-directory-reset').click();gate(!new URL(p.url()).searchParams.has('vf_q')&&await p.locator('.vf-theme-post-list--'+kind+'_index [data-vf-directory-item]:visible').count()===3,'help reset restores the native first page',{lang,kind});
   }
   await p.goto(root+'problems/?vf_fixture_help=1');await p.locator('input[name="vf_q"]').fill('Beyondneedle');await p.locator('.vf-directory-filter-group a[data-vf-directory-filter-button="access"]').click();gate(new URL(p.url()).searchParams.get('vf_q')==='Beyondneedle'&&new URL(p.url()).searchParams.get('vf_filter')==='access'&&await p.locator('.vf-directory-card:visible').count()===1,'native problem filter preserves the unsent keyword with JavaScript',{lang});
   await p.goto(root+'glossary/?vf_fixture_help=1&vf_filter=access');await p.locator('.vf-glossary-letter-disclosure>summary').click();await p.locator('.vf-glossary-letter-index a[data-vf-directory-filter-button="a"]').click();gate(new URL(p.url()).searchParams.get('vf_filter')==='access'&&new URL(p.url()).searchParams.get('vf_letter')==='a'&&await p.locator('[data-vf-directory-item]:visible').count()===1,'glossary category and initial-letter filters compose across the full directory',{lang});
  });
  await scenario(lang+'-help-nojs',async()=>{
   const root=base+(lang==='zh'?'/zh/':'/'),nc=await browser.newContext({javaScriptEnabled:false}),np=await nc.newPage();
   await np.goto(root+'faq/');gate(await np.locator('[data-vf-faq-query]').isDisabled()&&await np.locator('[data-vf-faq-item]').count()===4,'without JavaScript FAQ answers stay available and inactive keyword field is disabled',{lang});await np.locator('[data-vf-faq-item] summary').last().click();gate(await np.locator('[data-vf-faq-item]').last().evaluate(e=>e.open),'native FAQ answer expansion works without JavaScript',{lang});
   await np.goto(root+'problems/?vf_fixture_help=1');await np.locator('.vf-directory-filter-group a[data-vf-directory-filter-button="browser"]').click();gate(new URL(np.url()).searchParams.get('vf_filter')==='browser'&&await np.locator('[data-vf-directory-item]').count()===3,'problem category links work without JavaScript',{lang});
   await np.goto(root+'glossary/?vf_fixture_help=1');await np.locator('.vf-glossary-category-filter a[data-vf-directory-filter-button="access"]').click();await np.locator('.vf-glossary-letter-disclosure>summary').click();await np.locator('.vf-glossary-letter-index a[data-vf-directory-filter-button="a"]').click();gate(await np.locator('[data-vf-directory-item]').count()===1,'glossary combined native filters work without JavaScript',{lang});await np.locator('input[name="vf_q"]').fill('Aliasneedle');await np.locator('form[data-vf-directory-server-search] button').click();gate(new URL(np.url()).searchParams.get('vf_filter')==='access'&&new URL(np.url()).searchParams.get('vf_letter')==='a'&&await np.locator('[data-vf-directory-item]').count()===1,'native glossary submit retains both filter dimensions without JavaScript',{lang});await nc.close();
  });
  await scenario(lang+'-help-geometry',async()=>{
   const root=base+(lang==='zh'?'/zh/':'/');
   for(const width of [1920,1440,1319,1024])for(const [route,kind] of [['faq/','faq'],['problems/?vf_fixture_help=1','problem_index'],['glossary/?vf_fixture_help=1','glossary_index']]){
    await p.setViewportSize({width,height:1000});await p.goto(root+route);gate(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'help desktop has no horizontal overflow',{lang,width,kind});
    const el=p.locator(kind==='faq'?'[data-vf-faq-page]':'.vf-theme-post-list--'+kind),g=await el.evaluate(e=>{const c=e.querySelector(':scope>.container-wide');return{width:c.getBoundingClientRect().width,heading:parseFloat(getComputedStyle(e.querySelector('h2')).fontSize)}});gate(g.width<=1101&&g.heading<=28,'help catalogue uses a bounded rail and subordinate heading',{lang,width,kind,...g});
    if(kind!=='faq'){const row=await el.locator('[data-vf-directory-item]').first().evaluate(e=>({radius:getComputedStyle(e).borderRadius,shadow:getComputedStyle(e).boxShadow,height:e.getBoundingClientRect().height}));gate(row.radius==='0px'&&row.shadow==='none'&&row.height<180,'help catalogue uses compact result rows',{lang,width,kind,...row});const iw=await el.locator('input[type="search"]').evaluate(e=>e.getBoundingClientRect().width);gate(iw>300,'help keyword field has usable desktop width',{lang,width,kind,inputWidth:iw});gate((await el.locator('.vf-content-list-summary').innerText()).includes(lang==='zh'?'本页':'On this page')&&!(lang==='zh'&&(await el.locator('.vf-family-section-head').innerText()).includes('Find ')),'help counts are page-scoped and default copy follows language',{lang,width,kind});}
    if(width===1440)await p.screenshot({path:'proof/help-'+phase+'-'+lang+'-'+kind+'.png',fullPage:true});
   }
   for(const kind of ['problem','glossary'])for(const width of [1440,1024]){
    await p.setViewportSize({width,height:1000});await p.goto(seed.help[lang][kind].urls[0]);gate(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)&&await p.locator('main h1').count()===1,'help detail has one title and no desktop overflow',{lang,width,kind});const size=await p.locator('main h1').evaluate(e=>parseFloat(getComputedStyle(e).fontSize));gate(size<=42&&(await p.locator('.vf-reading-article').innerText()).includes('Owner help body '+lang),'help detail keeps the authored reading body and measured title hierarchy',{lang,width,kind,size});if(width===1440)await p.screenshot({path:'proof/help-'+phase+'-'+lang+'-'+kind+'-detail.png',fullPage:true});
   }
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
