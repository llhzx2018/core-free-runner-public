const fs=require('fs'),assert=require('assert/strict'),{chromium}=require('playwright');
(async()=>{
 const phase=process.argv.find(x=>x.startsWith('--phase='))?.split('=')[1]||'after',fixed=phase==='after';
 const urls=JSON.parse(fs.readFileSync('proof/pagination-fixtures.json')),b=await chromium.launch(),c=await b.newContext(),p=await c.newPage();globalThis.reviewPage=p;
 const errors=[],writes=[],rows=[];let checks=0;
 p.on('pageerror',e=>errors.push(e.message));c.on('request',r=>{if(r.url().startsWith('http://127.0.0.1:18880')&&!['GET','HEAD','OPTIONS'].includes(r.method()))writes.push(r.method());});
 const nav=()=>p.locator('.vf-theme-pagination,.vf-theme-post-list--archive_list .navigation.pagination').first();
 const go=async url=>{assert.equal((await p.goto(url,{waitUntil:'networkidle'})).status(),200);await p.evaluate(()=>document.fonts.ready);};
 const snapshot=()=>p.evaluate(()=>({title:document.title,h1:[...document.querySelectorAll('h1')].map(x=>x.textContent),meta:[...document.head.querySelectorAll('meta,link[rel="canonical"],link[rel="alternate"],script[type="application/ld+json"]')].map(x=>{let s=x.outerHTML;if((x.getAttribute('name')||'').startsWith('vf-'))return s.replace(/1\.35\.20[34]/g,'THEME_VERSION').replace(/vf-theme-13520[34]/g,'THEME_CACHE_VERSION');if(['/blog/','/zh/blog/','/guides/','/zh/guides/','/problems/','/zh/problems/'].includes(location.pathname)&&x.getAttribute('property')==='article:published_time'&&Math.abs(Date.now()-Date.parse(x.content))<15000)return s.replace(x.content,'REQUEST_TIME_ON_VIRTUAL_INDEX');return s;}),text:document.querySelector('main').innerText,links:[...document.querySelectorAll('main a')].map(x=>[x.textContent,x.getAttribute('href')])}));
 const metrics=()=>nav().evaluate(root=>{const read=e=>{if(!e)return null;const s=getComputedStyle(e),r=e.getBoundingClientRect();return{border:['Top','Right','Bottom','Left'].map(x=>parseFloat(s['border'+x+'Width'])),background:s.backgroundColor,color:s.color,radius:s.borderRadius,shadow:s.boxShadow,font:s.fontSize,weight:s.fontWeight,height:r.height,minWidth:s.minWidth,padding:s.padding,gap:s.gap,outline:s.outlineStyle,outlineWidth:parseFloat(s.outlineWidth)};};return{root:read(root),container:read(root.querySelector('ul.page-numbers,.nav-links')),current:read(root.querySelector('.current')),link:read(root.querySelector('a.page-numbers')),dots:read(root.querySelector('.dots')),li:[...root.querySelectorAll('li')].map(read),overflow:document.documentElement.scrollWidth>innerWidth+1};});
 const zero=x=>assert.ok(x&&x.border.every(v=>v===0),JSON.stringify(x));
 const capture=async path=>{await nav().scrollIntoViewIfNeeded();const clip=await nav().evaluate(e=>{const r=e.getBoundingClientRect();return{x:Math.max(0,r.x+scrollX-7),y:Math.max(0,r.y+scrollY-7),width:r.width+14,height:r.height+14};});await p.screenshot({path,clip,fullPage:true});};
 let common=null;
 for(const lang of ['en','zh'])for(const family of ['blog','guides','problems','glossary','category','tag','author','date','search']){
  const url=urls[lang][family];await p.setViewportSize({width:1440,height:1100});await go(url);
  assert.equal(await nav().count(),1,family+' pagination absent');assert.equal(await p.locator('meta[name="vf-theme-version"]').getAttribute('content'),fixed?'1.35.204':'1.35.203');checks+=2;
  const snap=await snapshot(),file=`proof/baseline-${lang}-${family}.json`;
  if(phase==='before')fs.writeFileSync(file,JSON.stringify(snap));else assert.deepEqual(snap,JSON.parse(fs.readFileSync(file)),lang+' '+family+' content/head/hrefs');checks++;
  for(const width of (phase==='smoke'?[1440]:[1440,1024])){
   await p.setViewportSize({width,height:1100});await go(url);const m=await metrics();assert.equal(m.overflow,false);checks++;
   fs.writeFileSync(`proof/metrics-${phase}-${lang}-${family}-${width}.json`,JSON.stringify(m));
   if(!fixed)continue;
   zero(m.root);zero(m.container);for(const item of m.li)zero(item);assert.equal(m.container.background,'rgba(0, 0, 0, 0)');assert.equal(m.container.shadow,'none');assert.ok(m.current.height>=44);assert.equal(m.link.radius,'7px');assert.equal(m.link.font,'14px');assert.equal(m.link.weight,'600');assert.deepEqual(m.link.border,[1,1,1,1]);checks+=9;
   const standard={link:m.link,current:m.current};if(common===null)common=standard;else assert.deepEqual(standard,common,'same shared computed controls '+lang+' '+family);checks++;
   if(m.dots){assert.equal(m.dots.background,'rgba(0, 0, 0, 0)');checks++;}
   await capture(`proof/pagination-${lang}-${family}-${width}.png`);
   if(width===1440){
    const link=nav().locator('a.page-numbers').last();await link.hover();zero((await metrics()).container);await capture(`proof/pagination-hover-${lang}-${family}.png`);
    await link.focus();await p.keyboard.press('Tab');await p.keyboard.press('Shift+Tab');assert.ok(await link.evaluate(e=>e.matches(':focus-visible')&&getComputedStyle(e).outlineStyle==='solid'&&parseFloat(getComputedStyle(e).outlineWidth)>=2));zero((await metrics()).container);checks+=3;await capture(`proof/pagination-focus-${lang}-${family}.png`);
   }
  }
  if(fixed){
   await p.setViewportSize({width:1440,height:1100});await go(url);
   const itemSelector=family==='glossary'?'.vf-glossary-inline-term h3':'[data-vf-directory-item] h3';const first=await p.locator(itemSelector).allTextContents();assert.ok(first.length>0);const next=nav().locator('a.next');assert.equal(await next.count(),1);const href=await next.getAttribute('href');await next.click();await p.waitForLoadState('networkidle');assert.ok(await nav().locator('[aria-current="page"]').count());assert.notDeepEqual(await p.locator(itemSelector).allTextContents(),first,'real page2 '+family);checks+=4;
   if(family==='search'){assert.equal(new URL(p.url()).searchParams.get('s'),'Pagination204');checks++;}
   const last=nav().locator('.page-numbers').filter({hasText:/^\d+$/}).last();if(await last.count()){if(await last.evaluate(e=>e.tagName==='A')){await last.click();await p.waitForLoadState('networkidle');}assert.equal(await nav().locator('a.next').count(),0,'last page '+family);checks++;}
   if(['blog','guides','glossary','search'].includes(family)){
    const nc=await b.newContext({javaScriptEnabled:false,viewport:{width:1024,height:1100}}),np=await nc.newPage();assert.equal((await np.goto(new URL(href,url).href)).status(),200);assert.ok(await np.locator(itemSelector).count()>0);await nc.close();checks++;
   }
  }
  rows.push({lang,family,status:'PASS'});
 }
 if(fixed){
  // Existing legacy data-renderer shape uses direct anchors, not WordPress UL.
  // Exercise this CSS consumer explicitly without claiming a public legacy route.
  await go(urls.en.blog);await p.locator('main').evaluate(e=>e.insertAdjacentHTML('beforeend','<nav class="vf-data-pagination" id="compat-pagination-proof"><a class="is-current" href="#one">1</a><a href="#two">2</a></nav>'));
  const legacy=await p.locator('#compat-pagination-proof').evaluate(e=>{const s=getComputedStyle(e),a=getComputedStyle(e.lastElementChild),cur=getComputedStyle(e.firstElementChild);return{border:parseFloat(s.borderWidth),background:s.backgroundColor,height:e.lastElementChild.getBoundingClientRect().height,radius:a.borderRadius,current:cur.backgroundColor};});assert.equal(legacy.border,0);assert.equal(legacy.background,'rgba(0, 0, 0, 0)');assert.equal(legacy.radius,'7px');assert.ok(legacy.height>=44);assert.equal(legacy.current,common.current.background);checks+=5;
 }
 assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);const receipt={status:'PASS',phase,checks,rows,errors,writes,contentHeadURLs:phase==='before'?'BASELINE_CAPTURED':'BYTE_IDENTICAL',sharedControl:fixed?'SAME_COMPUTED_STYLE_9_ROUTES_2_LANGUAGES_2_WIDTHS':'BASELINE_ONLY',legacy:fixed?'CSS_CONSUMER_DOM_SHAPE_VERIFIED_NOT_PUBLIC_ROUTE':'NOT_RUN',production:'UNTOUCHED',operationalAcceptance:'OWNER_REVIEW_REQUIRED_AFTER_MANUAL_UPGRADE'};fs.writeFileSync(`proof/pagination-${phase}.json`,JSON.stringify(receipt));console.log('PAGINATION_'+phase.toUpperCase()+'_PASS checks='+checks);await b.close();
})().catch(async e=>{console.error(e);try{fs.writeFileSync('proof/failure.html',await globalThis.reviewPage.content());await globalThis.reviewPage.screenshot({path:'proof/failure.png',fullPage:true});}catch(_){}process.exit(1);});
