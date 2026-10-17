'use strict';
const fs=require('fs'),assert=require('node:assert/strict'),{chromium}=require('playwright');
const cases=JSON.parse(fs.readFileSync('proof/cases.json')).cases,seed=JSON.parse(fs.readFileSync('proof/seed.json')),checks=[],errors=[];
function gate(value,name,detail){checks.push({name,pass:!!value,detail});/* Collect independent failures before the final gate. */}
(async()=>{const browser=await chromium.launch({headless:true}),context=await browser.newContext(),p=await context.newPage();p.setDefaultTimeout(8000);p.on('pageerror',e=>errors.push(e.message));
 for(const lang of ['en','zh'])for(const width of [1920,1440,1319,1024]){
  await p.setViewportSize({width,height:1000});
  for(const [family,url]of Object.entries(cases[lang])){
   const response=await p.goto(url);await p.waitForLoadState('networkidle');
   gate(response.status()===(family==='not_found'?404:200),'real route status',{lang,width,family,status:response.status()});
   gate(await p.locator('[data-vf-theme-module-stack="'+family+'"][data-vf-frontend-design="reference-v1"]').count()===1,'real context uses approved design',{lang,width,family,actual:await p.locator('[data-vf-theme-module-stack]').getAttribute('data-vf-theme-module-stack')});
   gate(await p.locator('main h1').count()===1,'one page title',{lang,width,family});
   gate(await p.locator('header[data-vf-frontend-design]').count()===1&&await p.locator('footer[data-vf-frontend-design]').count()===1,'one shared header/footer',{lang,width,family});
   const geom=await p.evaluate(()=>({overflow:document.documentElement.scrollWidth>innerWidth+1,header:document.querySelector('.vf-header-inner').getBoundingClientRect().x,footer:document.querySelector('.vf-production-footer-wrap').getBoundingClientRect().x,css:getComputedStyle(document.querySelector('.vf-production-footer')).backgroundColor}));
   if(width===1920&&family==='home')fs.writeFileSync('proof/geometry-'+lang+'.json',JSON.stringify(await p.evaluate(()=>({elements:['.vf-header-inner','.vf-production-footer','.vf-production-footer-wrap'].map(sel=>{const e=document.querySelector(sel),c=getComputedStyle(e);return{sel,html:e.outerHTML.slice(0,350),rect:e.getBoundingClientRect().toJSON(),width:c.width,maxWidth:c.maxWidth,padding:c.padding,wide:c.getPropertyValue('--vf-container-wide'),rules:[...document.styleSheets].flatMap(sheet=>{try{return [...sheet.cssRules]}catch{return[]}}).flatMap(function walk(rule){if(rule.selectorText){try{return e.matches(rule.selectorText)?[rule.cssText]:[]}catch{return[]}}return rule.cssRules?[...rule.cssRules].flatMap(walk):[]})}})})),null,2));
   gate(!geom.overflow&&Math.abs(geom.header-geom.footer)<=1,'desktop rails align without overflow',{lang,width,family,...geom});
   gate(geom.css!=='rgb(11, 18, 32)'&&await p.locator('.vf-footer-component-version').count()===0,'light footer has no technical version label',{lang,width,family});
   const cta=await p.locator('main .vf-data-cta-box').evaluateAll(es=>es.map(e=>({shadow:getComputedStyle(e).boxShadow,before:getComputedStyle(e,'::before').display})));gate(cta.every(c=>c.shadow==='none'&&c.before==='none'),'shared continuation uses the approved simple treatment',{lang,width,family,cta});
   if(width===1440)await p.screenshot({path:'proof/'+family+'-'+lang+'.png',fullPage:true});
  }
 }
 for(const lang of ['en','zh']){
  await p.setViewportSize({width:1440,height:1000});await p.goto(cases[lang].home);
  gate(await p.locator('.vf-home-quick-start a').count()>0,'home quick start consumes available tools',{lang});
  const quick=await p.locator('.vf-home-quick-start a').first().getAttribute('href');gate(new URL(quick).origin===new URL(p.url()).origin,'quick start points to real same-site tool',{lang});
  await p.goto(cases[lang].tool_hub);const search=p.locator('[data-vf-directory-query],.vf-directory-search input[type="search"]').first();
  gate(await search.count()===1,'tool directory search exists',{lang});{await search.fill('zz-no-such-tool-147');await search.press('Enter');await p.waitForLoadState('networkidle');gate(await p.locator('.vf-directory-tool-card:visible').count()===0,'tool search empty stays empty',{lang});}
  await p.goto(cases[lang].faq_page);const faq=p.locator('[data-vf-faq-page]');const q=faq.locator('[data-vf-faq-query]');await q.fill('Uniqueanswer');gate(await faq.locator('[data-vf-faq-item]:visible').count()===1,'FAQ filters authored answers',{lang});await faq.locator('[data-vf-faq-clear]').click();gate(await faq.locator('[data-vf-faq-item]:visible').count()===4,'FAQ clear recovers',{lang});const summary=faq.locator('[data-vf-faq-item] summary').first();if(await summary.locator('..').getAttribute('open')!==null)await summary.click();await summary.focus();await p.keyboard.press('Enter');gate(await summary.locator('..').getAttribute('open')!==null,'FAQ keyboard opens answer',{lang});
  await p.goto(cases[lang].search+'&vf_fixture_count=1');const form=p.locator('form[data-vf-theme-search-form="wordpress"]').first();gate(await form.count()===1,'native WordPress search form exists',{lang});{await form.locator('input[type="search"]').fill('zz-no-article-match');await form.locator('[type="submit"]').click();await p.waitForLoadState('networkidle');gate(await p.locator('.vf-theme-search-results-grid .vf-directory-card').count()===0,'search no result does not fabricate cards',{lang});}
  await p.goto(cases[lang].archive_list+'?vf_fixture_count=1');const next=p.locator('.vf-theme-post-list--archive_list .pagination .next');gate(await next.count()===1,'archive keeps real next page',{lang});await next.click();await p.waitForLoadState('networkidle');gate(await p.locator('.vf-theme-post-list--archive_list .pagination .current').count()===1,'archive next page resolves',{lang});
  await p.goto(cases[lang].guide_index+'?vf_fixture_pages=guide');const g=p.locator('.vf-theme-post-list--guide_index .vf-theme-pagination--internal .next');gate(await g.count()===1,'guide has real next page',{lang});{await g.click();await p.waitForLoadState('networkidle');gate(await p.locator('.vf-theme-post-list--guide_index .vf-directory-grid a').count()>0,'guide pagination works',{lang});}
  await p.goto(seed.basic[lang].basiclong);gate(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'long authored content does not overflow',{lang});gate((await p.locator('main').innerText()).includes('Owner preserved code'),'authored code preserved',{lang});
  await p.goto(cases[lang].tool);gate(await p.locator('main input, main textarea').count()>0,'real provider input still mounted',{lang});
 }
 for(const lang of ['en','zh']){
  await p.setViewportSize({width:1440,height:1000});await p.goto(cases[lang].home);
  const partner=p.locator('.vf-footer-partner-link[href="https://www.youtube.com/"]');
  gate(await partner.count()===1,'external partner menu seeded',{lang});
  if(await partner.count()){
    const external=await partner.first().evaluate(e=>({active:e.classList.contains('is-active'),current:e.getAttribute('aria-current')}));
    gate(!external.active&&external.current!=='page','external footer link cannot be current page',{lang,external});
  }
  const grid=p.locator('.vf-home-tools-grid'),cards=grid.locator('.vf-home-tool-card');
  gate(await grid.count()===1&&await cards.count()>0,'home tool grid remains populated',{lang,count:await cards.count()});
  if(await grid.count()){
    const geom=await grid.evaluate(e=>({columns:getComputedStyle(e).gridTemplateColumns.split(' ').length,scroll:document.documentElement.scrollWidth,viewport:innerWidth}));
    gate(geom.scroll<=geom.viewport+1&&(await cards.count()!==6||geom.columns===3),'desktop home card grid stays compact',{lang,geom,count:await cards.count()});
  }
  const disc=p.locator('.vf-home-task-disclosure');
  gate(await disc.count()===1,'home task disclosure exists',{lang,count:await disc.count()});
  if(await disc.count()){
    const summary=disc.locator('summary');gate(await disc.getAttribute('open')===null,'home task disclosure closed by default',{lang});
    await summary.focus();await p.keyboard.press('Enter');
    gate(await disc.getAttribute('open')!==null,'home task disclosure keyboard opens',{lang});
    await p.keyboard.press('Enter');gate(await disc.getAttribute('open')===null,'home task disclosure keyboard closes',{lang});
  }
  await p.goto(cases[lang].tool_hub);
  const external=p.locator('.vf-footer-partner-link[href="https://www.youtube.com/"]');
  gate(await external.count()===1&&await external.getAttribute('aria-current')!=='page','external partner inactive on inner page',{lang});
 }

 // Bounded 1024+ three-family desktop rhythm proof on exact WordPress output.
 for(const lang of ['en','zh']) for(const width of [1440,1024]){
   await p.setViewportSize({width,height:1000});
   await p.goto(cases[lang].tool_hub);
   const directory=await p.locator('.vf-directory-tool-card').first().evaluate(el=>({pad:getComputedStyle(el).paddingTop,gap:getComputedStyle(el).gap}));
   gate(directory.pad==='18px'&&directory.gap==='11px','tool hub desktop cards consume dense family owner',{lang,width,directory});
   gate(await p.locator('.vf-directory-tool-card').count()===11,'tool directory retains all 11 fixture tools',{lang,width});
   await p.goto(cases[lang].tool);
   const steps=await p.locator('.vf-tool-steps-list li').first().evaluate(el=>({min:getComputedStyle(el).minHeight,pad:getComputedStyle(el).paddingTop}));
   gate(steps.min==='150px'&&steps.pad==='18px','tool detail only tightens secondary guidance',{lang,width,steps});
   gate(await p.locator('[data-vf-tool-runtime-stage="1"]').count()===1,'Provider work surface retained',{lang,width});
   await p.goto(cases[lang].guide_index);
   const guide=await p.locator('.vf-theme-post-list--guide_index .vf-directory-card').first().evaluate(el=>({pad:getComputedStyle(el).paddingTop}));
   gate(guide.pad==='17px','guide index desktop row spacing consumes family owner',{lang,width,guide});
   gate(await p.locator('.vf-theme-post-list--guide_index .vf-directory-card').count()>=9,'guide index keeps nine or more existing results',{lang,width});
 }

 // R03 visual system: exact-source home/header/footer computed desktop styles.
 for(const lang of ['en','zh']) for(const width of [1440,1319,1024]){
   await p.setViewportSize({width,height:1000});
   await p.goto(cases[lang].home);
   const o=await p.evaluate(()=>{
     const sty=selector=>{const el=document.querySelector(selector);if(!el)return null;const s=getComputedStyle(el);return {font:s.fontSize,min:s.minHeight,padTop:s.paddingTop,padBottom:s.paddingBottom,outline:s.outlineWidth,visible:el.getBoundingClientRect().width>0};};
     return {
       overflow:document.documentElement.scrollWidth>innerWidth+1,
       heading:sty('.vf-home-hero h1'),
       hero:sty('.vf-home-hero'),
       nav:sty('.vf-primary-nav .vf-nav-link'),
       link:sty('.vf-production-footer-col .vf-footer-link'),
       legal:sty('.vf-footer-legal a'),
       bottom:sty('.vf-footer-bottom')
     };
   });
   gate(!o.overflow,'R03 home shell stays within desktop viewport',{lang,width,o});
   gate(!!o.link&&o.link.font==='14px'&&!!o.legal&&o.legal.font==='14px',
     'R03 readable footer links and legal copy',{lang,width,o});
   if(width>=1180){
     gate(!!o.nav&&o.nav.visible&&o.nav.font==='15px',
       'R03 desktop nav has consistent 15px font',{lang,width,o});
     gate(!!o.heading&&parseFloat(o.heading.font)<=44&&!!o.hero&&parseFloat(o.hero.padTop)<=44,
       'R03 home hero remains compact without hiding heading',{lang,width,o});
   }
   if(width===1440){
     const a=p.locator('.vf-primary-nav .vf-nav-link:visible').first();
     await a.focus();
     const navFocus=await a.evaluate(e=>getComputedStyle(e).outlineWidth);
     gate(parseFloat(navFocus)>=2,'R03 header keyboard focus visibly outlined',{lang});
     const legal=p.locator('.vf-footer-legal a:visible').first();
     await legal.focus();
     const legalFocus=await legal.evaluate(e=>getComputedStyle(e).outlineWidth);
     gate(parseFloat(legalFocus)>=2,'R03 footer keyboard focus visibly outlined',{lang});
   }
 }

 // R04: blog list + article detail visual rhythm and technical SEO projections.
 const r04Heads=[];
 for(const lang of ['en','zh'])for(const width of [1440,1024]){
   await p.setViewportSize({width,height:1000});
   for(const family of ['blog_index','article_detail']){
     const url=cases[lang][family];
     const response=await p.goto(url);
     const obs=await p.evaluate(()=>{
       const style=s=>{const e=document.querySelector(s);if(!e)return null;const c=getComputedStyle(e);return{font:c.fontSize,line:c.lineHeight,padding:c.paddingTop,outline:c.outlineWidth,maxWidth:c.maxWidth};};
       const canon=[...document.querySelectorAll('head link[rel="canonical"]')].map(e=>e.href);
       const alt=[...document.querySelectorAll('head link[rel="alternate"][hreflang]')].map(e=>({lang:e.hreflang,url:e.href}));
       return{
         overflow:document.documentElement.scrollWidth>innerWidth+1,
         title:document.title.trim(),
         h1:[...document.querySelectorAll('main h1')].map(x=>x.textContent.trim()),
         canonical:canon,
         hreflang:alt,
         robots:[...document.querySelectorAll('head meta[name="robots"]')].map(e=>e.content),
         description:[...document.querySelectorAll('head meta[name="description"]')].map(e=>e.content),
         schemas:[...document.querySelectorAll('head script[type="application/ld+json"]')].map(e=>{try{JSON.parse(e.textContent);return'VALID_JSON'}catch{return'INVALID_JSON'}}),
         listCard:style('.vf-theme-post-list--blog_index .vf-directory-card'),
         listTitle:style('.vf-theme-post-list--blog_index .vf-post-card-body h3'),
         listMeta:style('.vf-theme-post-list--blog_index .vf-post-card-meta'),
         articleBody:style('.vf-reading-article'),
         articleMeta:style('.vf-article-hero-meta strong')
       };
     });
     gate(response.status()===200&&!obs.overflow,'R04 blog/article real desktop status and no overflow',{lang,width,family,status:response.status(),overflow:obs.overflow});
     gate(obs.title.length>6&&obs.h1.length===1&&obs.h1[0].length>3,'R04 article/list title H1 consistency',{lang,width,family,title:obs.title,h1:obs.h1});
     gate(obs.canonical.length<=1&&obs.canonical.every(h=>new URL(h).origin===new URL(p.url()).origin),
       'R04 canonical output nonduplicate and same-origin',{lang,width,family,canonical:obs.canonical});
     gate(obs.description.length<=1&&obs.robots.length<=1&&obs.schemas.every(x=>x==='VALID_JSON'),
       'R04 SEO meta single writer and structured data JSON valid',{lang,width,family,metaCount:obs.description.length,robotsCount:obs.robots.length,schemas:obs.schemas});
     gate(new Set(obs.hreflang.map(x=>x.lang)).size===obs.hreflang.length&&obs.hreflang.every(x=>new URL(x.url).origin===new URL(p.url()).origin),
       'R04 hreflang projection not duplicated or external',{lang,width,family,hreflang:obs.hreflang});
     if(family==='blog_index'){
       gate(!!obs.listCard&&obs.listCard.padding==='19px'&&!!obs.listTitle&&obs.listTitle.font==='21px',
         'R04 blog list uses readable row and headline',{lang,width,styles:obs});
       gate(await p.locator('.vf-theme-post-list--blog_index .vf-directory-card').count()>=9,
         'R04 blog keeps fixture entries intact',{lang,width});
       const action=p.locator('.vf-theme-post-list--blog_index .vf-directory-card-action:visible').first();
       await action.focus();
       const out=await action.evaluate(e=>getComputedStyle(e).outlineWidth);
       gate(parseFloat(out)>=2,'R04 blog read action keyboard focus clear',{lang,width,outline:out});
     }else{
       gate(!!obs.articleBody&&obs.articleBody.font==='18px'&&!!obs.articleMeta&&obs.articleMeta.font==='14px',
         'R04 article reading measure and metadata readable',{lang,width,styles:obs});
       gate(await p.locator('.vf-reading-article').count()===1,
         'R04 article uses original authored body',{lang,width});
       const prev=p.locator('.vf-reading-post-navigation a:visible').first();
       if(await prev.count()){
         await prev.focus();const out=await prev.evaluate(e=>getComputedStyle(e).outlineWidth);
         gate(parseFloat(out)>=2,'R04 article previous/next keyboard focus visible',{lang,width,outline:out});
       }
     }
     r04Heads.push({lang,width,family,url:p.url(),title:obs.title,h1:obs.h1,canonical:obs.canonical,hreflang:obs.hreflang,robots:obs.robots,description:obs.description,schemas:obs.schemas});
   }
   await p.goto(cases[lang].blog_index+'?vf_fixture_pages=blog');
   const next=p.locator('.vf-theme-post-list--blog_index .vf-theme-pagination--internal .next');
   gate(await next.count()===1,'R04 real blog pagination next exists',{lang,width});
   if(await next.count()){
     await next.click();await p.waitForLoadState('networkidle');
     gate(await p.locator('.vf-theme-post-list--blog_index .vf-directory-card').count()>0,'R04 blog page 2 keeps articles',{lang,width});
   }
 }
 fs.writeFileSync('proof/r04-head-observations.json',JSON.stringify({status:'OBSERVED_ONLY_NOT_SEO_INDEXING_CERTIFICATION',production:'NOT_EXECUTED',observations:r04Heads},null,2));
 const nativeContext=await browser.newContext({javaScriptEnabled:false,viewport:{width:1440,height:1000}}),n=await nativeContext.newPage();for(const lang of ['en','zh']){await n.goto(cases[lang].faq_page);await n.locator('[data-vf-faq-item] summary').first().click();gate(await n.locator('[data-vf-faq-item][open]').count()>0,'FAQ works without JavaScript',{lang});await n.goto(cases[lang].archive_list+'?vf_fixture_count=1');await n.locator('.pagination .next').click();gate(await n.locator('.pagination .current').count()===1,'native pagination works',{lang});}await nativeContext.close();
 const admin=await context.newPage();await admin.goto('http://127.0.0.1:18880/wp-login.php');await admin.locator('#user_login').fill('admin');await admin.locator('#user_pass').fill('Synthetic-Only-Update-54!');await admin.locator('input[name="redirect_to"]').evaluate(e=>e.value='http://127.0.0.1:18880/wp-admin/themes.php?page=vf-theme-modules&tab=layout&view=pages');await admin.locator('#wp-submit').click();await admin.waitForURL('**/wp-admin/**');await admin.goto('http://127.0.0.1:18880/wp-admin/themes.php?page=vf-theme-modules&tab=layout&view=pages');gate(await admin.locator('[data-vf-page-context]').count()===20,'same admin directory keeps all types');gate((await admin.locator('.vf-frontend-pages__review-overview').innerText()).includes('待复验'),'backend records source phase truthfully');gate((await admin.locator('#vf-review-home .vf-frontend-pages__progress-record > p').first().innerText()).includes('待复验'),'unreviewed source starts at verify, not accepted');await admin.screenshot({path:'proof/admin-progress.png'});
 gate(errors.length===0,'no uncaught runtime errors',errors);assert(checks.every(c=>c.pass),'Independent gates failed: '+JSON.stringify(checks.filter(c=>!c.pass))); fs.writeFileSync('proof/public-browser.json',JSON.stringify({status:'PASS',checks,mobile:'NOT_RUN_OWNER_DEFERRED',production:'NOT_EXECUTED',owner_real_use:'PENDING'},null,2));await browser.close();
})().catch(e=>{fs.writeFileSync('proof/public-browser-failure.json',JSON.stringify({status:'FAIL',error:e.message,checks,errors},null,2));console.error(e);process.exit(1)});
