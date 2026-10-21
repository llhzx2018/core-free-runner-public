const {chromium}=require('playwright');
const fs=require('fs');
(async()=>{
 const browser=await chromium.launch({headless:true}),checks=[],baseline={};
 const check=(name,ok,detail)=>checks.push({name,pass:!!ok,detail});
 const mode=process.argv[2]||'candidate';
 async function support(page){
  return page.evaluate(()=>({
   related:[...document.querySelectorAll('.vf-tool-related-card')].map(n=>({href:n.getAttribute('href'),text:n.textContent.trim()})),
   cta:document.querySelector('[data-vf-theme-module="cta"]')?.textContent.trim(),
   diagnostic:document.querySelector('.vf-tool-runtime-boundary a')?.outerHTML
  }));
 }
 try{
  for(const lang of ['en','zh']){
   const prefix=lang==='zh'?'/zh/':'/',base='http://127.0.0.1:18880'+prefix;
   const context=await browser.newContext({viewport:{width:1440,height:900}});
   const page=await context.newPage();
   await page.goto(base+'m3u8-player/',{waitUntil:'load'});
   baseline[lang]=await support(page);
   if(mode==='baseline'){await context.close();continue;}
   const prev=JSON.parse(fs.readFileSync('proof/other-baseline.json'));
   check(lang+' player recommendations CTA and diagnostics unchanged',JSON.stringify(prev[lang])===JSON.stringify(baseline[lang]),baseline[lang]);
   for(const width of [1024,1280,1440,1920]){
    await page.setViewportSize({width,height:900});
    const response=await page.goto(base+'m3u8-backup-restore/',{waitUntil:'load'});
    const actual=await page.evaluate(()=>({
     status:document.querySelector('.vf-backup-restore')?.getAttribute('data-vf-backup-ready'),
     related:[...document.querySelectorAll('.vf-tool-related-card')].map(n=>({href:n.getAttribute('href'),text:n.textContent.trim()})),
     relatedTitle:document.querySelector('.vf-tool-related-section h2')?.textContent.trim(),
     ctaTitle:document.querySelector('[data-vf-theme-module="cta"] h2')?.textContent.trim(),
     ctaHref:document.querySelector('[data-vf-theme-module="cta"] a')?.getAttribute('href'),
     diagnosticHref:document.querySelector('.vf-tool-runtime-boundary a')?.getAttribute('href'),
     diagnostic:document.querySelector('.vf-tool-runtime-boundary a')?.textContent.trim(),
     guide:document.querySelector('.vf-tool-runtime-guide')?.textContent,
     faq:document.querySelector('.vf-tool-faq-section .vf-tool-support-head p')?.textContent,
     overflow:document.documentElement.scrollWidth>innerWidth+2,
     restoreDisabled:document.querySelector('[data-vf-backup-action="restore-backup"]')?.disabled,
     primary:document.querySelector('[data-vf-backup-action="preview-workspace"]')?.textContent.trim(),
     toolCount:document.querySelectorAll('#tool').length
    }));
    const id=lang+' '+width;
    check(id+' real route and Provider mount',response.status()===200&&!!actual.primary,actual);
    check(id+' focused local-data routes',JSON.stringify(actual.related.map(n=>new URL(n.href,page.url()).pathname))===JSON.stringify(['iptv-manager/','m3u8-test-links/','tools/'].map(p=>prefix+p)),actual.related);
    check(id+' backup-specific headings',lang==='zh'?actual.relatedTitle==='继续使用本地数据'&&actual.ctaTitle==='更改本地数据前，先保留备份。':actual.relatedTitle==='Continue with your local data'&&actual.ctaTitle==='Keep a backup before changing local data.',actual);
    check(id+' safe same-page workspace links',actual.ctaHref===base+'m3u8-backup-restore/#tool'&&actual.diagnosticHref===actual.ctaHref&&actual.toolCount===1,actual);
    check(id+' backup-specific retry privacy and FAQ',!(/Playback or access|播放或访问失败|DRM|源站访问限制|switching to a diagnostic|切换到诊断/.test([actual.diagnostic,actual.guide,actual.faq].join(' ')))&&/JSON/.test(actual.guide),actual);
    check(id+' restore remains gated',actual.restoreDisabled===true,actual);
    check(id+' desktop has no horizontal overflow',!actual.overflow,actual);
    if(width===1440)await page.screenshot({path:'proof/'+lang+'-backup-followup.png',fullPage:true});
   }
   // Visit every emitted destination through the actual localized public route.
   for(const target of ['iptv-manager/','m3u8-test-links/','tools/']){
    const response=await page.goto(base+target,{waitUntil:'load'});
    check(lang+' related destination '+target+' exists',response.status()===200&&page.url().startsWith(base+target),{status:response.status(),url:page.url()});
   }
   for(const variant of ['legacy','custom']){
    await page.goto(base+'m3u8-backup-restore/?vf_backup_review='+variant,{waitUntil:'load'});
    const text=await page.evaluate(()=>Object.fromEntries(['related_tools','cta','faq'].map(m=>{
     const n=document.querySelector('[data-vf-theme-module="'+m+'"]');
     return[m,{title:n?.querySelector('h2')?.textContent.trim(),description:n?.querySelector('p')?.textContent.trim()}];
    })));
    check(lang+' '+variant+' configured titles and descriptions',variant==='custom'?Object.entries(text).every(([m,t])=>t.title==='Owner '+m+' title'&&t.description==='Owner '+m+' description'):text.related_tools.title===(lang==='zh'?'继续使用本地数据':'Continue with your local data')&&text.cta.title===(lang==='zh'?'更改本地数据前，先保留备份。':'Keep a backup before changing local data.')&&!/diagnostic|诊断/.test(text.faq.description),text);
   }
   await page.goto(base+'m3u8-backup-restore/',{waitUntil:'load'});
   const before=await page.evaluate(()=>({storage:JSON.stringify(localStorage),disabled:document.querySelector('[data-vf-backup-action="restore-backup"]').disabled,ready:document.querySelector('.vf-backup-restore').dataset.vfBackupReady}));
   const cta=page.locator('[data-vf-theme-module="cta"] a');
   await cta.focus(); await page.keyboard.press('Enter');
   await page.waitForURL('**/#tool');
   const after=await page.evaluate(()=>({storage:JSON.stringify(localStorage),disabled:document.querySelector('[data-vf-backup-action="restore-backup"]').disabled,ready:document.querySelector('.vf-backup-restore').dataset.vfBackupReady}));
   check(lang+' keyboard CTA returns to workspace without data action',JSON.stringify(before)===JSON.stringify(after)&&new URL(page.url()).hash==='#tool',{before,after,url:page.url()});
   await context.close();
  }
 }finally{await browser.close();}
 if(mode==='baseline'){fs.writeFileSync('proof/other-baseline.json',JSON.stringify(baseline,null,2));console.log('OTHER_ROUTES_BASELINE_CAPTURED');return;}
 const result={status:checks.every(x=>x.pass)?'PASS':'FAIL',count:checks.length,passed:checks.filter(x=>x.pass).length,checks};
 fs.writeFileSync('proof/browser-results.json',JSON.stringify(result,null,2));
 console.log('BACKUP_FOLLOWUP_RESULT '+JSON.stringify({status:result.status,count:result.count,passed:result.passed,failures:checks.filter(x=>!x.pass)}).slice(0,20000));
 if(result.status!=='PASS')process.exitCode=1;
})().catch(e=>{console.error(e);process.exitCode=1;});
