'use strict';
const fs=require('node:fs'),{chromium}=require('playwright');
const fixture=JSON.parse(fs.readFileSync('proof/article-detail-fixture.json','utf8')).posts;
const cases=JSON.parse(fs.readFileSync('proof/cases.json','utf8')).cases;
(async()=>{
const browser=await chromium.launch({headless:true}),all=[];
try{
const page=await browser.newPage({viewport:{width:1440,height:900},permissions:['clipboard-read','clipboard-write']});
for(const lang of ['en','zh'])for(const width of [1440,1024]){
 await page.setViewportSize({width,height:900});
 for(const variant of ['long','short']){
  const url=fixture[lang][variant];const resp=await page.goto(url,{waitUntil:'networkidle'});
  const v=await page.evaluate(()=>{
    const shell=document.querySelector('[data-vf-reading-context="article_detail"]');
    const toc=[...document.querySelectorAll('.vf-reading-toc a[href^="#"],.vf-reading-section-index a[href^="#"]')];
    const footer=document.querySelector('.vf-article-reading-footer');
    const anchors=toc.filter(a=>!document.getElementById(decodeURIComponent(a.getAttribute('href').slice(1)))).map(x=>x.href);
    const ld=[...document.querySelectorAll('head script[type="application/ld+json"]')];
    const badld=ld.filter(x=>{try{JSON.parse(x.textContent);return false}catch{return true}}).length;
    const content=document.querySelector('.vf-reading-entry');
    return {pageTitle:document.title,h1:document.querySelectorAll('main h1').length,hasShell:!!shell,hasReading:!!content,headings:content?.querySelectorAll('h2').length||0,toc:toc.length,badAnchors:anchors,
       bodyCopy:content?.innerText.length||0,hasTool:!!content?.querySelector('a[href*="m3u8-checker"]'),
       canon:[...document.querySelectorAll('head link[rel="canonical"]')].map(x=>x.href),
       description:document.querySelectorAll('head meta[name="description"]').length,
       docTitle:document.querySelectorAll('head title').length,jsonldValid:badld===0,
       footer:!!footer,share:!!footer?.querySelector('[data-vf-article-share]'),
       copy:!!footer?.querySelector('[data-vf-article-copy]'),
       adjacent:footer?.querySelectorAll('.vf-reading-post-navigation a[href]').length||0,
       overflow:document.documentElement.scrollWidth>innerWidth+1};
  });
  const pass=resp.status()===200&&v.h1===1&&v.hasShell&&v.hasReading&&v.headings>=1&&v.badAnchors.length===0&&v.docTitle===1&&v.canon.length===1&&v.description===1&&v.jsonldValid&&v.footer&&v.copy&&!v.overflow&&(variant==='short'||(v.headings>=4&&v.toc>=3&&v.hasTool));
  let item={lang,width,variant,status:resp.status(),pass,...v};all.push(item);
  if(!pass)throw Error('BLOG_ARTICLE_DETAIL_FAIL '+JSON.stringify(item));
  if(variant==='long'&&v.toc){
   const selector='.vf-reading-toc a[href^="#"],.vf-reading-section-index a[href^="#"]';
   const target=await page.locator(selector).first().getAttribute('href');
   await page.locator(selector).first().click();
   if(new URL(page.url()).hash!==target)throw Error('BLOG_ARTICLE_TOC_CLICK_FAIL '+JSON.stringify({lang,width,target,actual:page.url()}));
  }
 }
 await page.goto(cases[lang].blog_index,{waitUntil:'networkidle'});
 const href=await page.locator('.vf-theme-post-list--blog_index a.vf-directory-card').first().getAttribute('href');
 const title=(await page.locator('.vf-theme-post-list--blog_index a.vf-directory-card h3').first().innerText()).trim();
 if(!href)throw Error('BLOG_CARD_NO_LINK '+lang);
 const detail=await page.goto(href,{waitUntil:'networkidle'});
 const actual=await page.evaluate(()=>({h1:document.querySelector('main h1')?.textContent.trim(),context:document.querySelector('[data-vf-reading-context]')?.getAttribute('data-vf-reading-context')}));
 const pass=detail.status()===200&&actual.context==='article_detail'&&actual.h1===title;
 const item={lang,width,variant:'list_card_to_article',status:detail.status(),href,title,actual,pass};all.push(item);
 if(!pass)throw Error('BLOG_LIST_TO_ARTICLE_FAIL '+JSON.stringify(item));
}
fs.writeFileSync('proof/blog-article-detail.json',JSON.stringify({status:'PASS',tests:all,mobile:'DEFERRED',production:'UNTOUCHED'},null,2));
console.log('BLOG_ARTICLE_DETAIL_DESKTOP_PASS '+all.length+'/'+all.length);
}finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
