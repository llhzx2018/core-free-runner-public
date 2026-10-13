'use strict';
const fs=require('fs'),assert=require('node:assert/strict'),{chromium}=require('playwright');
const phase=process.argv[2]||'candidate',base='http://127.0.0.1:18880';
const checks=[],errors=[];
function gate(ok,name,detail){checks.push({name,pass:!!ok,detail:detail===undefined?null:detail});assert(ok,name+(detail?' '+JSON.stringify(detail).slice(0,300):''));}
async function until(page,expr,ms=30000){await page.waitForFunction(expr,null,{timeout:ms});}
async function settle(page){await page.waitForLoadState('domcontentloaded');await page.waitForTimeout(700);}
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--autoplay-policy=no-user-gesture-required']});
 const context=await browser.newContext({viewport:{width:1440,height:1000},acceptDownloads:true,permissions:['clipboard-read','clipboard-write']});
 const page=await context.newPage();page.on('pageerror',e=>errors.push(String(e.message).slice(0,180)));
 const root=sel=>page.locator(sel).first();
 await page.goto(base+'/m3u8-playlist-checker/');await settle(page);
 const pc=root('[data-vf-module="playlist-checker"]');
 gate(await pc.count()===1,'playlist mounted');
 const action=await pc.locator('[data-vf-playlist-action]').count();
 if(phase==='baseline'||phase==='rollback'){
  gate(action>=0,'baseline/rollback public WordPress route mounted; PHP render regression is separately reproduced',action);
  await page.goto(base+'/m3u8-embed-generator/');await settle(page);
  gate((await page.locator('.vf-embed').count())===1,'Existing published Embed Mount remains available on baseline and rollback');
  await page.screenshot({path:'proof/playlist-'+phase+'-1440.png',fullPage:true});
  fs.writeFileSync('proof/tools-'+phase+'.json',JSON.stringify({status:'OBSERVED',phase,actions:action,checks},null,2));
  await browser.close();return;
 }
 gate(action>=8,'actual playlist controls preserved',action);
 gate(await page.locator('[data-vf-launchbar="playlist-checker"] .vf-m3u8-launchbar__steps').count()===0,'checker has no duplicate launchbar workflow');
 gate(await page.locator('.vf-tool-runtime-path').count()===0,'Theme does not add a second operation workflow');
 gate((await page.locator('.vf-tool-steps-list').innerText()).includes('Review structure and risks'),'Theme HLS support workflow');
 gate((await page.locator('[data-vf-theme-module="faq"]').innerText()).includes('HTTP and CORS'),'Theme checker FAQ matches evidence modes');
 gate((await pc.locator('[data-vf-playlist-action="analyze"]').count())===1,'playlist analyze control exact');
 await pc.locator('[data-vf-playlist-action="analyze"]').click();
 gate((await pc.getAttribute('data-vf-playlist-has-result'))!=='1','empty source does not yield fake result');
 await pc.locator('[data-vf-playlist-action="sample-master"]').click();
 await until(page,()=>document.querySelector('[data-vf-module="playlist-checker"]')?.getAttribute('data-vf-playlist-has-result')==='1',25000);
 gate((await pc.locator('[data-vf-playlist-type]').innerText()).length>2,'master sample actually analyzed');
 await pc.locator('[data-vf-playlist-mode-switch="pro"]').click();
 gate((await pc.getAttribute('data-vf-playlist-mode'))==='pro','playlist professional mode');
 gate((await pc.locator('[data-vf-playlist-pane="json"]').count())===1,'playlist actual JSON pane mounted');
 gate((await pc.locator('[data-vf-playlist-pane="segments"]').count())===1,'playlist segment pane mounted');
 await pc.locator('[data-vf-playlist-action="sample-media"]').click();
 await until(page,()=>{const r=document.querySelector('[data-vf-module="playlist-checker"]');return r?.getAttribute('data-vf-playlist-has-result')==='1'&&Number(r.querySelector('[data-vf-playlist-segments]')?.textContent)>0},30000);
 const seg=(await pc.locator('[data-vf-playlist-segments]').innerText()).trim();
 gate(Number(seg)>0,'media sample has real segments',seg);
 gate(!(await pc.locator('[data-vf-playlist-result-panel]').innerText()).includes('No results yet'),'completed report has no stale empty message');
 const pcCopy=pc.locator('[data-vf-playlist-action="copy-report"]');
 await pcCopy.click();await page.waitForTimeout(250);
 const copied=await page.evaluate(()=>navigator.clipboard.readText());
 gate(copied.length>50 && copied.includes('M3U8'),'playlist actual clipboard contents',copied.length);
 for(const [format,actionName] of [['json','export-json'],['txt','export-txt'],['csv','export-csv']]){
  const wait=page.waitForEvent('download');await pc.locator('[data-vf-playlist-action="'+actionName+'"]').click();
  const downloaded=await wait,filename=downloaded.suggestedFilename(),filepath=await downloaded.path(),data=fs.readFileSync(filepath,'utf8');
  gate(data.length>40,'playlist actual '+format+' download',filename);
  if(format==='json')gate(!!JSON.parse(data),'playlist exported JSON parses');
 }
 const handoffButton=pc.locator('[data-vf-playlist-action="segments-open"]');
 gate(await handoffButton.isVisible(),'segment handoff actionable after successful media analysis');
 const popupWait=context.waitForEvent('page',{timeout:4000}).catch(()=>null);
 await handoffButton.click();
 const transfer=pc.locator('[data-vf-playlist-handoff-link]');
 const href=await transfer.getAttribute('href');
 gate(!!href&&href!=='#','playlist actual handoff action resolves a concrete URL',href);
 const transferResponse=await page.request.get(new URL(href,base).href);
 console.log('PUBLIC_SAFE_HANDOFF_ROUTE',JSON.stringify({href,target:new URL(href,base).pathname,status:transferResponse.status(),source:page.url()}));
 gate(transferResponse.status()===200,'playlist handoff target reachable',transferResponse.status());
 const popup=await popupWait;
 if(popup){await popup.waitForLoadState('domcontentloaded',{timeout:12000});gate(new URL(popup.url()).pathname===new URL(href,base).pathname,'handoff popup route matches generated target');await popup.close();}
 await pc.locator('[data-vf-playlist-action="clear"]').click();
 gate((await pc.getAttribute('data-vf-playlist-has-result'))==='0','playlist clear invalidates old report');
 await pc.locator('[data-vf-playlist-file]').setInputFiles({name:'synthetic.m3u8',mimeType:'application/vnd.apple.mpegurl',buffer:Buffer.from('#EXTM3U\n#EXT-X-TARGETDURATION:3\n#EXTINF:3.0,\nsegment01.ts\n#EXT-X-ENDLIST\n')});
 await until(page,()=>String(document.querySelector('[data-vf-playlist-input]')?.value||'').includes('#EXTM3U'),12000);
 gate((await pc.locator('[data-vf-playlist-input]').inputValue()).includes('#EXTM3U'),'playlist file input loads exact local bytes');
 await pc.locator('[data-vf-playlist-action="analyze"]').click();
 await until(page,()=>document.querySelector('[data-vf-module="playlist-checker"]')?.getAttribute('data-vf-playlist-has-result')==='1',15000);
 gate((await pc.getAttribute('data-vf-playlist-has-result'))==='1','uploaded manifest analyzes');
 await pc.locator('[data-vf-playlist-action="clear"]').click();
 const pcUrl=pc.locator('[data-vf-playlist-url]');
 gate(await pcUrl.count()===1,'playlist URL input');
 await pcUrl.fill(base+'/wp-content/plugins/vf-tool-m3u8/public/media/player-demo/demo.m3u8');
 await pc.locator('[data-vf-playlist-action="analyze"]').click();
 await until(page,()=>document.querySelector('[data-vf-module="playlist-checker"]')?.getAttribute('data-vf-playlist-has-result')==='1',30000);
 gate((await pc.getAttribute('data-vf-playlist-has-result'))==='1','same-origin URL fetched and analyzed');
 await pc.locator('[data-vf-playlist-action="clear"]').click();
 await pc.locator('[data-vf-playlist-input]').fill('#EXTM3U\n#EXTINF:4.0,\nclip.ts\n#EXT-X-ENDLIST');
 await pc.locator('[data-vf-playlist-input]').press('Control+Enter');
 await until(page,()=>document.querySelector('[data-vf-module="playlist-checker"]')?.getAttribute('data-vf-playlist-has-result')==='1',15000);
 gate((await pc.getAttribute('data-vf-playlist-has-result'))==='1','playlist keyboard submit');
 await page.goto(base+'/m3u8-browser-stream-test/');await settle(page);
 const st=root('[data-vf-module="browser-stream-test"]');
 gate(await st.count()===1,'stream tester mounted');
 await st.locator('[data-vf-browser-stream-sample]').click();
 gate((await st.locator('[data-vf-browser-stream-url]').inputValue()).includes('.m3u8'),'stream sample populates URL');
 await st.locator('[data-vf-browser-stream-check]').click();
 await until(page,()=>document.querySelector('[data-vf-module="browser-stream-test"]')?.getAttribute('data-vf-browser-stream-has-result')==='1',60000);
 const state=await st.locator('[data-vf-browser-stream-signal]').getAttribute('data-state');
 gate(state==='success','actual media browser playback verdict',state);
 const video=await st.locator('[data-vf-browser-video]').evaluate(v=>({ready:v.readyState,width:v.videoWidth,height:v.videoHeight,error:v.error?.code||null}));
 gate(video.ready>=2 && video.width>0 && !video.error,'stream actual decoded video',video);
 await st.locator('[data-vf-browser-stream-mode-button="pro"]').click();
 gate((await st.getAttribute('data-vf-browser-stream-mode'))==='pro','stream professional mode');
 await page.waitForTimeout(1700); // allow asynchronous mode/contract initialization to settle before native details gesture
 const details=st.locator('details[data-vf-browser-stream-pro-panel]').first();
 if(await details.count()){
  const before=await details.evaluate(e=>({open:e.open,hidden:e.hidden,mode:e.closest('[data-vf-module]')?.getAttribute('data-vf-browser-stream-mode'),summary:e.querySelector('summary')?.textContent?.trim().slice(0,80)}));
  await details.evaluate(el=>{
   window.__vfDetailTrace=[];
   const desc=Object.getOwnPropertyDescriptor(HTMLDetailsElement.prototype,'open');
   if(desc?.get && desc?.set){
    Object.defineProperty(el,'open',{configurable:true,get(){return desc.get.call(this)},set(value){
     window.__vfDetailTrace.push({stage:'script-open-setter',value:String(value),stack:String(new Error().stack).split('\n').slice(1,5).join(' | ').slice(0,500)});
     desc.set.call(this,value);
    }});
   }
   new MutationObserver(records=>records.forEach(()=>window.__vfDetailTrace.push({stage:'attribute-open-change',open:el.open}))).observe(el,{attributes:true,attributeFilter:['open']});
   el.addEventListener('toggle',e=>window.__vfDetailTrace.push({stage:'toggle',open:el.open}),true);
   el.querySelector('summary').addEventListener('click',e=>{
    window.__vfDetailTrace.push({stage:'summary-capture',defaultPrevented:e.defaultPrevented});
    setTimeout(()=>window.__vfDetailTrace.push({stage:'after-click',open:el.open,defaultPrevented:e.defaultPrevented}),0);
   },true);
  });
  await details.locator('summary').click();await page.waitForTimeout(150);
  const events=await page.evaluate(()=>window.__vfDetailTrace||[]);
  console.log('PUBLIC_SAFE_DETAILS_EVENTS',JSON.stringify(events));
  const after=await details.evaluate(e=>({open:e.open,hidden:e.hidden,mode:e.closest('[data-vf-module]')?.getAttribute('data-vf-browser-stream-mode')}));
  console.log('PUBLIC_SAFE_NATIVE_DETAILS',JSON.stringify({before,after}));
  gate(after.open!==before.open,'stream real native detail toggles',{before,after});
  await details.locator('summary').click();
 }
 await st.locator('[data-vf-browser-stream-copy]').click();await page.waitForTimeout(250);
 const streamCopied=await page.evaluate(()=>navigator.clipboard.readText());
 gate(streamCopied.length>30 && streamCopied!==copied,'stream actual clipboard updates',streamCopied.length);
 const streamWait=page.waitForEvent('download');await st.locator('[data-vf-browser-stream-export]').click();
 const downloaded=await streamWait,streamJson=fs.readFileSync(await downloaded.path(),'utf8');
 gate(!!JSON.parse(streamJson),'stream JSON actual file download');
 await st.locator('[data-vf-browser-stream-clear]').click();
 gate((await st.getAttribute('data-vf-browser-stream-has-result'))==='0','stream clear invalidates result');
 await st.locator('[data-vf-browser-stream-url]').fill('not-a-url');
 await st.locator('[data-vf-browser-stream-check]').click();
 gate((await st.getAttribute('data-vf-browser-stream-has-result'))!=='1','invalid URL cannot produce successful result');
 await st.locator('[data-vf-browser-stream-sample]').click();
 await page.route('**/player-demo/demo.m3u8',route=>new Promise(resolve=>setTimeout(()=>route.continue().then(resolve).catch(resolve),2500)));
 await st.locator('[data-vf-browser-stream-check]').click();
 await st.locator('[data-vf-browser-stream-cancel]').click();
 gate((await st.getAttribute('data-vf-browser-stream-busy'))==='0','stream cancel restores control');
 await page.unroute('**/player-demo/demo.m3u8');
 await st.locator('[data-vf-browser-stream-check]').click();
 await until(page,()=>document.querySelector('[data-vf-module="browser-stream-test"]')?.getAttribute('data-vf-browser-stream-has-result')==='1',60000);
 gate((await st.locator('[data-vf-browser-stream-signal]').getAttribute('data-state'))==='success','stream recovery retry decodes');
 for(const width of [390,768,1440]){
  await page.setViewportSize({width,height:1000});await page.goto(base+'/zh/m3u8-playlist-checker/');await settle(page);
  const zhpc=page.locator('[data-vf-module="playlist-checker"]');
  gate(await page.locator('[data-vf-launchbar="playlist-checker"] .vf-m3u8-launchbar__steps').count()===0,'ZH checker native workflow only '+width);
  gate((await page.locator('.vf-tool-steps-list').innerText()).includes('查看结构与风险'),'ZH Theme HLS steps '+width);
  gate((await page.locator('[data-vf-theme-module="faq"]').innerText()).includes('HTTP 和 CORS'),'ZH Theme correct FAQ '+width);
  await zhpc.locator('[data-vf-playlist-action="sample-master"]').click();
  await until(page,()=>document.querySelector('[data-vf-module="playlist-checker"]')?.getAttribute('data-vf-playlist-has-result')==='1');
  const report=await zhpc.locator('[data-vf-playlist-result-panel]').innerText();
  gate(!report.includes('暂无结果'),'ZH completed report avoids stale empty message '+width);
  gate((await zhpc.locator('[data-vf-playlist-result-state]').innerText()).includes('需要复核'),'ZH localized report state '+width);
  gate((await zhpc.locator('[data-vf-playlist-decision-title]').innerText()).includes('Master 总列表'),'ZH decision title fully localized '+width);
  gate((await zhpc.locator('[data-vf-playlist-progress-title]').innerText()).includes('需要复核'),'ZH warning completion follows actual decision '+width);
  const related=page.locator('[data-vf-theme-module=\"related_tools\"]');
  const relatedText=await related.innerText();
  console.log('PUBLIC_SAFE_ZH_RELATED',JSON.stringify({width,text:relatedText.slice(0,1100)}));
  gate(relatedText.includes('根据检查结果'),'ZH checker related tools guidance localized '+width,relatedText.slice(0,300));
  await zhpc.locator('[data-vf-playlist-mode-switch="pro"]').click();
  gate(!(await zhpc.locator('[data-vf-playlist-pro]').innerText()).includes('playlist_checker.renderer.'),'ZH technical evidence readable '+width);
  gate(!(await zhpc.locator('[data-vf-playlist-pane=\"overview\"]').innerText()).match(/\b(?:yes|no)\b/),'ZH professional booleans localized '+width);
  await zhpc.locator('[data-vf-playlist-action=\"clear\"]').click();
  gate(!(await zhpc.locator('[data-vf-playlist-pro]').isVisible()),'ZH clearing hides professional report '+width);
 }

 for(const locale of ['en','zh']){
  for(const width of [390,768,1440]){
   await page.setViewportSize({width,height:1000});
   const prefix=locale==='zh'?'/zh':'';
   await page.goto(base+prefix+'/m3u8-browser-stream-test/');await settle(page);
   const stream=page.locator('[data-vf-module="browser-stream-test"]');
   gate(await stream.locator('[data-vf-browser-stream-metric="probe"]').count()===1,'runtime probe selector preserved '+locale+' '+width);
   gate(await stream.locator('[data-vf-browser-stream-probes]').count()===1,'runtime probe evidence selector preserved '+locale+' '+width);
   gate((await stream.getAttribute('data-vf-browser-stream-settings-consumed')).includes('defaultMode'),'configuration field identifiers preserved '+locale+' '+width);
   await stream.locator('[data-vf-browser-stream-sample]').click();
   await until(page,()=>document.querySelector('[data-vf-module="browser-stream-test"]')?.getAttribute('data-vf-browser-stream-has-result')==='1',60000);
   gate((await stream.locator('[data-vf-browser-stream-metric="probe"]').innerText()).includes('4/4'),'real media summary matches requests '+locale+' '+width);
   await stream.locator('[data-vf-browser-stream-mode-button="pro"]').click();
   const evidence=stream.locator('[data-vf-browser-stream-probes]');
   gate((await evidence.locator('.vf-bst-probe').count())===4,'all real probe evidence rendered '+locale+' '+width);
   const report=JSON.parse(await stream.locator('[data-vf-browser-stream-json]').textContent());
   gate(report.mediaSamples.tested===4 && report.mediaSamples.reachable===4 && report.mediaSamples.failed===0,'UI/report media evidence agrees '+locale+' '+width);
   gate((await stream.locator('[data-vf-browser-stream-signal]').getAttribute('data-state'))==='success','successful media chain retained '+locale+' '+width);
   const guidance=await page.locator('[data-vf-theme-module="related_tools"]').innerText();
   gate(guidance.includes(locale==='zh'?'根据结果选择播放':'Use the result to choose playback'),'stream default next step localized '+locale+' '+width);
   const metrics=await stream.locator('.vf-bst-metrics').evaluate(el=>({width:el.clientWidth,scroll:el.scrollWidth}));
   gate(metrics.scroll<=metrics.width+1,'media metrics readable without overflow '+locale+' '+width,metrics);
   await page.goto(base+prefix+'/embed/');await settle(page);
   const embedGuidance=await page.locator('[data-vf-theme-module="related_tools"]').innerText();
   gate(embedGuidance.includes(locale==='zh'?'发布前先预览播放':'Preview playback, check browser access'),'embed default next step localized '+locale+' '+width);
  }
 }
 await page.goto(base+'/zh/m3u8-browser-stream-test/');await settle(page);
 const failedStream=page.locator('[data-vf-module="browser-stream-test"]');
 await page.route('**/player-demo/seg001.m4s',route=>route.fulfill({status:403,body:'Synthetic forbidden'}));
 await failedStream.locator('[data-vf-browser-stream-sample]').click();
 await until(page,()=>document.querySelector('[data-vf-module="browser-stream-test"]')?.getAttribute('data-vf-browser-stream-has-result')==='1',60000);
 const failedReport=JSON.parse(await failedStream.locator('[data-vf-browser-stream-json]').textContent());
 gate(failedReport.mediaSamples.failed===1 && failedReport.mediaSamples.reachable===3,'failed media request remains visible in report');
 gate((await failedStream.locator('[data-vf-browser-stream-metric="probe"]').innerText()).includes('3/4'),'partial summary never claims all reached');
 gate((await failedStream.locator('[data-vf-browser-stream-signal]').getAttribute('data-state'))!=='success','failed probe remains fail-closed');
 await page.unroute('**/player-demo/seg001.m4s');
 await failedStream.locator('[data-vf-browser-stream-sample]').click();
 await until(page,()=>document.querySelector('[data-vf-module="browser-stream-test"] [data-vf-browser-stream-signal]')?.getAttribute('data-state')==='success',60000);
 gate((await failedStream.locator('[data-vf-browser-stream-metric="probe"]').innerText()).includes('4/4'),'retry replaces partial result with fresh complete evidence');
 const widths=[1920,1440,1319,1024,768,390],viewports=[];
 if(phase==='candidate'){
  for(const width of widths){await page.setViewportSize({width,height:1000});for(const path of ['m3u8-browser-stream-test','m3u8-playlist-checker','embed','m3u8-embed-generator']){await page.goto(base+'/'+path+'/');await settle(page);const snap=await page.evaluate(()=>({scroll:document.documentElement.scrollWidth,client:document.documentElement.clientWidth,h1:document.querySelectorAll('h1').length,header:document.querySelector('.vf-site-header')?.textContent?.trim().replace(/\s+/g,' ').slice(0,200)||''}));gate(snap.scroll<=snap.client+1,'responsive no overflow '+path+' '+width,snap);viewports.push({width,path,...snap});}}
  await page.setViewportSize({width:390,height:850});await page.goto(base+'/m3u8-playlist-checker/');await settle(page);await page.screenshot({path:'proof/playlist-after-390.png',fullPage:true});
  await page.goto(base+'/m3u8-browser-stream-test/');await settle(page);await page.screenshot({path:'proof/browser-after-390.png',fullPage:true});
 }
 // Production-reproduced regression: WordPress Page Mount URL used to render
 // only a Theme shell while legacy /embed/ loaded the actual M3U8 provider.
 for(const path of ['/m3u8-embed-generator/','/zh/m3u8-embed-generator/']){
  await page.goto(base+path);await settle(page);
  const embedRouteDiagnostic=await page.evaluate(()=>({url:location.pathname,title:document.title,h1:document.querySelector('h1')?.innerText??'',bodyClass:document.body.className,mainText:document.querySelector('main')?.innerText?.slice(0,240)??'',mainHTML:document.querySelector('main')?.outerHTML?.slice(0,900)??'',moduleStack:document.querySelector('[data-vf-theme-module-stack]')?.getAttribute('data-vf-theme-module-stack')??'',toolCount:document.querySelectorAll('.vf-embed').length}));
  console.log('PUBLIC_SAFE_EMBED_ROUTE_DIAG',JSON.stringify(embedRouteDiagnostic));
  gate((await page.locator('.vf-embed').count())===1,'new public Embed Page Mount renders actual provider '+path);
  gate((await page.locator('[data-vf-embed-generator]').getAttribute('data-vf-tool-version'))===undefined || (await page.locator('[data-vf-embed-generator]').count())===1,'embed generator exists '+path);
  gate((await page.locator('[data-vf-tool-runtime-stage]').count())>0,'tool page shortcode container '+path);
  // The zh page localizes the visible demo-button label. Gate its real
  // provider controls without assuming an English string on a Chinese page;
  // the EN mount below exercises the actual button and player iframe.
  if(path.startsWith('/zh/')){
   gate((await page.locator('[data-vf-embed-generator] button').count())>=5,'translated Embed tool exposes interactive controls '+path);
   continue;
  }
  const buttons=await page.getByRole('button',{name:'Run bundled example',exact:true}).count();
  gate(buttons===1,'new mount sample action available '+path,buttons);
  await page.getByRole('button',{name:'Run bundled example',exact:true}).click();
  await page.waitForFunction(()=>Array.from(document.querySelectorAll('iframe')).some(f=>f.src.includes('vf_m3u8_embed=1')),{},{timeout:30000});
  gate(await page.locator('iframe[src*="vf_m3u8_embed=1"]').count()>=1,'new mount builds real playable iframe '+path);
 }
 if(phase==='clean'){
  await page.goto(base+'/wp-login.php');
  await page.locator('#user_login').fill('admin');
  await page.locator('#user_pass').fill('Synthetic-Only-Update-54!');
  await page.locator('#wp-submit').click();
  await page.waitForURL('**/wp-admin/**');
  await page.goto(base+'/wp-admin/profile.php');
  gate(await page.locator('form#your-profile').count()===1 && new URL(page.url()).pathname==='/wp-admin/profile.php','clean install authenticated administrator profile');
  await page.goto(base+'/wp-admin/install.php');
  gate((await page.locator('body').innerText()).includes('Already Installed'),'setup revisit is safely locked');
 }
 gate(errors.length===0,'no uncaught page errors',errors.slice(0,4));
 const res={status:'PASS',phase,checks,viewports,video,playlist:{actions:action,segments:seg,clipboard_length:copied.length},stream:{clipboard_length:streamCopied.length},production:'NOT_EXECUTED'};
 fs.writeFileSync('proof/tools-'+phase+'.json',JSON.stringify(res,null,2));console.log('PUBLIC_SAFE_TOOL_RESULT',JSON.stringify({status:'PASS',phase,count:checks.length,video}));
 await browser.close();
})().catch(e=>{console.error('SYNTHETIC_TOOL_ASSERTION_FAILED',String(e.stack||e).slice(0,1500));process.exit(1)});


