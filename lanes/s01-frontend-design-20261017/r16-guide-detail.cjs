'use strict';
const fs=require('node:fs'),{chromium}=require('playwright');
const cases=JSON.parse(fs.readFileSync('proof/cases.json','utf8')).cases;
const lum=rgb=>{const t=rgb.map(n=>{n/=255;return n<=.04045?n/12.92:((n+.055)/1.055)**2.4});return .2126*t[0]+.7152*t[1]+.0722*t[2]};
(async()=>{
 const browser=await chromium.launch({headless:true});const checks=[];
 try{
  const page=await browser.newPage({viewport:{width:1440,height:900}});
  for(const lang of ['en','zh'])for(const width of [1440,1024]){
   await page.setViewportSize({width,height:900});
   const url=cases[lang].guide_detail;
   const response=await page.goto(url,{waitUntil:'networkidle'});
   const f=await page.evaluate(()=>{
     const get=s=>document.querySelector(s),tag=get('.vf-reading-hero--guide .vf-family-eyebrow');
     const facts=get('.vf-article-hero-meta>*'),cue=get('.vf-reading-entry>div>p');
     const anchors=[...document.querySelectorAll('.vf-reading-toc a[href^="#"],.vf-reading-section-index a[href^="#"]')];
     const canvas=document.createElement('canvas');canvas.width=1;canvas.height=1;const ctx=canvas.getContext('2d',{willReadFrequently:true});
     const rgb=s=>{ctx.clearRect(0,0,1,1);ctx.fillStyle=s;ctx.fillRect(0,0,1,1);return [...ctx.getImageData(0,0,1,1).data].slice(0,3)};
     const colors=tag?getComputedStyle(tag):null;
     return {title:document.title,h1:document.querySelectorAll('main h1').length,article:!!get('article.vf-reading-article'),
       sections:document.querySelectorAll('.vf-reading-article h2').length,toc:anchors.length,
       badAnchors:anchors.filter(e=>!document.getElementById(decodeURIComponent(e.getAttribute('href').slice(1)))).map(e=>e.hash),
       tool:!!get('.vf-reading-article a[href*="m3u8-checker"]'),adjacent:document.querySelectorAll('.vf-reading-post-navigation a[href]').length,
       titleCount:document.querySelectorAll('head title').length,canonicalCount:document.querySelectorAll('head link[rel="canonical"]').length,
       jsonldValid:[...document.querySelectorAll('head script[type="application/ld+json"]')].every(e=>{try{JSON.parse(e.textContent);return true}catch{return false}}),
       metaFont:facts?parseFloat(getComputedStyle(facts).fontSize):null,cueFont:cue?parseFloat(getComputedStyle(cue).fontSize):null,
       foreground:colors?rgb(colors.color):null,background:colors?rgb(colors.backgroundColor):null,
       overflow:document.documentElement.scrollWidth>innerWidth+1};
   });
   const a=f.foreground&&lum(f.foreground),b=f.background&&lum(f.background);
   const ratio=a!==null&&b!==null?(Math.max(a,b)+.05)/(Math.min(a,b)+.05):0;
   const pass=response.status()===200&&f.h1===1&&f.article&&f.sections>=3&&f.toc>=3&&f.badAnchors.length===0&&f.tool&&f.titleCount===1&&f.canonicalCount<=1&&f.jsonldValid&&f.metaFont===14&&f.cueFont===15&&ratio>=4.5&&!f.overflow;
   checks.push({lang,width,pass,status:response.status(),contrast:Number(ratio.toFixed(2)),...f});
   if(!pass)throw Error('Guide detail '+lang+' '+width+' '+JSON.stringify(checks.at(-1)));
   const selector='.vf-reading-toc a[href^="#"],.vf-reading-section-index a[href^="#"]';
   const anchor=await page.locator(selector).first().getAttribute('href');
   await page.locator(selector).first().click();
   if(new URL(page.url()).hash!==anchor)throw Error('TOC click failed '+lang+' '+width);
   await page.goBack({waitUntil:'domcontentloaded'});
   if(new URL(page.url()).hash)throw Error('Browser back failed '+lang+' '+width);
   const bad=await page.evaluate(()=>[...document.querySelectorAll('.vf-reading-post-navigation a,.vf-reading-article a')].map(e=>e.href).filter(h=>{const u=new URL(h);return u.origin!==location.origin||u.pathname.includes('/wp-admin/')}));
   if(bad.length)throw Error('Unsafe article links '+JSON.stringify(bad));
  }
  fs.writeFileSync('proof/guide-detail-browser.json',JSON.stringify({status:'PASS',checks,scope:'ISOLATED_WORDPRESS_MARIADB_CHROMIUM_DESKTOP',mobile:'DEFERRED'},null,2));
  console.log('GUIDE_DETAIL_DESKTOP=PASS '+checks.length+'/'+checks.length+' bilingual cases');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
