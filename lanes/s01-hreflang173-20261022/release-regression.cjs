const {chromium}=require('playwright');
const fs=require('fs');
const origin='http://127.0.0.1:18880';
const phase=(process.argv.find(x=>x.startsWith('--phase='))||'--phase=after').split('=')[1];
const candidate=['upgrade','after'].includes(phase);
const reference='public-stream-test-reference';
const tools=['m3u8-test-links','m3u8-browser-stream-test','m3u8-player'];
const assert=(ok,msg)=>{if(!ok)throw new Error(msg)};
(async()=>{
 const browser=await chromium.launch(),context=await browser.newContext({viewport:{width:1440,height:1000}}),page=await context.newPage();
 const rows=[],errors=[],writes=[],negative=[];
 const fixture=JSON.parse(fs.readFileSync('proof/head-fixtures.json')).canonical_pairs;
 page.on('pageerror',e=>errors.push(String(e)));
 page.on('request',r=>{if(r.url().startsWith(origin+'/wp-')&&!['GET','HEAD','OPTIONS'].includes(r.method()))writes.push({method:r.method(),url:r.url().split('?')[0]})});
 for(const route of [...tools,reference])for(const language of ['en','zh']){
  const path=(language==='zh'?'/zh/':'/')+route+'/';
  const response=await page.goto(origin+path,{waitUntil:'domcontentloaded'});assert(response.status()===200,'Public route not200 '+path);await page.waitForTimeout(250);
  const observed=await page.evaluate(()=>({htmlLang:document.documentElement.lang,bodyClass:document.body.className,title:document.title,h1:[...document.querySelectorAll('h1')].map(x=>x.textContent.trim()),canonical:[...document.querySelectorAll('head link[rel=canonical]')].map(x=>x.href),hreflang:[...document.querySelectorAll('head link[hreflang]')].map(x=>({code:x.hreflang,href:x.href})),robots:[...document.querySelectorAll('meta[name=robots]')].map(x=>x.content),description:[...document.querySelectorAll('meta[name=description]')].map(x=>x.content)}));
  fs.writeFileSync('proof/'+phase+'-observed.json',JSON.stringify({phase,rows:[...rows,{route,language,path,observed,expected_post_id:fixture[route][language]}]},null,2));
  const actualId=Number((observed.bodyClass.match(/(?:^| )page-id-(\d+)(?: |$)/)||[])[1]||0);
  assert(actualId===fixture[route][language],'Wrong native language object '+path+' expected '+fixture[route][language]+' actual '+actualId);
  assert(observed.htmlLang.toLowerCase().startsWith(language),'HTML language mismatch '+path);
  assert(observed.canonical.length===1&&observed.canonical[0]===origin+path,'Unique exact canonical '+path);
  assert(observed.h1.length===1,'One H1 '+path);
  const map=Object.fromEntries(observed.hreflang.map(x=>[x.code,x.href]));
  if(route===reference&&!candidate)assert(observed.hreflang.length===0,'Published page false-preview bug not reproduced '+path);
  else assert(observed.hreflang.length===2&&map.en===origin+'/'+route+'/'&&map.zh===origin+'/zh/'+route+'/','Exact reciprocal head missing '+path);
  const {bodyClass,...head}=observed;
  rows.push({route,language,path,post_id:actualId,head,status:'PASS'});
 }
 if(phase!=='before'){
  const old=JSON.parse(fs.readFileSync('proof/before-head.json'));
  for(const row of rows){const prev=old.rows.find(r=>r.route===row.route&&r.language===row.language);for(const key of ['title','h1','canonical','robots','description','htmlLang'])assert(JSON.stringify(row.head[key])===JSON.stringify(prev.head[key]),'Unrelated metadata changed '+row.path+' '+key);if(tools.includes(row.route))assert(JSON.stringify(row.head)===JSON.stringify(prev.head),'Existing tool head changed '+row.path)}
 }
 if(phase==='after'){
  for(const route of [...tools.slice(0,2),reference]){
   const response=await page.goto(origin+'/'+route+'/?preview=true',{waitUntil:'domcontentloaded'});
   const state=await page.evaluate(()=>({count:document.querySelectorAll('head link[hreflang]').length,robots:[...document.querySelectorAll('meta[name=robots]')].map(x=>x.content).join(',')}));
   assert(state.count===0&&(/noindex/.test(state.robots)||response.status()>=400),'Real preview exclusion failed '+route);negative.push({kind:'preview',route,...state,status:response.status()});
  }
  const response=await page.goto(origin+'/unpublished-test-reference/',{waitUntil:'domcontentloaded'});
  const state=await page.evaluate(()=>({count:document.querySelectorAll('head link[hreflang]').length,body:document.body.innerText}));
  assert(response.status()===404&&state.count===0&&!state.body.includes('This draft must not become public.'),'Draft target leaked public content or hreflang');negative.push({kind:'unpublished',status:response.status(),count:state.count});
 }
 assert(errors.length===0,'Browser runtime errors '+errors.join(';'));assert(writes.length===0,'Unexpected WordPress write request');
 fs.writeFileSync('proof/'+phase+'-head.json',JSON.stringify({status:'PASS',phase,rows,negative,errors,wordpress_write_requests:writes,production:'UNTOUCHED',production_tool_trigger:'UNPROVEN_POST_MANUAL_UPGRADE_READBACK_REQUIRED'},null,2));
 await browser.close();console.log(candidate?'REAL_WORDPRESS_PUBLIC_PAGE_CORRECTION_TOOL_HEAD_REGRESSION_PASS':'REAL_WORDPRESS_PUBLISHED_PAGE_FALSE_PREVIEW_REPRODUCED_PASS');
 console.log('NATIVE_HEAD_PHASE_PASS='+phase);
})().catch(e=>{console.error(e);process.exit(1)});
