const {chromium}=require('playwright');
const fs=require('fs');
const origin='http://127.0.0.1:18880';
const baseline=process.argv.includes('--baseline'),phase=baseline?'before':'after';
const assert=(ok,msg)=>{if(!ok)throw new Error(msg)};
(async()=>{
 const browser=await chromium.launch(),context=await browser.newContext({viewport:{width:1440,height:1000}}),page=await context.newPage();
 const rows=[],errors=[],writes=[];
 page.on('pageerror',e=>errors.push(String(e)));
 page.on('request',r=>{if(r.url().startsWith(origin+'/wp-')&&!['GET','HEAD','OPTIONS'].includes(r.method()))writes.push({method:r.method(),url:r.url().split('?')[0]})});
 for(const route of ['m3u8-test-links','m3u8-browser-stream-test','m3u8-player'])for(const language of ['en','zh']){
  const path=(language==='zh'?'/zh/':'/')+route+'/';
  const response=await page.goto(origin+path,{waitUntil:'domcontentloaded'});assert(response.status()===200,'Public route not200 '+path);await page.waitForTimeout(350);
  const head=await page.evaluate(()=>({title:document.title,h1:[...document.querySelectorAll('h1')].map(x=>x.textContent.trim()),canonical:[...document.querySelectorAll('head link[rel=canonical]')].map(x=>x.href),hreflang:Object.fromEntries([...document.querySelectorAll('head link[hreflang]')].map(x=>[x.hreflang,x.href])),robots:[...document.querySelectorAll('meta[name=robots]')].map(x=>x.content),description:[...document.querySelectorAll('meta[name=description]')].map(x=>x.content)}));
  assert(head.canonical.length===1&&head.canonical[0]===origin+path,'Unique exact canonical '+path);assert(head.h1.length===1,'One H1 '+path);
  if(baseline&&language==='en'&&route!=='m3u8-player')assert(Object.keys(head.hreflang).length===0,'Old actual WordPress missing hreflang not reproduced '+path);
  if(!baseline||route==='m3u8-player')assert(head.hreflang.en===origin+'/'+route+'/'&&head.hreflang.zh===origin+'/zh/'+route+'/','Actual paired head missing '+path);
  rows.push({route,language,path,head,status:'PASS'});
 }
 if(!baseline){
  const old=JSON.parse(fs.readFileSync('proof/before-head.json'));
  for(const row of rows){const prev=old.rows.find(r=>r.route===row.route&&r.language===row.language);for(const key of ['title','h1','canonical','robots','description'])assert(JSON.stringify(row.head[key])===JSON.stringify(prev.head[key]),'Unrelated SEO metadata changed '+row.path+' '+key);if(row.route==='m3u8-player')assert(JSON.stringify(row.head)===JSON.stringify(prev.head),'Control player head changed '+row.language)}
  for(const route of ['m3u8-test-links','m3u8-browser-stream-test']){const response=await page.goto(origin+'/'+route+'/?preview=true',{waitUntil:'domcontentloaded'});const state=await page.evaluate(()=>({count:document.querySelectorAll('head link[hreflang]').length,robots:[...document.querySelectorAll('meta[name=robots]')].map(x=>x.content).join(',')}));assert(state.count===0&&(/noindex/.test(state.robots)||response.status()>=400),'Real preview exclusion failed '+route);}
 }
 assert(errors.length===0,'Browser runtime errors '+errors.join(';'));assert(writes.length===0,'Unexpected WordPress write request');
 fs.writeFileSync('proof/'+phase+'-head.json',JSON.stringify({status:'PASS',phase,rows,errors,wordpress_write_requests:writes,production:'UNTOUCHED'},null,2));
 await browser.close();console.log(baseline?'REPRODUCED_TWO_ENGLISH_PUBLIC_TEST_HEADS_MISSING_PASS':'REAL_WORDPRESS_BILINGUAL_PUBLIC_HEAD_AND_PREVIEW_EXCLUSION_PASS');
})().catch(e=>{console.error(e);process.exit(1)});
