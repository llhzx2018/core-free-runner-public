'use strict';
const fs=require('node:fs'),{chromium}=require('playwright');
const cases=JSON.parse(fs.readFileSync('proof/cases.json','utf8')).cases;
(async()=>{
 const b=await chromium.launch({headless:true});const checks=[];
 try{
  const p=await b.newPage({viewport:{width:1440,height:900}});
  for(const lang of ['en','zh'])for(const width of [1440,1024]){
   await p.setViewportSize({width,height:900});
   const r=await p.goto(cases[lang].blog_index,{waitUntil:'networkidle'});
   const v=await p.evaluate(()=>{
     const one=s=>document.querySelector('.vf-theme-post-list--blog_index '+s);
     const size=s=>{const x=one(s);return x?parseFloat(getComputedStyle(x).fontSize):null};
     const cards=[...document.querySelectorAll('.vf-theme-post-list--blog_index a.vf-directory-card')];
     const direct=cards.filter(c=>c.querySelector(':scope > .vf-post-card-media.is-fallback'));
     const editorial=cards.filter(c=>c.querySelector(':scope > .vf-post-card-media:not(.is-fallback)'));
     const section=one('');
     const block=document.querySelector('.vf-theme-post-list--blog_index');
     return {count:cards.length,fallbackCount:direct.length,realCoverCount:editorial.length,metadataFont:size('.vf-directory-card-meta'),titleFont:size('.vf-directory-card h3'),excerptFont:size('.vf-directory-card p'),paddingBottom:block?getComputedStyle(block).paddingBottom:null,overflow:document.documentElement.scrollWidth>innerWidth+1,h1:document.querySelectorAll('main h1').length,links:cards.every(x=>x.hasAttribute('href')),search:!!one('input[name="vf_q"]'),pager:!!one('.vf-theme-pagination'),content:cards.every(x=>x.querySelector('h3')&&x.querySelector('p'))};
   });
   const pass=r.status()===200&&v.count>=3&&v.fallbackCount===0&&v.metadataFont>=13&&v.titleFont>=20&&v.excerptFont>=15&&parseFloat(v.paddingBottom)<=24&&!v.overflow&&v.h1===1&&v.links&&v.search&&v.content;
   const item={lang,width,status:r.status(),pass,...v};checks.push(item);
   if(!pass)throw Error('BLOG_READING_DESKTOP_FAIL '+JSON.stringify(item));
  }
  fs.writeFileSync('proof/blog-reading-v135140.json',JSON.stringify({status:'PASS',checks,production:'UNTOUCHED',mobile:'DEFERRED'},null,2));
  console.log('BLOG_READING_V135140_DESKTOP_PASS '+checks.length+'/'+checks.length);
 }finally{await b.close()}
})().catch(e=>{console.error(e);process.exit(1)});
