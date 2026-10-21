const {chromium}=require('playwright'),fs=require('fs');
(async()=>{
 const mode=process.argv[2]||'candidate',checks=[],baseline={},cases=JSON.parse(fs.readFileSync('proof/cases.json')).cases;
 const check=(name,pass,detail)=>checks.push({name,pass:!!pass,detail});
 const browser=await chromium.launch({headless:true});
 try{
  for(const lang of ['en','zh']){
   const context=await browser.newContext({viewport:{width:1440,height:1000},permissions:['clipboard-read','clipboard-write']});
   const page=await context.newPage(),url=cases[lang].article_detail,prefix=lang==='zh'?'/zh/':'/';
   const errors=[];page.on('pageerror',e=>errors.push(e.message));
   await page.goto(url,{waitUntil:'load'});
   baseline[lang]={body:await page.locator('#vf-reading-content').innerHTML(),title:await page.locator('h1').innerText()};
   await page.goto('http://127.0.0.1:18880'+prefix+'m3u8-backup-restore/',{waitUntil:'load'});
   baseline[lang].backup=await page.locator('#content').innerText();
   if(mode==='baseline'){await context.close();continue;}
   const old=JSON.parse(fs.readFileSync('proof/other-baseline.json'));
   check(lang+' backup route text unchanged',old[lang].backup===baseline[lang].backup);
   for(const width of [1024,1280,1440,1920]){
    await page.setViewportSize({width,height:1000});
    const response=await page.goto(url+'?vf_article_review=legacy&vf_article_mode=inline',{waitUntil:'load'});
    await page.evaluate(()=>document.fonts.ready);
    const actual=await page.evaluate(()=>({
     body:document.querySelector('#vf-reading-content')?.innerHTML,
     title:document.querySelector('h1')?.textContent,
     h1s:document.querySelectorAll('h1').length,
     relatedTitle:document.querySelector('[data-vf-theme-module="related_tools"] h2')?.textContent,
     relatedDesc:document.querySelector('[data-vf-theme-module="related_tools"] p')?.textContent,
     faqTitle:document.querySelector('[data-vf-theme-module="faq"] h2')?.textContent,
     faqDesc:document.querySelector('[data-vf-theme-module="faq"] .vf-reading-support-head p')?.textContent,
     cta:document.querySelector('[data-vf-theme-module="cta"] a')?.getAttribute('href'),
     progressLabel:document.querySelector('[data-vf-reading-progress]')?.getAttribute('aria-label'),
     toc:[...document.querySelectorAll('[data-vf-toc-link]')].map(n=>({id:n.dataset.vfTocLink,exists:!!document.getElementById(n.dataset.vfTocLink)})),
     tables:document.querySelectorAll('#vf-reading-content table').length,
     code:document.querySelectorAll('#vf-reading-content pre code').length,
     overflow:document.documentElement.scrollWidth>innerWidth+2,
     canonical:document.querySelector('link[rel="canonical"]')?.href,
     robots:document.querySelector('meta[name="robots"]')?.content
    }));
    const id=lang+' '+width;
    check(id+' actual article route and body preserved',response.status()===200&&actual.h1s===1&&actual.body===old[lang].body&&actual.title===old[lang].title,{status:response.status(),h1s:actual.h1s});
    check(id+' reader-facing support copy',actual.relatedTitle===(lang==='zh'?'需要操作时，选择工具':'Continue with a tool')&&!/Send readers|把读者|isolated/.test(actual.relatedDesc),actual.relatedDesc);
    check(id+' generic tool FAQ accurately labeled',actual.faqTitle===(lang==='zh'?'工具使用问题':'Tool usage questions')&&!/directly related|当前页面直接/.test(actual.faqDesc),actual.faqDesc);
    check(id+' article continuation and progress localized',actual.cta==='http://127.0.0.1:18880'+prefix+'blog/'&&actual.progressLabel===(lang==='zh'?'阅读进度':'Reading progress'),actual);
    check(id+' real headings table and code remain usable',actual.toc.length>=3&&actual.toc.every(n=>n.exists)&&actual.tables>0&&actual.code>0,actual.toc);
    check(id+' no desktop overflow and canonical unchanged',!actual.overflow&&actual.canonical===url,actual);
    if(width===1440)await page.screenshot({path:'proof/'+lang+'-article.png',fullPage:true});
   }
   await page.setViewportSize({width:1440,height:1000});
   for(const layout of ['sidebar','always','off']){
    await page.goto(url+'?vf_article_mode='+layout,{waitUntil:'load'});
    const sidebar=page.locator('.vf-sidebar');
    check(lang+' '+layout+' saved layout respected',layout==='off'?await sidebar.count()===0:await sidebar.count()===1);
    if(layout!=='off')check(lang+' '+layout+' sidebar label localized',await sidebar.getAttribute('aria-label')===(lang==='zh'?'阅读侧栏':'Reading sidebar'));
   }
   for(const variant of ['legacy','custom']){
    await page.goto(url+'?vf_article_review='+variant+'&vf_article_mode=inline',{waitUntil:'load'});
    const actual=await page.evaluate(()=>Object.fromEntries(['related_tools','faq','cta'].map(m=>{const n=document.querySelector('[data-vf-theme-module="'+m+'"]');return[m,{title:n?.querySelector('h2')?.textContent.trim(),description:n?.querySelector('p')?.textContent.trim()}]})));
    check(lang+' '+variant+' configured copy',variant==='custom'?Object.entries(actual).every(([m,v])=>v.title==='Owner '+m+' title'&&v.description==='Owner '+m+' description'):!JSON.stringify(actual).includes('Send readers')&&actual.cta.title===(lang==='zh'?'按需要继续阅读。':'Continue reading when you are ready.'),actual);
   }
   await page.goto(url+'?vf_article_mode=inline',{waitUntil:'load'});
   const link=page.locator('[data-vf-toc-link]').first(),target=await link.getAttribute('href');
   await link.focus();await page.keyboard.press('Enter');
   check(lang+' keyboard directory jumps to real heading',await page.evaluate(()=>location.hash)===target,target);
   await page.locator('[data-vf-article-copy]').click();
   await page.waitForFunction(()=>document.querySelector('[data-vf-article-action-status]')?.textContent.trim());
   const copied=await page.evaluate(()=>navigator.clipboard.readText());
   check(lang+' copy uses actual canonical article URL',copied===url,{copied,url});
   const share=page.locator('[data-vf-article-share]');
   check(lang+' unsupported system sharing remains hidden',await page.evaluate(()=>typeof navigator.share==='function')||await share.isHidden());
   const adjacent=await page.locator('.vf-reading-post-navigation a').evaluateAll(ns=>ns.map(n=>n.href));
   check(lang+' adjacent article language preserved',adjacent.length>0&&adjacent.every(h=>new URL(h).pathname.startsWith(prefix)&&!(lang==='en'&&new URL(h).pathname.startsWith('/zh/'))),adjacent);
   const b=await page.goto('http://127.0.0.1:18880'+prefix+'blog/',{waitUntil:'load'});
   check(lang+' continue-reading destination exists',b.status()===200);
   check(lang+' no script errors',errors.length===0,errors);
   await context.close();
  }
 }finally{await browser.close();}
 if(mode==='baseline'){fs.writeFileSync('proof/other-baseline.json',JSON.stringify(baseline,null,2));console.log('OTHER_ROUTES_BASELINE_CAPTURED');return;}
 const result={status:checks.every(c=>c.pass)?'PASS':'FAIL',count:checks.length,passed:checks.filter(c=>c.pass).length,checks};
 fs.writeFileSync('proof/browser-results.json',JSON.stringify(result,null,2));
 console.log('ARTICLE_READING_RESULT '+JSON.stringify({status:result.status,count:result.count,passed:result.passed,failures:checks.filter(c=>!c.pass)}).slice(0,18000));
 if(result.status!=='PASS')process.exitCode=1;
})().catch(e=>{console.error(e);process.exitCode=1;});
