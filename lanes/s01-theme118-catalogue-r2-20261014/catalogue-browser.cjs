'use strict';
const fs=require('fs'),assert=require('node:assert/strict'),{chromium}=require('playwright');
const phase=process.argv[2],candidate=!['baseline','rollback'].includes(phase),base='http://127.0.0.1:18880',checks=[],rows=[],reading=[];
function gate(ok,label,detail){checks.push({label,pass:!!ok,detail});assert(ok,label+' '+JSON.stringify(detail));}
(async()=>{const browser=await chromium.launch({headless:true}),page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
 for(const locale of ['en','zh'])for(const width of [1024,1280,1440,1920]){
  await page.setViewportSize({width,height:1000});await page.goto(base+(locale==='zh'?'/zh':'')+'/tools/');await page.waitForLoadState('networkidle');
  const cards=page.locator('[data-vf-directory-item]');gate(await cards.count()===11,'actual runtime-gated tool pool',{locale,width});
  gate(await page.locator('#content h1').count()===1,'one directory H1');
  const data=await page.evaluate(()=>({overflow:document.documentElement.scrollWidth>innerWidth+1,cards:[...document.querySelectorAll('[data-vf-directory-item]')].map(e=>({tag:e.tagName,route:e.dataset.vfDirectoryRoute,title:e.querySelector('h4').textContent,details:e.querySelectorAll('details').length,open:e.querySelector('details')?.open,summaryFont:e.querySelector('summary')?getComputedStyle(e.querySelector('summary')).fontSize:null,action:e.querySelector('.vf-directory-card-action')?.tagName,actionHeight:e.querySelector('.vf-directory-card-action')?.getBoundingClientRect().height,href:e.querySelector('a')?.getAttribute('href')||e.getAttribute('href'),nested:e.querySelector('a details,a summary')!==null}))}));
  gate(!data.overflow,'directory no horizontal overflow',{locale,width});
  if(candidate){
   gate(data.cards.every(c=>c.tag==='ARTICLE'&&c.details===1&&!c.open&&c.action==='A'&&!c.nested&&c.actionHeight>=44),'valid compact cards and one accessible primary link',data.cards);
   if(locale==='zh'){const titles=Object.fromEntries(data.cards.map(c=>[c.route,c.title]));gate(titles['m3u8-playlist-checker']==='播放列表检查器'&&titles['m3u8-browser-stream-test']==='浏览器流测试'&&titles['m3u8-backup-restore']==='备份与恢复','default Chinese labels',titles);}
   const card=page.locator('[data-vf-directory-route="m3u8-playlist-checker"]'),summary=card.locator('summary');await summary.focus();await page.keyboard.press('Enter');
   gate(await card.locator('details').getAttribute('open')!==null,'keyboard opens native details');
   gate(await card.locator('.vf-directory-card-route').isVisible()&&await card.locator('.vf-directory-card-limit').isVisible(),'input/result/limit discoverable');
   await page.keyboard.press('Enter');gate(await card.locator('details').getAttribute('open')===null,'keyboard closes native details');
   const href=await card.locator('.vf-directory-card-action').getAttribute('href');const response=await page.request.get(new URL(href,base).href);gate(response.status()===200,'primary tool route reachable');
  }else gate(data.cards.every(c=>c.tag==='A'&&c.details===0),'actual117 card baseline observed');
  const search=page.locator('[data-vf-directory-query]');await search.fill('Browser Stream Test');await page.waitForFunction(()=>document.querySelector('[data-vf-directory-count]')?.textContent.trim()==='1');gate(await page.locator('[data-vf-directory-item]:visible').count()===1,'original English alias search works');
  if(candidate&&locale==='zh'){await search.fill('播放列表检查器');await page.waitForFunction(()=>document.querySelector('[data-vf-directory-count]')?.textContent.trim()==='1');gate(await page.locator('[data-vf-directory-item]:visible').count()===1,'Chinese search works');}
  await search.fill('vf-no-result-123');await page.waitForFunction(()=>document.querySelector('[data-vf-directory-count]')?.textContent.trim()==='0');gate(await page.locator('[data-vf-directory-empty]').isVisible(),'honest no results');
  await page.locator('[data-vf-directory-reset]').click();await page.waitForLoadState('domcontentloaded');gate(await page.locator('[data-vf-directory-item]:visible').count()===11,'reset restores whole pool');
  await page.locator('[data-vf-directory-filter-button="inspect"]').click();await page.waitForLoadState('domcontentloaded');gate(await page.locator('[data-vf-directory-item]:visible').count()===4,'actual category filter');
  await page.locator('[data-vf-directory-reset]').click();await page.waitForLoadState('domcontentloaded');
  rows.push({locale,width,...data});if(candidate&&width===1440)await page.screenshot({path:'proof/catalogue-'+locale+'.png',fullPage:true});
 }
 for(const locale of ['en','zh'])for(const readingWidth of ['focused','balanced','relaxed']){
  await page.setViewportSize({width:1440,height:1000});await page.goto(base+(locale==='zh'?'/zh':'')+'/guides/s01-reading-fixture/?vf_reading_fixture=guide_detail&reading_width='+readingWidth);await page.waitForLoadState('networkidle');
  const value=await page.evaluate(()=>{const a=document.querySelector('#vf-reading-content'),r=a.getBoundingClientRect();return {text:a.textContent.trim(),width:r.width,font:getComputedStyle(a).fontSize,line:getComputedStyle(a).lineHeight,h1:document.querySelectorAll('#content h1').length,summary:document.querySelector('.vf-article-hero-description')?.textContent.trim(),index:document.querySelectorAll('[data-vf-reading-section-index] a').length,overflow:document.documentElement.scrollWidth>innerWidth+1};});
  gate(value.h1===1&&value.index===4&&value.font==='18px'&&value.line==='32.4px'&&!value.overflow,'reading template retained',value);
  if(candidate)gate(!/blueprint|蓝图|SEO/.test(value.summary)&&value.summary.length>20,'reader-facing summary replaces implementation copy',value.summary);
  const chapter=page.locator('[data-vf-reading-section-index] a').nth(1);await chapter.focus();await page.keyboard.press('Enter');await page.waitForFunction(()=>{const e=document.getElementById(location.hash.slice(1));return e&&document.activeElement===e&&e.getBoundingClientRect().top>=0&&e.getBoundingClientRect().top<210;});
  gate(true,'chapter keyboard jump and focused target after smooth scroll');reading.push({locale,readingWidth,...value});if(candidate&&readingWidth==='focused')await page.screenshot({path:'proof/guide-'+locale+'.png',fullPage:true});
 }
 if(candidate&&phase!=='clean'){const before=JSON.parse(fs.readFileSync('proof/catalogue-baseline.json')).reading;gate(reading.every((r,i)=>r.text===before[i].text&&r.width===before[i].width),'body and saved reading widths retained');}
 for(const locale of ['en','zh']){await page.goto(base+(locale==='zh'?'/zh/':'/'));await page.waitForLoadState('domcontentloaded');gate(await page.locator('#content h1').count()===1,'native homepage title retained');gate(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'native homepage no overflow');}
 if(phase==='clean'){
  await page.goto(base+'/wp-login.php');await page.locator('#user_login').fill('admin');await page.locator('#user_pass').fill('Synthetic-Only-Update-54!');await page.locator('#wp-submit').click();await page.waitForURL('**/wp-admin/**');await page.goto(base+'/wp-admin/profile.php');gate(await page.locator('form#your-profile').count()===1,'clean authenticated administrator profile');await page.goto(base+'/wp-admin/install.php');gate((await page.locator('body').innerText()).includes('Already Installed'),'setup revisit safely locked');
 }
 gate(errors.length===0,'no uncaught browser errors',errors);fs.writeFileSync('proof/catalogue-'+phase+'.json',JSON.stringify({status:'PASS',phase,rows,reading,checks,mobile:'NOT_RUN_OWNER_DEFERRED',production:'NOT_EXECUTED'},null,2));await browser.close();
})().catch(e=>{fs.writeFileSync('proof/catalogue-'+phase+'-failure.json',JSON.stringify({status:'FAIL',error:e.message,rows,reading,checks},null,2));console.error(e);process.exit(1);});
