'use strict';
/**
 * R8 SEO: actual WordPress+Polylang+RankMath+Theme live HTTP render.
 * No synthetic DOM / monkeypatched head / mocked language relations.
 */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const { chromium }=require('playwright');
const dir='/tmp/s01-r8-seo-live';
const fixture=JSON.parse(fs.readFileSync(dir+'/fixture.json','utf8'));
const origin=process.env.S01_R8_SEO_ORIGIN||'http://127.0.0.1:18880';
assert.equal(fixture.status,'PASS','No actual Polylang fixture');
assert.equal(fixture.polylang,'REAL_PLUGIN');
assert.equal(fixture.rank_math,'REAL_PLUGIN');
for (const u of Object.values(fixture.urls))assert.equal(new URL(u).origin,origin,'Never test nonlocal SEO pages');
const targets=[
  {key:'en',url:fixture.urls.en,kind:'pair',lang:'en',status:200},
  {key:'zh',url:fixture.urls.zh,kind:'pair',lang:'zh',status:200},
  {key:'single',url:fixture.urls.single,kind:'single',lang:'en',status:200},
  {key:'search',url:origin+'/?s=s01r8-unmatched-seo-fixture',kind:'edge',status:200},
  {key:'404',url:origin+'/s01-r8-intentionally-not-found-unique-912638/',kind:'edge',status:404},
];
const norm=s=>String(s||'').replace(/\/+$/,'');
const go=async(page,target)=>{
  const errors=[];
  page.on('pageerror',e=>errors.push(String(e?.message||e)));
  const response=await page.goto(target.url,{waitUntil:'domcontentloaded',timeout:55000});
  assert(response,'Missing actual WordPress HTTP response for '+target.key);
  const doc=await page.evaluate(()=>{
    const head=document.head;
    const links=[...head.querySelectorAll('link[rel]')];
    const canonicals=links.filter(x=>x.rel.toLowerCase()==='canonical').map(x=>x.href);
    const alts=links.filter(x=>x.rel.toLowerCase()==='alternate'&&x.hasAttribute('hreflang')).map(x=>({
      lang:x.getAttribute('hreflang'),url:x.href
    }));
    const robots=[...head.querySelectorAll('meta[name="robots" i]')].map(x=>x.content);
    const descriptions=[...head.querySelectorAll('meta[name="description" i]')].map(x=>x.content);
    const ld=[...head.querySelectorAll('script[type="application/ld+json"]')].map(x=>({
      source:x.getAttribute('data-vf-seo-head')||x.getAttribute('data-vf-jsonld')||'plugin',
      raw:x.textContent||''
    }));
    const schemas=ld.map(x=>{
      try{
        const value=JSON.parse(x.raw);
        return {valid:true,context:value['@context']||'',types:Object.keys(value),source:x.source,
          size:x.raw.length};
      }catch(e){return {valid:false,error:String(e.message||e),source:x.source};}
    });
    return {
      title:document.title,htmlLang:document.documentElement.lang,
      canonicals,alts,robots,descriptions,schemas,
      firstHeading:document.querySelector('h1')?.textContent?.trim().slice(0,100)||'',
      mainExists:!!document.querySelector('main'),
      bodyLength:document.body?.textContent?.length||0,
      headLength:document.head.outerHTML.length,
      themeMarkers:[...head.querySelectorAll('[data-vf-seo-head]')].map(x=>x.getAttribute('data-vf-seo-head')).slice(0,20)
    };
  });
  return {key:target.key,url:target.url,kind:target.kind,http:response.status(),...doc,jsErrors:errors};
};
(async()=>{
 const browser=await chromium.launch({headless:true}),records=[],issues=[];
 try{
  for(const target of targets){
    const page=await browser.newPage({viewport:{width:1440,height:900}});
    try{
      const o=await go(page,target);
      records.push(o);
      const check=(expr,message)=>{if(!expr)issues.push({key:target.key,message,actual:{
        http:o.http,canonicals:o.canonicals,alts:o.alts,robots:o.robots,
        htmlLang:o.htmlLang,schemas:o.schemas,descriptions:o.descriptions
      }});};
      check(o.http===target.status,'Unexpected real HTTP status');
      check(o.bodyLength>200&&o.mainExists,'Real public HTML document/body/main missing');
      check(o.jsErrors.length===0,'Uncaught browser JS exceptions');
      check(o.schemas.every(x=>x.valid),'Malformed JSON-LD script in real head');
      if(target.kind==='pair'||target.kind==='single'){
        check(o.canonicals.length===1,'Published indexable page must have exactly one canonical');
        check(o.canonicals.length===1&&norm(o.canonicals[0])===norm(target.url),'Canonical must be public permalink of exact translated post');
        check(o.robots.every(x=>!/\bnoindex\b/i.test(x)),'Published public page incorrectly noindex');
        check(o.htmlLang.toLowerCase().startsWith(target.lang),'Actual HTML lang differs from assigned Polylang language');
        check(o.schemas.length>0,'Public content must have valid structured data from enabled SEO owner');
        check(o.descriptions.some(x=>x.trim()!==''),'Published SEO description missing');
      }
      if(target.kind==='pair'){
        const map=new Map(o.alts.filter(x=>x.lang!=='x-default').map(x=>[x.lang,norm(x.url)]));
        check(map.size===2&&o.alts.filter(x=>x.lang!=='x-default').length===2,'Translation pair requires exactly 2 unique hreflang links, one writer');
        check(map.get('en')===norm(fixture.urls.en)&&map.get('zh')===norm(fixture.urls.zh),'Hreflang alternates must link bidirectionally to real Polylang permalinks');
        check(map.get(target.lang)===norm(o.canonicals[0]||''),'Hreflang self-link must match self-canonical');
        if(o.alts.some(x=>x.lang==='x-default')){
          check(o.alts.filter(x=>x.lang==='x-default').length===1,'x-default appears more than once');
          check([norm(fixture.urls.en),norm(fixture.urls.zh)].includes(norm(o.alts.find(x=>x.lang==='x-default').url)),'x-default target must be a valid family member');
        }
      }
      if(target.kind==='single'){
        check(o.alts.length===0,'Single untranslated post must not fabricate alternate translations');
      }
      if(target.kind==='edge'){
        check(o.canonicals.length===0,'Search/404 must not receive indexable canonical');
        check(o.alts.length===0,'Search/404 must not emit hreflang');
        check(o.robots.some(x=>/\bnoindex\b/i.test(x)),'Search/404 missing noindex');
      }
    }catch(e){issues.push({key:target.key,message:'BROWSER_OR_HTTP_FATAL',error:String(e?.stack||e)});}
    finally{await page.close();}
  }
 }finally{await browser.close();}
 const report={source:'exact pinned Theme + Ops + M3U8 + real WP Polylang and RankMath',total:targets.length,
    checked:records.length,passed:targets.length-new Set(issues.map(x=>x.key)).size,
    failed:issues.length,issues,records,productionWrites:0};
 fs.writeFileSync(dir+'/seo-live-head-results.json',JSON.stringify(report,null,2));
 console.log('S01_R8_REAL_POLYLANG_RANKMATH_SEO_HTTP '+JSON.stringify({
   total:report.total,checked:report.checked,passed:report.passed,failed:report.failed,
   issues:report.issues,brief:report.records.map(x=>({
     key:x.key,http:x.http,htmlLang:x.htmlLang,canonicalCount:x.canonicals.length,
     hreflang:x.alts.map(a=>a.lang),robots:x.robots,schemas:x.schemas.length
   }))
 }));
 assert.equal(issues.length,0,'Actual real bilingual WordPress/Polylang/RankMath SEO output gate failed');
})().catch(e=>{console.error(e.stack||e);process.exitCode=1;});
