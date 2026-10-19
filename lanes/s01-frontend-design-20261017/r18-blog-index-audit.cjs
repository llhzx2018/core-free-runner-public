'use strict';
const fs=require('node:fs'),{chromium}=require('playwright');
const cases=JSON.parse(fs.readFileSync('proof/cases.json','utf8')).cases;
(async()=>{
 const b=await chromium.launch({headless:true});const checks=[];
 try{
 const p=await b.newPage({viewport:{width:1440,height:900}});
 const query=async (url)=>{const r=await p.goto(url,{waitUntil:'networkidle'});const x=await p.evaluate(()=>{
    const cards=[...document.querySelectorAll('.vf-theme-post-list--blog_index a.vf-directory-card')];
    const empty=document.querySelector('.vf-theme-post-list--blog_index [data-vf-directory-empty]');
    const pagers=[...document.querySelectorAll('.vf-theme-post-list--blog_index .vf-theme-pagination a')];
    const style=s=>{const e=document.querySelector(s);return e?parseFloat(getComputedStyle(e).fontSize):null};
    return {h1:document.querySelectorAll('main h1').length,cards:cards.length,titles:cards.map(e=>e.querySelector('h3')?.textContent.trim()),links:cards.map(e=>e.href),rows:cards.map(e=>e.getAttribute('data-vf-directory-search')||''),empty:empty?!empty.hidden&&getComputedStyle(empty).display!=='none':false,pager:pagers.map(e=>({url:e.href,text:e.textContent.trim(),next:e.classList.contains('next')})),search:!!document.querySelector('.vf-theme-post-list--blog_index input[name="vf_q"]'),font:style('.vf-theme-post-list--blog_index .vf-directory-card p'),searchFont:style('.vf-theme-post-list--blog_index .vf-directory-search input'),mainHeading:document.querySelector('main h1')?.textContent.trim(),canon:[...document.querySelectorAll('link[rel="canonical"]')].map(e=>e.href),description:!!document.querySelector('meta[name="description"]'),headTitle:document.querySelectorAll('title').length,noHorizontal:document.documentElement.scrollWidth<=innerWidth+1};});
    return {status:r.status(),...x};};
 for(const lang of ['en','zh'])for(const width of [1440,1024]){
   const base=cases[lang].blog_index;await p.setViewportSize({width,height:900});
   const a=await query(base);
   let next=a.pager.find(v=>v.next);
   checks.push({lang,width,scenario:'base',...a});
   if(a.status!==200||a.h1!==1||!a.mainHeading||a.cards<3||!a.search||!a.noHorizontal||!a.description||a.headTitle!==1||a.canon.length!==1||a.links.some(x=>!x.startsWith('http'))||a.links.length!==new Set(a.links).size)throw Error('BLOG_BASE_FAIL '+JSON.stringify({lang,width,...a}));
   const keyword=await query(base+'?vf_q=Needleword');
   checks.push({lang,width,scenario:'global_keyword',...keyword});
   if(keyword.status!==200||keyword.cards!==1||!keyword.titles[0].includes('Needleword'))throw Error('BLOG_GLOBAL_SEARCH_FAIL '+JSON.stringify({lang,width,...keyword}));
   const none=await query(base+'?vf_q=never-matches-417231');
   checks.push({lang,width,scenario:'empty',...none});
   if(none.status!==200||none.cards!==0||!none.empty||none.pager.length)throw Error('BLOG_EMPTY_FAIL '+JSON.stringify({lang,width,...none}));
   if(lang==='en'){
     if(!next)throw Error('BLOG_PAGINATION_MISSING '+JSON.stringify(a));
     const second=await query(next.url);
     checks.push({lang,width,scenario:'page2',...second});
     if(second.status!==200||second.cards<1||second.h1!==1||!second.noHorizontal||second.links.some(x=>a.links.includes(x)))throw Error('BLOG_PAGE2_FAIL '+JSON.stringify({lang,width,second}));
     const allSearch=await query(base+'?vf_q=Searchwork');
     const filterNext=allSearch.pager.find(x=>x.next);
     if(!filterNext||!new URL(filterNext.url).searchParams.has('vf_q'))throw Error('BLOG_FILTER_PAGER_DROPS_KEYWORD '+JSON.stringify(allSearch));
     const s2=await query(filterNext.url);
     checks.push({lang,width,scenario:'search_page2',...s2});
     if(s2.status!==200||s2.cards<1||s2.titles.some(t=>!t?.includes('Searchwork')))throw Error('BLOG_SEARCH_PAGE2_FAIL '+JSON.stringify(s2));
   }
 }
 fs.writeFileSync('proof/blog-audit.json',JSON.stringify({status:'PASS',checks,mobile:'DEFERRED',production:'UNTOUCHED'},null,2));
 console.log('BLOG_INDEX_BILINGUAL_DESKTOP_AUDIT_PASS '+checks.length+'/'+checks.length);
 }finally{await b.close()}
})().catch(e=>{console.error(e);process.exit(1)});
