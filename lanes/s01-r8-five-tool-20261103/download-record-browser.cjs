'use strict';
// S01 R8 actual user-entry downloader and live-recorder tool business paths.
// Synthetic local HLS fragments and disposable WordPress only. No external media.
const {chromium}=require('playwright');
const fs=require('node:fs');
const assert=require('node:assert/strict');
const base='http://127.0.0.1:18880';
const report={scope:'R8 current M3U8 exact-head real Chromium VOD and LIVE',cases:[],errors:[]};
const mark=(name,meta)=>{report.cases.push({name,result:'PASS',meta});console.log('S01_R8_ENTRY_'+name+'=PASS');};
const url=base+'/m3u8-download-record/';
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  for(const width of [768,1440]){
   const context=await browser.newContext({viewport:{width,height:900},acceptDownloads:true});
   try{
    const page=await context.newPage();
    page.on('pageerror',e=>report.errors.push(String(e.message)));
    let response=await page.goto(url,{waitUntil:'networkidle',timeout:35000});
    assert.equal(response.status(),200,'Entry page must be public');
    const root=page.locator('[data-vf-product-flow="download-record"]').first();
    await root.waitFor({timeout:20000});
    await page.waitForFunction(()=>!!window.VFM3U8DownloadRecordEntry&&document.querySelector('[data-vf-product-flow="download-record"]')?.dataset.vfEntryBound==='1',null,{timeout:20000});
    const vodUrl=base+'/wp-content/plugins/vf-tools-m3u8/public/media/player-demo/demo.m3u8';
    await root.locator('[data-vf-entry-input]').fill(vodUrl);
    await root.locator('[data-vf-entry-analyze]').click();
    await page.waitForFunction(()=>document.querySelector('[data-vf-product-flow="download-record"]')?.__vfEntryResult?.state==='can-download',null,{timeout:20000});
    const dlPromise=page.waitForEvent('download',{timeout:30000});
    await root.locator('[data-vf-entry-download]').click();
    const dl=await dlPromise;
    const actual=fs.readFileSync(await dl.path());
    const dir='candidate/src/public/media/player-demo/';
    const expected=Buffer.concat(['init.mp4','seg000.m4s','seg001.m4s','seg002.m4s'].map(n=>fs.readFileSync(dir+n)));
    assert.ok(actual.equals(expected),'real browser VOD downloaded bytes must equal init+segments in playlist order');
    await page.waitForFunction(()=>document.querySelector('[data-vf-product-flow="download-record"]')?.querySelector('[data-vf-entry-download-task]')?.dataset.state==='completed',null,{timeout:16000});
    mark('VOD_REAL_FILE_'+width,{filename:dl.suggestedFilename(),bytes:actual.length,sourceSegments:3,withInit:true});
    await page.close();

    const live=await context.newPage();
    live.on('pageerror',e=>report.errors.push(String(e.message)));
    let manifestRequests=0,fragmentRequests=0;
    await live.route('**/vf-r8-live.m3u8',async route=>{
      manifestRequests++;
      const entries=manifestRequests<=2?['100.ts']:['100.ts','101.ts','102.ts'];
      const body=['#EXTM3U','#EXT-X-VERSION:3','#EXT-X-TARGETDURATION:1','#EXT-X-MEDIA-SEQUENCE:100',...entries.flatMap(x=>['#EXTINF:1,','vf-r8-live/'+x])].join('\n')+'\n';
      await route.fulfill({status:200,body,contentType:'application/vnd.apple.mpegurl',headers:{'access-control-allow-origin':'*'}});
    });
    await live.route('**/vf-r8-live/*',async route=>{
      fragmentRequests++;
      const match=route.request().url().match(/\/(100|101|102)\.ts(?:\?.*)?$/);
      assert.ok(match,'only the three synthetic transport segments are allowed');
      const packet=Buffer.alloc(188,0);
      packet[0]=0x47;
      packet[1]=Number(match[1])-100;
      packet[2]=0x10;
      packet[3]=0x10;
      await route.fulfill({status:200,body:packet,contentType:'video/mp2t',headers:{'access-control-allow-origin':'*'}});
    });
    response=await live.goto(url,{waitUntil:'networkidle',timeout:35000});
    assert.equal(response.status(),200);
    const lr=live.locator('[data-vf-product-flow="download-record"]').first();
    await lr.waitFor({timeout:20000});
    await lr.locator('[data-vf-entry-input]').fill(base+'/vf-r8-live.m3u8');
    await lr.locator('[data-vf-entry-analyze]').click();
    await live.waitForFunction(()=>document.querySelector('[data-vf-product-flow="download-record"]')?.__vfEntryResult?.state==='can-record',null,{timeout:20000});
    await lr.locator('[data-vf-entry-record]').click();
    await live.waitForFunction(()=>{const r=document.querySelector('[data-vf-product-flow="download-record"]');return r?.__vfEntryRecorder?.snapshot?.().partSegments>=2;},null,{timeout:28000});
    const liveDownload=live.waitForEvent('download',{timeout:25000});
    await lr.locator('[data-vf-entry-record-stop]').click();
    const part=await liveDownload;
    const bytes=fs.readFileSync(await part.path());
    assert.equal(bytes.length,376,'live file must contain exactly two full 188-byte transport packets');
    assert.equal(bytes[0],0x47,'first packet sync byte');
    assert.equal(bytes[1],1,'recording begins with first NEW segment 101, not baseline 100');
    assert.equal(bytes[188],0x47,'second packet sync byte');
    assert.equal(bytes[189],2,'second NEW segment 102 follows 101 in original order');
    assert.ok(fragmentRequests>=2 && manifestRequests>=3,'real live polling must retrieve both new segments, not only the baseline');
    mark('LIVE_REAL_PART_'+width,{filename:part.suggestedFilename(),bytes:bytes.length,manifestRequests,fragmentRequests});
    await live.close();
   }finally{await context.close();}
  }
  assert.deepEqual(report.errors,[],'No browser page JavaScript errors');
  console.log('S01_R8_DOWNLOAD_AND_RECORD_REAL_BROWSER=PASS 4/4');
 }catch(err){report.failure=String(err.stack||err);throw err;}
 finally{fs.writeFileSync('s01-r8-download-record-browser-evidence.json',JSON.stringify(report,null,2));await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
