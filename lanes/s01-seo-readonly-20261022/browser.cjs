'use strict';
const assert=require('node:assert/strict'),{createHash}=require('node:crypto'),{chromium}=require('playwright');
const row={routeId:'route_demo',pageFamily:'tool',pathPattern:'demo',resolver:'vf_theme_url_resolver',canonicalPolicy:'self',hreflangPolicy:'paired',indexability:'index_follow',staticPathPolicy:'required'};
const expected={searchIndexability:'noindex_follow',previewIndexability:'noindex_follow',notFoundRobots:'noindex_follow',virtualRoutePolicy:[row]};
const php=v=>typeof v==='string'?'s:'+Buffer.byteLength(v)+':"'+v+'";':Array.isArray(v)?'a:'+v.length+':{'+v.map((x,i)=>'i:'+i+';'+php(x)).join('')+'}':'a:'+Object.keys(v).length+':{'+Object.entries(v).map(([k,x])=>php(k)+php(x)).join('')+'}';
const revision=createHash('sha256').update(php(expected)).digest('hex');
const manifest={schemaVersion:'1.0.0',owner:'vf-theme',revision,robots:{search:'noindex,follow',preview:'noindex,follow','404':'noindex,follow'},virtualRoutePolicy:[row],ownerBoundary:{themeOwner:'technical_routes_and_system_edges',themeStoresRankMathMeta:false,themeStoresPolylangRelations:false,duplicateContentOwner:false},previewLinks:{route_demo:{pathPattern:'demo',url:'',message:'no page'}}};
const checks=Object.fromEntries(['database','routes','canonical','hreflang','robots','schema','static','owner'].map(k=>[k,{ok:true,message:'ok'}]));
const rv={ok:true,checks,edgeRobots:{search:'noindex,follow',preview:'noindex,follow','404':'noindex,follow'},manifest,routes:{route_demo:{ok:true,checks:Object.fromEntries(['canonical','hreflang','robots','sitemap','static'].map(k=>[k,true]))}},presentation:{sitemap:{status:'empty',count:0,label:'none',message:'no urls',url:'/tool-sitemap.xml'},legacy:{label:'kept',message:'no legacy change'}}};
const reply={ok:true,readback:true,revision,manifest,runtimeVerification:rv,stages:{validate:'passed',execute:'skipped',readback:'passed',verify:'passed'}};
const f=(key,value)=>'<input data-key="'+key+'" value="'+value+'">';
const sel=(key,values)=>'<select data-key="'+key+'">'+values.map(v=>'<option value="'+v+'">'+v+'</option>').join('')+'</select>';
const html='<section data-vf-seo-form-shell="1" data-vf-seo-stored="1" data-vf-seo-needs-save="0" data-vf-seo-checks-ok="1" data-vf-seo-preview-links="{}" data-vf-seo-language-codes="[]">'
 +'<p data-vf-seo-error-summary hidden><span data-vf-seo-error-title></span><span data-vf-seo-error-message></span><ul data-vf-seo-error-list></ul></p>'
 +'<p data-vf-seo-toast hidden><strong data-vf-seo-toast-title></strong><span data-vf-seo-toast-message></span></p>'
 +'<p data-vf-seo-save-feedback></p><div data-vf-seo-result-summary><span></span></div><span data-vf-seo-result-summary-text></span>'
 +'<form data-vf-seo-form><input type="hidden" name="revision" data-vf-seo-revision value="'+revision+'">'
 +'<select data-vf-seo-field="searchIndexability" name="seo[searchIndexability]"><option value="noindex_follow">noindex</option><option value="index_follow">index</option></select>'
 +'<div data-vf-seo-route-table><article data-vf-seo-route-row data-route-key="route-0">'
 +f('routeId','route_demo')+sel('pageFamily',['tool','home'])+f('pathPattern','demo')
 +sel('canonicalPolicy',['self','none'])+sel('hreflangPolicy',['paired','none'])
 +sel('indexability',['index_follow','noindex_follow'])+sel('staticPathPolicy',['required','exclude'])
 +'</article></div><button data-vf-seo-discard type="button" hidden>discard</button>'
 +'<button data-vf-seo-verify type="button" hidden>recheck</button><button data-vf-seo-save type="submit">save</button></form></section>';
(async()=>{
 const browser=await chromium.launch();
 try{
  const page=await browser.newPage();
  await page.setContent(html);
  await page.evaluate(()=>{
   window.VFThemeSeo={ajaxUrl:'/wp-admin/admin-ajax.php',nonce:'test-token',saveAction:'vf_theme_seo_save'};
   window.__seen=[];window.__mode='success';
   window.fetch=async (_url,{body})=>{
    window.__seen.push(body.get('action'));
    if(window.__mode==='failed')return{ok:false,json:async()=>({success:false,data:{failureCode:'RUNTIME_CONSUMER_MISMATCH',message:'runtime blocked'}})};
    if(window.__mode==='offline')throw Error('offline');
    return{ok:true,json:async()=>({success:true,data:window.__fixture})};
   };
  });
  await page.evaluate(v=>window.__fixture=v,reply);
  await page.addScriptTag({path:'target/src/assets/js/admin/admin-seo.js'});
  await page.waitForFunction(()=>document.querySelector('[data-vf-seo-form-shell]').dataset.vfSeoEnhanced==='1');
  const verify=page.locator('[data-vf-seo-verify]');
  assert.equal(await verify.isHidden(),false);
  await verify.click();
  await page.waitForFunction(()=>document.querySelector('[data-vf-seo-save-feedback]').textContent.includes('未执行保存'));
  assert.deepEqual(await page.evaluate(()=>window.__seen),['vf_theme_seo_verify']);
  console.log('PASS_SEO_BROWSER_READONLY_SUCCESS');
  await page.evaluate(()=>window.__mode='failed');
  await verify.click();
  await page.waitForFunction(()=>document.querySelector('[data-vf-seo-error-title]').textContent==='检查未完成');
  assert.equal(await page.locator('[data-vf-seo-form-shell]').getAttribute('data-vf-seo-unknown'),'0');
  console.log('PASS_SEO_BROWSER_CHECK_FAILURE_NOT_UNCERTAIN_WRITE');
  await page.evaluate(()=>window.__mode='offline');
  await verify.click();
  await page.waitForFunction(()=>document.querySelector('[data-vf-seo-error-message]').textContent.includes('本次没有写入设置'));
  assert.equal(await page.locator('[data-vf-seo-form-shell]').getAttribute('data-vf-seo-unknown'),'0');
  console.log('PASS_SEO_BROWSER_NETWORK_FAILURE_NOT_UNCERTAIN_WRITE');
  await page.evaluate(()=>window.__mode='failed');
  await page.locator('[data-vf-seo-field="searchIndexability"]').selectOption('index_follow');
  assert.equal(await verify.isHidden(),true);
  await page.locator('[data-vf-seo-save]').click();
  await page.waitForFunction(()=>document.querySelector('[data-vf-seo-error-title]').textContent==='保存未完成');
  assert.deepEqual(await page.evaluate(()=>window.__seen),['vf_theme_seo_verify','vf_theme_seo_verify','vf_theme_seo_verify','vf_theme_seo_save']);
  console.log('PASS_SEO_BROWSER_REAL_SAVE_UNCHANGED');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
