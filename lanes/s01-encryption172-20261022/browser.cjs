const {chromium}=require('playwright');
const fs=require('fs');
const base='http://127.0.0.1:18880';
const baseline=process.argv.includes('--baseline');
const phase=baseline?'before':'after';
const rows=[],writes=[],errors=[];
const section=n=>`section[data-vf-theme-module="${n}"]`;
const check=(v,m)=>{if(!v)throw Error(m)};
(async()=>{
 const browser=await chromium.launch();
 const widths=baseline?[1440]:[1440,1319,1024];
 for(const language of ['en','zh'])for(const width of widths){
  const context=await browser.newContext({viewport:{width,height:1000}}),page=await context.newPage();
  page.on('request',r=>{if(r.url().startsWith(base)&&!['GET','HEAD','OPTIONS'].includes(r.method()))writes.push({method:r.method(),path:new URL(r.url()).pathname})});
  page.on('pageerror',e=>errors.push(String(e)));
  const path=(language==='zh'?'/zh':'')+'/m3u8-encryption-detector/';
  const response=await page.goto(base+path,{waitUntil:'networkidle'});
  check(response.status()===200,`${phase} ${path} HTTP`);
  const steps=page.locator(section('steps')),faq=page.locator(section('faq')),related=page.locator(section('related_tools')),cta=page.locator(section('cta'));
  await faq.waitFor();
  const stepText=await steps.textContent(),faqText=await faq.textContent();
  const head=await page.evaluate(()=>({title:document.title,h1:[...document.querySelectorAll('h1')].map(e=>e.textContent.trim()),canonical:[...document.querySelectorAll('link[rel=canonical]')].map(e=>e.href),hreflang:[...document.querySelectorAll('link[hreflang]')].map(e=>[e.hreflang,e.href]),robots:[...document.querySelectorAll('meta[name=robots]')].map(e=>e.content),description:[...document.querySelectorAll('meta[name=description]')].map(e=>e.content)}));
  check(head.h1.length===1&&head.canonical.length===1,`${phase} unique title/canonical`);
  if(baseline){
   check(stepText.includes(language==='zh'?'整理分组和重复项':'Clean groups and duplicates'),'actual old wrong steps');
   check(faqText.includes(language==='zh'?'频道都在线':'every channel is live'),'actual old wrong FAQ');
  }else{
   for(const term of ['EXT-X-KEY','METHOD','URI','IV'])check((stepText+faqText).includes(term),'actual topic '+term);
   check(!/IPTV|Clean groups|频道都在线|整理分组|重复项/.test(stepText+faqText),'actual unrelated copy removed');
   check(await steps.locator('[data-vf-tool-step]').count()===3,'actual three steps');
   check(await faq.locator('details').count()===3,'actual three answers');
   check(faqText.includes(language==='zh'?'不获取加密密钥':'does not fetch encryption keys'),'actual metadata boundary');
   const second=faq.locator('details').nth(1);
   if(await second.evaluate(e=>e.open))await second.locator('summary').click();
   await second.locator('summary').focus();await page.keyboard.press('Enter');
   await page.waitForFunction(el=>el.open,await second.elementHandle());
   check(await second.locator('p').isVisible(),'keyboard answer expands');
   await page.keyboard.press('Enter');await page.waitForFunction(el=>!el.open,await second.elementHandle());
   const targets=await related.locator('a').evaluateAll(es=>es.map(e=>new URL(e.href).pathname));
   const prefix=language==='zh'?'/zh':'';
   check(JSON.stringify(targets)===JSON.stringify(['/m3u8-playlist-checker/','/m3u8-segment-viewer/','/m3u8-player/'].map(p=>prefix+p)),'actual focused next tools');
   check((await related.locator('h2').textContent()).includes(language==='zh'?'加密':'encryption'),'actual focused related heading');
   const ctaHref=await cta.locator('a').getAttribute('href');
   check(new URL(ctaHref,base).pathname===prefix+'/m3u8-playlist-checker/','actual CTA target');
   check((await cta.locator('a').textContent()).includes(language==='zh'?'检查播放清单':'Check playlist'),'actual action label');
   check((await cta.locator('h2').textContent()).includes(language==='zh'?'清单结构':'playlist structure'),'legacy generic title no longer overrides');
   for(const part of [steps,faq,related,cta]){
    const geom=await part.evaluate(e=>{const r=e.getBoundingClientRect();return{left:r.left,right:r.right,scroll:e.scrollWidth,client:e.clientWidth}});
    check(geom.left>=-1&&geom.right<=width+1&&geom.scroll<=geom.client+1,'changed section fits desktop '+width);
   }
   if(width===1440){
    for(const target of targets){const r=await page.request.get(base+target);check(r.status()===200,'recommended target reachable '+target)}
    await cta.locator('a').click();await page.waitForURL(base+prefix+'/m3u8-playlist-checker/');
    check((await page.locator('h1').count())===1,'CTA lands on real checker');
    await page.goBack({waitUntil:'networkidle'});
   }
  }
  await page.screenshot({path:`proof/${phase}-encryption-${language}-${width}.png`,fullPage:true});
  rows.push({language,width,path,head,steps:stepText,faq:faqText,status:'PASS'});
  // One real management page in each locale confirms the family remains distinct.
  if(width===1440){
   await page.goto(base+(language==='zh'?'/zh':'')+'/iptv-manager/',{waitUntil:'networkidle'});
   const control={language,steps:await page.locator(section('steps')).textContent(),faq:await page.locator(section('faq')).textContent()};
   check(control.steps.includes(language==='zh'?'整理分组和重复项':'Clean groups and duplicates'),'IPTV retains actual management workflow');
   fs.writeFileSync(`proof/${phase}-iptv-${language}.json`,JSON.stringify(control,null,2));
  }
  await context.close();
 }
 check(writes.length===0,'No mutation requests from guidance/FAQ/navigation');
 check(errors.length===0,'No browser runtime errors');
 if(!baseline){
  const before=JSON.parse(fs.readFileSync('proof/before-browser.json'));
  for(const old of before.rows){const now=rows.find(r=>r.language===old.language&&r.width===old.width);check(JSON.stringify(old.head)===JSON.stringify(now.head),'Canonical/Hreflang/Title/Meta/H1 unchanged '+old.language)}
  for(const lang of ['en','zh'])check(fs.readFileSync(`proof/before-iptv-${lang}.json`,'utf8')===fs.readFileSync(`proof/after-iptv-${lang}.json`,'utf8'),'Actual IPTV content unchanged '+lang);
 }
 fs.writeFileSync(`proof/${phase}-browser.json`,JSON.stringify({status:'PASS',phase,rows,write_requests:writes.length,errors,owner_visual:'PENDING_AFTER_MANUAL_UPGRADE',production:'UNTOUCHED'},null,2));
 await browser.close();console.log('FOCUSED_REAL_WORDPRESS_GUIDANCE_'+phase.toUpperCase()+'_PASS');
})().catch(e=>{fs.writeFileSync(`proof/${phase}-failure.json`,JSON.stringify({error:String(e),rows,writes,errors},null,2));console.error(e);process.exit(1)});
