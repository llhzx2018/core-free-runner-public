'use strict';
const {chromium}=require('playwright'),fs=require('node:fs'),assert=require('node:assert/strict');
const base='http://127.0.0.1:18880',checks=[],errors=[];
function gate(value,name,detail){checks.push({name,pass:!!value,detail:detail??null});assert(value,name+(detail==null?'':': '+JSON.stringify(detail).slice(0,180)));}
async function waitResult(page){await page.waitForFunction(()=>{const r=document.querySelector('[data-vf-module="playlist-checker"]');return r?.getAttribute('data-vf-playlist-has-result')==='1'&&r?.getAttribute('data-vf-playlist-busy')!=='1'},null,{timeout:40000});}
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--autoplay-policy=no-user-gesture-required']});
 try{
  const ctx=await browser.newContext({viewport:{width:1440,height:900},acceptDownloads:true,permissions:['clipboard-read','clipboard-write']});
  const page=await ctx.newPage();page.on('pageerror',e=>errors.push(String(e.message).slice(0,140)));
  const resp=await page.goto(base+'/m3u8-playlist-checker/',{waitUntil:'domcontentloaded'});
  gate(resp?.status()===200,'real WordPress published page HTTP 200',resp?.status());
  const root=page.locator('[data-vf-module="playlist-checker"]').first();
  gate(await root.count()===1,'playlist checker shortcode mounted once');
  await page.waitForFunction(()=>!!document.querySelector('[data-vf-module="playlist-checker"]')?.getAttribute('data-vf-playlist-checker-ready'),null,{timeout:15000});
  gate((await root.getAttribute('data-vf-tool-version'))==='1.25.81','plugin version appears in actual UI');
  gate(await root.locator('[data-vf-playlist-action="analyze"]').count()===1,'analyze control present');
  await root.locator('[data-vf-playlist-action="analyze"]').click();
  gate((await root.getAttribute('data-vf-playlist-has-result'))!=='1','empty source does not fake a report');
  await root.locator('[data-vf-playlist-action="sample-master"]').click();await waitResult(page);
  gate((await root.locator('[data-vf-playlist-type]').innerText()).trim().length>2,'sample master parsed');
  await root.locator('[data-vf-playlist-mode-switch="pro"]').click();
  gate((await root.getAttribute('data-vf-playlist-mode'))==='pro','professional mode switches');
  const privateToken='PRIVATE_TEST_ONLY_12581';
  const signed='https://media.example/master.m3u8?auth='+privateToken;
  const manifest='#EXTM3U\n#EXT-X-TARGETDURATION:3\n#EXT-X-KEY:METHOD=AES-128,URI="https://media.example/key.bin?auth='+privateToken+'"\n#EXTINF:3,\nsegment.ts?token='+privateToken+'\n#EXT-X-ENDLIST';
  await root.locator('[data-vf-playlist-url]').fill(signed);
  await root.locator('[data-vf-playlist-input]').fill(manifest);
  await root.locator('[data-vf-playlist-action="analyze"]').click();await waitResult(page);
  const parsed=await page.evaluate(args=>{
    const lab=window.VFM3U8PlaylistCheckerLab,root=document.querySelector('[data-vf-module="playlist-checker"]');
    const m='#EXTM3U\n#EXT-X-TARGETDURATION:3\n#EXTINF:3,\n//foreign.example/part.ts\n#EXT-X-ENDLIST';
    const output=lab.parse(m,{sourceUrl:args.signed},root);
    const same=lab.parse(m.replace('//foreign.example/part.ts','part.ts'),{sourceUrl:args.signed},root);
    const current=root._vfPlaylistResult,exported=lab.exportPayload(current);
    return {cross:output.segments[0].url,same:same.segments[0].url,exported:JSON.stringify(exported),real:current.segments[0].url};
  },{signed});
  gate(!parsed.cross.includes(privateToken),'cross-origin segment must not inherit source token');
  gate(parsed.same.includes(privateToken),'same-origin segment retains token for authorized fetch');
  gate(!parsed.exported.includes(privateToken),'JSON API report redacts all signed inputs');
  gate(parsed.real.includes(privateToken),'live result keeps exact signed URL for tool handoff');
  await root.locator('[data-vf-playlist-action="copy-report"]').click();
  const copy=await page.evaluate(()=>navigator.clipboard.readText());
  gate(copy.length>70&&!copy.includes(privateToken),'actual clipboard excludes private token');
  for(const [kind,action] of [['json','export-json'],['txt','export-txt'],['csv','export-csv']]){
    const d=page.waitForEvent('download',{timeout:10000});
    await root.locator('[data-vf-playlist-action="'+action+'"]').click();
    const file=await d,bytes=fs.readFileSync(await file.path(),'utf8');
    gate(bytes.length>50&&!bytes.includes(privateToken),'actual '+kind+' download excludes token',{len:bytes.length,name:file.suggestedFilename()});
    if(kind==='json'){const report=JSON.parse(bytes);gate(report.schemaVersion==='1.0.0'&&!('rawPreview' in report),'JSON contains structured safe report');}
  }
  await root.locator('[data-vf-playlist-action="clear"]').click();
  gate((await root.getAttribute('data-vf-playlist-has-result'))!=='1','clear invalidates result');
  await root.locator('[data-vf-playlist-action="sample-media"]').click();await waitResult(page);
  const segments=Number((await root.locator('[data-vf-playlist-segments]').innerText()).trim());
  gate(segments>0,'actual bundled media sample parsed with segments',segments);
  await root.locator('[data-vf-playlist-action="clear"]').click();
  await root.locator('[data-vf-playlist-file]').setInputFiles({name:'synthetic.m3u8',mimeType:'application/vnd.apple.mpegurl',buffer:Buffer.from('#EXTM3U\n#EXTINF:3,\nseg.ts\n#EXT-X-ENDLIST\n')});
  await page.waitForFunction(()=>String(document.querySelector('[data-vf-playlist-input]')?.value||'').includes('#EXTM3U'),null,{timeout:12000});
  await root.locator('[data-vf-playlist-action="analyze"]').click();await waitResult(page);
  gate((await root.getAttribute('data-vf-playlist-has-result'))==='1','uploaded manifest analyzes');
  const desktopModes=await root.locator('[data-vf-playlist-mode-switch]').evaluateAll(buttons=>buttons.filter(b=>!b.hidden).map(b=>b.getBoundingClientRect().height));
  gate(desktopModes.length>=2&&desktopModes.every(n=>n>=44),'desktop display-mode buttons have at least 44px touch height',desktopModes);
  await page.setViewportSize({width:768,height:900});await page.waitForTimeout(120);
  const tablet=await root.evaluate(()=>({scroll:document.documentElement.scrollWidth,viewport:innerWidth}));
  gate(tablet.scroll<=tablet.viewport+2,'768px tablet has no horizontal overflow',tablet);
  await page.setViewportSize({width:390,height:844});await page.waitForTimeout(300);
  const mobile=await root.evaluate(el=>({font:parseFloat(getComputedStyle(el.querySelector('.vf-pc-shell')).fontSize),touch:el.querySelector('[data-vf-playlist-action="analyze"]').getBoundingClientRect().height,scroll:document.documentElement.scrollWidth,viewport:window.innerWidth}));
  gate(mobile.font>=15,'mobile tool content font at least 15px',mobile);
  gate(mobile.touch>=44,'mobile primary action at least 44px',mobile);
  gate(mobile.scroll<=mobile.viewport+2,'390px viewport has no horizontal scrolling',mobile);
  await root.locator('[data-vf-playlist-mode-switch="pro"]').click();
  await root.locator('[data-vf-playlist-tab="segments"]').click();
  const evidenceCells=await root.locator('[data-vf-playlist-pane="segments"] .vf-playlist-table tbody tr').first().locator('td').evaluateAll(cells=>cells.map(cell=>({label:cell.getAttribute('data-label'),before:getComputedStyle(cell,'::before').content,display:getComputedStyle(cell).display})));
  gate(evidenceCells.length===5&&evidenceCells.every(cell=>cell.label&&cell.before!=='none'&&cell.before!=='normal'&&cell.display==='grid'),'real 390px result cells show their meaning after hidden header',evidenceCells);
  gate((await root.locator('[data-vf-playlist-pane="segments"] .vf-playlist-table tbody tr').count())>0,'professional segment pane shows actual data');

  gate(errors.length===0,'no runtime JavaScript errors',errors);
  fs.writeFileSync('proof/playlist-browser.json',JSON.stringify({status:'PASS',checks,mobile,production:'NOT_EXECUTED'},null,2));
  await page.screenshot({path:'proof/playlist-390.png',fullPage:true});
  console.log('S01_PLAYLIST_12581_REAL_BROWSER_PASS',JSON.stringify({checks:checks.length,mobile}));
 }finally{await browser.close();}
})().catch(e=>{console.error('S01_PLAYLIST_12581_REAL_BROWSER_FAIL',e.stack||String(e),JSON.stringify(checks).slice(-2100));process.exitCode=1});
