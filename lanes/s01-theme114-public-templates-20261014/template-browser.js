'use strict';
const fs=require('fs'),assert=require('node:assert/strict'),{chromium}=require('playwright');
const phase=process.argv[2]||'candidate',base='http://127.0.0.1:18880';
const contexts=['home','tool','tool_hub','blog_index','article_detail','guide_index','guide_detail','problem_index','problem_detail','archive_list','faq_page','glossary_index','glossary_detail','legal','contact_page','about_page','basic_page','search','not_found','html_sitemap'];
const widths=phase==='candidate'?[1920,1440,1319,1024,768,390]:[1440,390];
const rows=[],checks=[],pageErrors=[];
function gate(ok,label,detail){checks.push({label,pass:!!ok,detail});assert(ok,label+' '+JSON.stringify(detail));}
(async()=>{
 const browser=await chromium.launch({headless:true});const page=await browser.newPage();page.on('pageerror',e=>pageErrors.push(e.message));
 for(const locale of ['en','zh'])for(const width of widths)for(const kind of contexts){
  await page.setViewportSize({width,height:1000});
  const response=await page.goto(base+(locale==='zh'?'/zh/':'/')+'?vf_template_fixture='+kind);await page.waitForLoadState('domcontentloaded');
  gate(response.status()===200,'fixture actual WordPress response '+kind,response.status());
  gate(await page.locator('[data-vf-fixture-context="'+kind+'"] [data-vf-theme-module-stack="'+kind+'"]').count()===1,'actual registered context '+kind);
  const h1=page.locator('[data-vf-fixture-context] h1');gate(await h1.count()===1,'one rendered H1 '+kind);
  const geometry=await page.evaluate(()=>{const el=document.querySelector('[data-vf-fixture-context] h1'),frame=document.querySelector('[data-vf-fixture-context] .vf-theme-module-frame');return {width:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth,h1Font:parseFloat(getComputedStyle(el).fontSize),h1Text:el.textContent.trim(),framePad:frame?parseFloat(getComputedStyle(frame).paddingTop):null,headHeight:document.querySelector('.vf-site-header')?.getBoundingClientRect().height};});
  gate(geometry.scroll<=geometry.width+1,'no whole-page overflow '+locale+' '+width+' '+kind,geometry);
  if(!['baseline','rollback'].includes(phase)){
   gate(geometry.framePad===0,'module gap applied once '+kind,geometry);
   if(kind==='home')gate(geometry.h1Font<=50,'compact homepage title',geometry.h1Font);
   if(['tool_hub','blog_index','guide_index','problem_index','archive_list','glossary_index','html_sitemap'].includes(kind))gate(geometry.h1Font<=42,'compact directory title '+kind,geometry.h1Font);
   if(['article_detail','guide_detail','problem_detail','glossary_detail','basic_page'].includes(kind))gate(geometry.h1Text==='Synthetic Content Owner '+kind,'actual stored Content Owner heading '+kind,geometry.h1Text);
  }
  rows.push({locale,width,context:kind,...geometry});
  if(phase==='candidate'&&[1440,390].includes(width)&&['home','tool_hub','tool','guide_index','guide_detail','faq_page','legal','search'].includes(kind))await page.screenshot({path:'proof/template-'+locale+'-'+width+'-'+kind+'.png',fullPage:true});
 }
 // Native public routes use their real existing router, not the fixture adapter.
 for(const path of ['/','/tools/','/guides/','/faq/','/about/','/contact/','/privacy-policy/','/search/']){
  await page.setViewportSize({width:1440,height:1000});const response=await page.goto(base+path);await page.waitForLoadState('domcontentloaded');
  gate(response.status()===200,'native public route '+path,response.status());
  gate(await page.locator('#content h1').count()===1,'native title hierarchy '+path);
  if(!['baseline','rollback'].includes(phase)){
   const title=await page.locator('#content h1').evaluate(e=>parseFloat(getComputedStyle(e).fontSize));gate(title<=50,'native first-version title '+path,title);
  }
 }
 await page.goto(base+'/tools/');const search=page.locator('[data-vf-directory-search]').first();
 if(await search.count()){
  const before=await page.locator('.vf-directory-tool-card:visible').count();gate(before>0,'actual tool catalogue has results');
  await search.fill('unmatched-synthetic-term-12345');await page.waitForTimeout(200);gate(await page.locator('.vf-directory-tool-card:visible').count()===0,'actual keyword empty state');
  const reset=page.locator('[data-vf-directory-reset]').first();if(await reset.isVisible()){await reset.click();}else{await search.fill('');}await page.waitForTimeout(200);
  gate(await page.locator('.vf-directory-tool-card:visible').count()===before,'actual catalogue recovery');
 }
 gate(pageErrors.length===0,'no uncaught page JS errors',pageErrors);
 fs.writeFileSync('proof/template-'+phase+'.json',JSON.stringify({status:'PASS',scope:'20 real Theme renderer contexts in isolated WordPress plus native public routes',registeredContexts:contexts.length,rows,checks,production:'NOT_EXECUTED'},null,2));
 await browser.close();
})().catch(e=>{fs.writeFileSync('proof/template-'+phase+'-failure.json',JSON.stringify({status:'FAIL',error:e.message,checks,rows},null,2));console.error(e);process.exit(1);});
