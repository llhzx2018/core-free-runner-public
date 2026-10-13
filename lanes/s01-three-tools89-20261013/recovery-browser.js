'use strict';
// Synthetic isolated WordPress only. Tests actual controls and real clipboard/download bytes.
const fs=require('node:fs'),assert=require('node:assert/strict'),{chromium}=require('playwright');
const base='http://127.0.0.1:18880',cases=[];
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--autoplay-policy=no-user-gesture-required']});
 try{for(const locale of ['en','zh'])for(const width of [390,1440])for(const tool of ['browser-stream-test','playlist-checker','embed']){
  const context=await browser.newContext({viewport:{width,height:1000},acceptDownloads:true,permissions:['clipboard-read','clipboard-write']});const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  const path=tool==='embed'?'/embed/':'/m3u8-'+tool+'/',prefix=locale==='zh'?'/zh':'';
  await page.goto(base+prefix+path);await page.waitForTimeout(700);
  const root=page.locator(tool==='embed'?'[data-vf-embed-generator]':'[data-vf-module="'+tool+'"]');
  const sample=tool==='embed'?'[data-vf-embed-sample]':tool==='playlist-checker'?'[data-vf-playlist-action="sample-media"]':'[data-vf-browser-stream-sample]';
  await root.locator(sample).click();
  const result=tool==='embed'?'[data-vf-embed-result-shell]':tool==='playlist-checker'?'[data-vf-playlist-result-panel]':'[data-vf-browser-stream-result-shell]';
  await root.locator(result).waitFor({state:'visible',timeout:60000});
  if(tool==='embed')await page.waitForFunction(()=>document.querySelector('[data-vf-embed-generator]')?.getAttribute('data-vf-embed-preview-state')==='success',null,{timeout:60000});
  const copy=tool==='embed'?'[data-vf-embed-copy-recommended]':tool==='playlist-checker'?'[data-vf-playlist-action="copy-report"]':'[data-vf-browser-stream-copy]';
  const exp=tool==='embed'?'[data-vf-embed-export]':tool==='playlist-checker'?'[data-vf-playlist-action="export-json"]':'[data-vf-browser-stream-export]';
  const status=tool==='embed'?'[data-vf-embed-status]':tool==='playlist-checker'?'[data-vf-playlist-status]':'[data-vf-browser-stream-status]';
  if(tool==='embed')await root.locator('[data-vf-embed-mode-button="pro"]').click();
  await page.evaluate(()=>{window.__recoveryCopy=navigator.clipboard.writeText.bind(navigator.clipboard);window.__recoveryExec=document.execCommand.bind(document);window.__recoveryURL=URL.createObjectURL.bind(URL);Object.defineProperty(navigator.clipboard,'writeText',{configurable:true,value:()=>Promise.reject(new DOMException('Synthetic denial','NotAllowedError'))});document.execCommand=()=>false;});
  await root.locator(copy).first().click();await page.waitForTimeout(100);
  assert.equal(await root.locator(status).getAttribute('data-state'),'error','denial never announces success');
  assert(await root.locator(result).isVisible(),'report retained after denial');
  assert.equal(await page.locator('body > textarea').count(),0,'fallback textarea removed');
  await page.evaluate(()=>{document.execCommand=()=>{throw Error('Synthetic copy throw');};});await root.locator(copy).first().click();await page.waitForTimeout(100);
  assert.equal(await root.locator(status).getAttribute('data-state'),'error');
  await page.evaluate(()=>{Object.defineProperty(navigator.clipboard,'writeText',{configurable:true,value:window.__recoveryCopy});document.execCommand=window.__recoveryExec;});
  await root.locator(copy).first().click();await page.waitForTimeout(200);
  const text=await page.evaluate(()=>navigator.clipboard.readText());assert(text.length>50,'actual clipboard bytes');
  assert.equal(await root.locator(status).getAttribute('data-state'),'success','copy retry succeeds');
  await page.evaluate(()=>{URL.createObjectURL=()=>{throw Error('Synthetic object URL denial');};});
  await root.locator(exp).first().click();assert.equal(await root.locator(status).getAttribute('data-state'),'error');assert(await root.locator(result).isVisible());
  await page.evaluate(()=>{URL.createObjectURL=window.__recoveryURL;});
  const wait=page.waitForEvent('download');await root.locator(exp).first().click();const download=await wait;const bytes=fs.readFileSync(await download.path(),'utf8');const report=JSON.parse(bytes);assert(report&&bytes.length>50);
  if(tool==='browser-stream-test')assert.equal(report.mediaSamples.reachable,4);if(tool==='playlist-checker')assert.equal(report.summary.segmentCount,3);if(tool==='embed')assert(report.embed.responsive.includes('<iframe'));
  // Clipboard completion after clear must preserve the newer cleared state.
  await page.evaluate(()=>{Object.defineProperty(navigator.clipboard,'writeText',{configurable:true,value:()=>new Promise(resolve=>{window.__lateCopyResolve=resolve;})});});
  await root.locator(copy).first().click();
  const clear=tool==='embed'?'[data-vf-embed-clear]':tool==='playlist-checker'?'[data-vf-playlist-action="clear"]':'[data-vf-browser-stream-clear]';await root.locator(clear).first().click();
  const before=await root.locator(status).textContent(),beforeState=await root.locator(status).getAttribute('data-state');
  await page.evaluate(()=>window.__lateCopyResolve());await page.waitForTimeout(100);
  assert.equal(await root.locator(status).textContent(),before);assert.equal(await root.locator(status).getAttribute('data-state'),beforeState);assert.equal(await root.locator(result).isVisible(),false);
  const overflow=await root.evaluate(el=>el.scrollWidth>el.clientWidth+1);assert.equal(overflow,false,'390/1440 tool overflow');assert.deepEqual(errors,[],'no uncaught errors');
  cases.push({locale,width,tool,clipboard_denial:'PASS',clipboard_fallback_throw:'PASS',clipboard_bytes:'PASS',download_denial:'PASS',download_json_retry:'PASS',late_copy_after_clear:'PASS',report_retained:'PASS',overflow:'PASS',uncaught_errors:'PASS'});await context.close();
 }}finally{await browser.close();}
 fs.writeFileSync('proof/three-tool-recovery-browser.json',JSON.stringify({status:'PASS',cases,production:'NOT_EXECUTED'},null,2));console.log('PUBLIC_SAFE_THREE_TOOL_RECOVERY',JSON.stringify({status:'PASS',cases:cases.length}));
})().catch(e=>{console.error('SYNTHETIC_RECOVERY_FAILED',String(e.stack||e).slice(0,1800));process.exitCode=1;});
