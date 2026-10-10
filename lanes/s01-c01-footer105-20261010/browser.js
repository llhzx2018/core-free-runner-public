'use strict';
const fs=require('fs'),assert=require('assert/strict'),{chromium}=require('playwright');
const base='http://127.0.0.1:18880',phase=process.argv[2]||'candidate';
(async()=>{const b=await chromium.launch(),p=await b.newPage({viewport:{width:1440,height:1000}});const errors=[];p.on('pageerror',e=>errors.push(e.message));
 async function inspect(){await p.waitForLoadState('networkidle');await p.waitForFunction(()=>document.documentElement.getAttribute('data-vf-navigation')==='ready'&&document.documentElement.getAttribute('data-vf-runtime-ready')==='stable');await p.evaluate(async()=>{await document.fonts.ready;await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))});return p.evaluate(()=>{
  const rgb=s=>{const a=s.match(/[\d.]+/g).map(Number);return a.slice(0,3)};
  const lum=a=>a.map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4}).reduce((n,v,i)=>n+v*[.2126,.7152,.0722][i],0);
  const f=document.querySelector('.vf-production-footer'),g=f.querySelector('.vf-production-footer-grid');
  const background=getComputedStyle(f).backgroundColor,L=lum(rgb(background));
  const text=Array.from(f.querySelectorAll('.vf-footer-brand-row strong,.vf-production-footer-brand p,.vf-production-footer-col h4,.vf-footer-link,.vf-footer-partner-link,.vf-footer-bottom')).filter(e=>e.getBoundingClientRect().width>0&&e.getBoundingClientRect().height>0).map(e=>{let s=getComputedStyle(e),l=lum(rgb(s.color));return {text:e.textContent.trim().slice(0,80),color:s.color,contrast:(Math.max(l,L)+.05)/(Math.min(l,L)+.05)}});
  const h=document.querySelector('.vf-site-header');return {width:innerWidth,scroll:document.documentElement.scrollWidth,client:document.documentElement.clientWidth,background,grid:getComputedStyle(g).gridTemplateColumns,footer_count:document.querySelectorAll('.vf-production-footer').length,text,header:{text:h.textContent.replace(/\s+/g,' ').trim(),links:Array.from(h.querySelectorAll('a')).map(e=>({text:e.textContent.trim(),path:new URL(e.href).pathname})),height:h.getBoundingClientRect().height},h1:document.querySelectorAll('h1').length};
 })}
 async function timing(){let values=[];for(let i=0;i<3;i++){await p.goto(base+'/tools/');values.push(await p.evaluate(()=>{const n=performance.getEntriesByType('navigation')[0];return n.responseStart-n.startTime}))}return {values,median:[...values].sort((a,b)=>a-b)[1]}}
 if(phase.startsWith('variant-')){
  const variantRows=[];for(const width of [1440,390]){await p.setViewportSize({width,height:1000});await p.goto(base+'/tools/');const r=await inspect();assert.equal(r.scroll,r.client);for(const t of r.text)assert(t.contrast>=4.5,phase+' '+t.text);variantRows.push(r);if(phase==='variant-accordion'&&width===390){const button=p.locator('.vf-footer-section-toggle:visible').first();const before=await button.getAttribute('aria-expanded');assert(['true','false'].includes(before));await button.click();assert.notEqual(await button.getAttribute('aria-expanded'),before);await button.click();assert.equal(await button.getAttribute('aria-expanded'),before);}}
  fs.writeFileSync('proof/footer-'+phase+'.json',JSON.stringify({status:'PASS',rows:variantRows,mobile_accordion:phase==='variant-accordion'?'PASS':'N_A'},null,2));await b.close();return;
 }
 if(phase!=='candidate'){
  await p.goto(base+'/tools/');let r=await inspect();assert.equal(r.footer_count,1);assert.equal(await p.locator('.vf-directory-card').count(),11);assert(r.text.some(x=>x.contrast<2),'baseline contrast bug must be reproduced');
  fs.writeFileSync('proof/footer-'+phase+'.json',JSON.stringify({status:'REPRODUCED',...r,production:'NOT_EXECUTED'},null,2));
  if(phase==='baseline'){fs.writeFileSync('proof/performance-baseline.json',JSON.stringify(await timing(),null,2));await p.screenshot({path:'proof/footer-before-1440.png',fullPage:true});}await b.close();return;
 }
 const rows=[];for(const width of [1920,1440,1319,1024,768,390]){await p.setViewportSize({width,height:1000});await p.goto(base+'/tools/');let r=await inspect();assert.equal(r.scroll,r.client,'page overflow at '+width);assert.equal(r.footer_count,1);assert.equal(r.h1,1);assert(r.text.length>=20);for(const x of r.text)assert(x.contrast>=4.5,'unreadable footer '+width+' '+JSON.stringify(x));rows.push(r);if(width===1440||width===390)await p.screenshot({path:'proof/footer-after-'+width+'.png',fullPage:true});}
 const baseline=JSON.parse(fs.readFileSync('proof/footer-baseline.json'));assert.deepEqual(rows.find(r=>r.width===1440).header,baseline.header,'frozen header changed');
 await p.setViewportSize({width:1440,height:1000});await p.goto(base+'/tools/');assert.equal(await p.locator('.vf-directory-card').count(),11);
 await Promise.all([p.waitForURL(u=>u.searchParams.get('vf_filter')==='export'),p.locator('[data-vf-directory-filter-button=export]').click()]);await p.waitForLoadState('networkidle');assert.equal(await p.locator('.vf-directory-card:visible').count(),2);
 await p.getByRole('searchbox',{name:'Search tools by name or task'}).fill('MP4');assert.equal(await p.locator('.vf-directory-card:visible').count(),1);
 await Promise.all([p.waitForURL(u=>!u.searchParams.has('vf_filter')&&!u.searchParams.has('vf_q')),p.locator('[data-vf-directory-reset]').click()]);await p.waitForLoadState('networkidle');assert.equal(await p.locator('.vf-directory-card:visible').count(),11);
 const faq=p.locator('summary').filter({hasText:'Do these tools bypass DRM or login restrictions?'});await faq.click();assert.equal(await faq.evaluate(e=>e.parentElement.open),true);
 await faq.click();assert.equal(await faq.evaluate(e=>e.parentElement.open),false);
 const contexts=[];for(const route of ['/','/m3u8-downloader/','/m3u8-to-mp4/']){await p.goto(base+route);const r=await inspect();assert.equal(r.footer_count,1);for(const t of r.text)assert(t.contrast>=4.5,'footer context '+route+' '+t.text);contexts.push({route,min_contrast:Math.min(...r.text.map(t=>t.contrast))});if(route!=='/')assert.equal(await p.locator('.vf-m3u8-launchbar').count(),1);}
 const t=await timing(),old=JSON.parse(fs.readFileSync('proof/performance-baseline.json'));assert(t.median<=old.median*2+500);fs.writeFileSync('proof/performance.json',JSON.stringify({status:'PASS',baseline:old,current:t,budget_ms:old.median*2+500,scope:'footer CSS update; same isolated directory navigation'},null,2));
 assert.deepEqual(errors,[]);fs.writeFileSync('proof/footer-browser.json',JSON.stringify({status:'PASS',rows,contexts,controls:'FILTER_SEARCH_CLEAR_FAQ_PASS',header_frozen:'PASS',footer_markup_frozen:'SOURCE_UNCHANGED',columns:'EXISTING_CONFIG_UNCHANGED',directory_tools:11,page_errors:errors,production:'NOT_EXECUTED'},null,2));await b.close();
})().catch(e=>{console.error(e);process.exit(1)});
