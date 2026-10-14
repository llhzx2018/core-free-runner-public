'use strict';
const fs=require('fs'),assert=require('node:assert/strict'),{chromium}=require('playwright');
const phase=process.argv[2],candidate=phase==='candidate',rows=[],checks=[],errors=[];
const gate=(ok,label,detail)=>{checks.push({pass:!!ok,label,detail});assert(ok,label+' '+JSON.stringify(detail));};
(async()=>{
 const browser=await chromium.launch({headless:true}),page=await browser.newPage();page.on('pageerror',e=>errors.push(e.message));
 for(const locale of ['en','zh'])for(const width of [1024,1280,1440,1920])for(const kind of ['guide_detail','article_detail'])for(const readingWidth of ['focused','balanced','relaxed']){
  await page.setViewportSize({width,height:1000});
  const url='http://127.0.0.1:18880'+(locale==='zh'?'/zh/':'/')+'?vf_template_fixture='+kind+'&reading_width='+readingWidth;
  const response=await page.goto(url);await page.waitForLoadState('networkidle');
  gate(response.status()===200,'actual WordPress response',{locale,width,kind,readingWidth});
  const data=await page.evaluate(()=>{
   const a=document.querySelector('#vf-reading-content'),rect=e=>{const r=e.getBoundingClientRect();return {x:r.x,width:r.width};};
   return {article:a?{...rect(a),font:getComputedStyle(a).fontSize,line:getComputedStyle(a).lineHeight,text:a.textContent.trim()}:null,
    scroll:document.documentElement.scrollWidth,viewport:document.documentElement.clientWidth,
    index:document.querySelectorAll('[data-vf-reading-section-index] a').length,fullTOC:document.querySelectorAll('[data-vf-native-toc]').length,
    support:[...document.querySelectorAll('.vf-theme-module-frame--steps,.vf-theme-module-frame--related_tools,.vf-theme-module-frame--faq,.vf-theme-module-frame--related_posts,.vf-theme-module-frame--cta')].map(e=>({key:e.dataset.vfThemeModule,...rect(e),children:e.children.length})),
    hero:document.querySelector('.vf-reading-entry a')?.getAttribute('href'),headings:[...a.querySelectorAll('h2,h3')].map(e=>({id:e.id,text:e.textContent.trim()})),
    moduleOrder:[...document.querySelectorAll('.vf-theme-module-stack>.vf-theme-module-frame')].map(e=>e.className),share:document.querySelectorAll('[data-vf-share-copy]').length};
  });
  gate(data.article&&data.scroll<=data.viewport+1,'body rendered without horizontal overflow',data);
  gate(data.headings.length===4&&data.headings[0].id==='answer'&&data.article.text.includes('EXT-X-KEY'),'stored headings, authored anchor and code retained',data.headings);
  gate(data.support.length>=3&&data.support.every(s=>s.children>0),'support modules remain rendered',data.support);
  if(candidate){
   gate(data.index===4&&data.fullTOC===0,'short content compact index only',data);
   gate(data.article.font==='18px'&&Math.abs(parseFloat(data.article.line)-32.4)<.1,'desktop reading typography',data.article);
   gate(data.hero==='#vf-reading-content','hero targets the real body',data.hero);
   gate(data.support.every(s=>Math.abs(s.x-data.article.x)<2&&Math.abs(s.width-data.article.width)<2),'support aligns with saved reading width',data);
   const links=page.locator('[data-vf-reading-section-index] a');
   await links.nth(1).focus();await page.keyboard.press('Enter');
   const jump=await page.evaluate(()=>{const id=decodeURIComponent(location.hash.slice(1)),e=document.getElementById(id);return {id,heading:!!e&&/^H[23]$/.test(e.tagName),focus:document.activeElement===e,y:e?.getBoundingClientRect().y};});
   gate(jump.heading&&jump.focus&&jump.y>=0&&jump.y<1000,'keyboard chapter jump and focus',jump);
  }else gate(data.index===0,'original short content has no compact index',data.index);
  const faq=page.locator('.vf-reading-faq-list details').first();
  if(await faq.count()){const before=await faq.getAttribute('open');await faq.locator('summary').click();gate((await faq.getAttribute('open'))!==before,'FAQ toggle remains usable');}
  rows.push({locale,width,kind,readingWidth,...data});
  if(candidate&&width===1440&&readingWidth==='focused')await page.screenshot({path:'proof/reading-'+locale+'-'+kind+'.png',fullPage:true});
 }
 if(candidate){
  for(const locale of ['en','zh'])for(const kind of ['guide_detail','article_detail'])for(const variant of ['long','off','disabled','context-off','levels-off','legacy']){
   await page.goto('http://127.0.0.1:18880'+(locale==='zh'?'/zh/':'/')+'?vf_template_fixture='+kind+'&reading_variant='+variant);
   gate(await page.locator('[data-vf-reading-section-index]').count()===0,'suppressed or long content has no duplicate index',{locale,kind,variant});
   const full=await page.locator('[data-vf-native-toc]').count();gate(full===(variant==='long'?1:0),'full TOC eligibility and disabled states',{locale,kind,variant,full});
  }
  for(const kind of ['problem_detail','glossary_detail']){
   await page.goto('http://127.0.0.1:18880/?vf_template_fixture='+kind);
   gate(await page.locator('[data-vf-reading-section-index]').count()===0,'other reading contexts unchanged',kind);
  }
 }
 gate(errors.length===0,'no uncaught browser errors',errors);
 if(candidate){
  const before=JSON.parse(fs.readFileSync('proof/reading-baseline.json')).rows;
  gate(rows.every((r,i)=>r.article.text===before[i].article.text&&JSON.stringify(r.moduleOrder)===JSON.stringify(before[i].moduleOrder)),'body text and module order retained across all configurations');
 }
 fs.writeFileSync('proof/reading-'+phase+'.json',JSON.stringify({status:'PASS',phase,rows,checks,production:'NOT_EXECUTED',mobile:'NOT_RUN_OWNER_DEFERRED'},null,2));
 await browser.close();
})().catch(e=>{fs.writeFileSync('proof/reading-'+phase+'-failure.json',JSON.stringify({status:'FAIL',error:e.message,rows,checks},null,2));console.error(e);process.exit(1);});
