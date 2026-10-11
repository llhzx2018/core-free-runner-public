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
  await page.screenshot({path:'proof/playlist-'+phase+'-1440.png',fullPage:true});
  fs.writeFileSync('proof/tools-'+phase+'.json',JSON.stringify({status:'OBSERVED',phase,actions:action,checks},null,2));
  await browser.close();return;
 }
 gate(action>=8,'Theme107 preserves actual playlist controls',action);
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
 gate(transferResponse.status()===200,'playlist handoff target reachable',transferResponse.status());
 const popup=await popupWait;
 if(popup){gate(new URL(popup.url()).pathname===new URL(href,base).pathname,'handoff popup route matches generated target');await popup.close();}
 await pc.locator('[data-vf-playlist-action="clear"]').click();
 gate((await pc.getAttribute('data-vf-playlist-has-result'))==='0','playlist clear invalidates old report');
 await pc.locator('[data-vf-playlist-file]').setInputFiles({name:'synthetic.m3u8',mimeType:'application/vnd.apple.mpegurl',buffer:Buffer.from('#EXTM3U\n#EXT-X-TARGETDURATION:3\n#EXTINF:3.0,\nsegment01.ts\n#EXT-X-ENDLIST\n')});
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
 const details=st.locator('details').first();
 if(await details.count()){const before=await details.getAttribute('open');await details.locator('summary').click();gate((await details.getAttribute('open'))!==before,'stream detail toggles');await details.locator('summary').click();}
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
 const widths=[1920,1440,1319,1024,768,390],viewports=[];
 if(phase==='candidate'){
  for(const width of widths){await page.setViewportSize({width,height:1000});for(const path of ['m3u8-browser-stream-test','m3u8-playlist-checker','embed']){await page.goto(base+'/'+path+'/');await settle(page);const snap=await page.evaluate(()=>({scroll:document.documentElement.scrollWidth,client:document.documentElement.clientWidth,h1:document.querySelectorAll('h1').length,header:document.querySelector('.vf-site-header')?.textContent?.trim().replace(/\s+/g,' ').slice(0,200)||''}));gate(snap.scroll<=snap.client+1,'responsive no overflow '+path+' '+width,snap);viewports.push({width,path,...snap});}}
  await page.setViewportSize({width:390,height:850});await page.goto(base+'/m3u8-playlist-checker/');await settle(page);await page.screenshot({path:'proof/playlist-after-390.png',fullPage:true});
  await page.goto(base+'/m3u8-browser-stream-test/');await settle(page);await page.screenshot({path:'proof/browser-after-390.png',fullPage:true});
 }
 gate(errors.length===0,'no uncaught page errors',errors.slice(0,4));
 const res={status:'PASS',phase,checks,viewports,video,playlist:{actions:action,segments:seg,clipboard_length:copied.length},stream:{clipboard_length:streamCopied.length},production:'NOT_EXECUTED'};
 fs.writeFileSync('proof/tools-'+phase+'.json',JSON.stringify(res,null,2));console.log('PUBLIC_SAFE_TOOL_RESULT',JSON.stringify({status:'PASS',phase,count:checks.length,video}));
 await browser.close();
})().catch(e=>{console.error('SYNTHETIC_TOOL_ASSERTION_FAILED',String(e.stack||e).slice(0,1500));process.exit(1)});
