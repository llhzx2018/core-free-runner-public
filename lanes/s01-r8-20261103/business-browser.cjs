'use strict';
const {chromium}=require('playwright');
const fs=require('node:fs');
const assert=require('node:assert/strict');
const base='http://127.0.0.1:18880';
const report={scope:'S01 R8 exact merged source 55495428da43683f5e0bc6e6ec3d596a5c3e64e4',production:'UNTOUCHED',checks:[]};
const mark=(k,info)=>{report.checks.push({case:k,result:'PASS',info:info||''});console.log('S01_R8_BUSINESS_'+k+'=PASS');};
const rootFor=(p,kind)=>p.locator('[data-vf-module="'+kind+'"]').first();
async function waitFor(p,fn,label,ms=12000){
  await p.waitForFunction(fn,null,{timeout:ms}).catch(async e=>{const summary=await p.evaluate(()=>({state:[...document.querySelectorAll('[data-vf-module]')].map(x=>({module:x.dataset.vfModule,task:x.dataset.vfConverterTaskState,status:x.dataset.vfRuntimeState,backup:x.dataset.vfBackupStatus,text:(x.querySelector('[data-vf-tool-status]')||{}).textContent?.slice(0,250)})),errors:document.body.innerText.slice(-1000)}));throw new Error(label+': '+e.message+' '+JSON.stringify(summary));});
}
(async()=>{
 const browser=await chromium.launch({headless:true});
 try {
  for(const width of [768,1440]){
   const context=await browser.newContext({viewport:{width,height:900},acceptDownloads:true});
   try {
    const check=await context.newPage();
    const failures=[];check.on('pageerror',e=>failures.push('JS_ERROR '+e.message));
    check.on('response',r=>{if(r.url().includes('vf-tools-m3u8')&&r.status()>=400)failures.push('HTTP '+r.status()+' '+r.url());});
    check.on('requestfailed',r=>failures.push('FAILED '+r.url()+' '+(r.failure()?.errorText||'')));
    let res=await check.goto(base+'/m3u8-playlist-checker/',{waitUntil:'networkidle'});
    const diag=await check.evaluate(()=>({scripts:[...document.querySelectorAll('script[src]')].map(x=>x.src).filter(x=>x.includes('m3u8')).slice(0,20),loaded:document.readyState,ready:document.querySelector('[data-vf-module="playlist-checker"]')?.dataset.vfPlaylistCheckerReady,global:Object.keys(window).filter(x=>x.startsWith('VFM3U8Playlist')).slice(0,15)}));
    console.log('S01_R8_JS_BOOT_DIAGNOSTIC='+JSON.stringify({diag,failures}));
    assert.equal(res.status(),200);
    let r=rootFor(check,'playlist-checker');await r.waitFor({timeout:12000});
    await waitFor(check,()=>{let e=document.querySelector('[data-vf-module="playlist-checker"]');return e&&e.dataset.vfPlaylistCheckerReady},'checker-boot');
    await r.locator('[data-vf-playlist-action="sample-media"]').first().click();
    await r.locator('[data-vf-playlist-action="analyze"]').first().click();
    await waitFor(check,()=>{let e=document.querySelector('[data-vf-module="playlist-checker"]');return e && e.getAttribute('data-vf-playlist-has-result')==='1' && e._vfPlaylistResult?.summary?.segmentCount>0},'playlist-media');
    const media=await r.evaluate(e=>({segments:e._vfPlaylistResult.summary.segmentCount,type:e._vfPlaylistResult.type,issues:e._vfPlaylistResult.issues.length}));
    assert.equal(media.type,'media');assert.ok(media.segments>0);
    mark('PLAYLIST_MEDIA_'+width,media);
    const saved=check.waitForEvent('download',{timeout:15000});
    await r.locator('[data-vf-playlist-action="export-json"]').first().click();
    const file=await saved;assert.ok(file.suggestedFilename().endsWith('.json'));
    const value=JSON.parse(fs.readFileSync(await file.path(),'utf8'));
    assert.equal(value.type,'media');assert.ok(value.summary.segmentCount>0);
    mark('PLAYLIST_JSON_DOWNLOAD_'+width,{bytes:fs.statSync(await file.path()).size,segments:value.summary.segmentCount});
    await r.locator('[data-vf-playlist-input]').fill('#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=800000\n#EXT-X-ENDLIST');
    await r.locator('[data-vf-playlist-action="analyze"]').first().click();
    await waitFor(check,()=>{const e=document.querySelector('[data-vf-module="playlist-checker"]');return e&&e._vfPlaylistResult?.issues?.some(x=>x.level==='error')},'playlist-malformed');
    const err=await r.evaluate(e=>({state:e.dataset.vfRuntimeState,errors:e._vfPlaylistResult.issues.filter(x=>x.level==='error').map(x=>x.code)}));
    assert.equal(err.state,'error');mark('PLAYLIST_INVALID_FAIL_CLOSED_'+width,err);
    await check.close();

    const backup=await context.newPage();res=await backup.goto(base+'/m3u8-backup-restore/',{waitUntil:'networkidle'});assert.equal(res.status(),200);
    r=rootFor(backup,'backup-restore');await r.waitFor({timeout:12000});
    await r.locator('[data-vf-backup-action="preview-workspace"]').first().click();
    await waitFor(backup,()=>{const e=document.querySelector('[data-vf-module="backup-restore"]');return e&&e.dataset.vfBackupBusy==='0'&&e.dataset.vfBackupLastAction==='preview-workspace'},'backup-preview',15000);
    const downloaded=backup.waitForEvent('download',{timeout:15000});
    await r.locator('[data-vf-backup-action="export-json"]').first().click();
    const d=await downloaded;let content=fs.readFileSync(await d.path(),'utf8'),json=JSON.parse(content);
    assert.equal(json.app,'vf-m3u8');
    assert.ok(content.length>120);
    mark('BACKUP_REAL_JSON_DOWNLOAD_'+width,{bytes:content.length,name:d.suggestedFilename()});
    await r.locator('[data-vf-backup-task-toggle="restore"]').first().click();
    await r.locator('[data-vf-backup-input]').fill('not-json-synthetic');
    await r.locator('[data-vf-backup-action="preview-import"]').first().click();
    await waitFor(backup,()=>{let e=document.querySelector('[data-vf-module="backup-restore"]');return e&&e.dataset.vfBackupBusy==='0'&&e.dataset.vfBackupLastAction==='preview-import'},'invalid-backup-preflight');
    assert.equal(await r.locator('[data-vf-backup-action="restore-backup"]').isDisabled(),true);
    assert.equal(await r.locator('[data-vf-backup-recovery]').isVisible(),true);
    mark('BACKUP_INVALID_PREVIEW_FAIL_CLOSED_'+width);
    await r.locator('[data-vf-backup-input]').fill(content);
    await r.locator('[data-vf-backup-action="preview-import"]').first().click();
    await waitFor(backup,()=>{const e=document.querySelector('[data-vf-module="backup-restore"]');return e&&e.dataset.vfBackupRestorePreview==='1'&&e.dataset.vfBackupBusy==='0'},'valid-preflight');
    assert.equal(await r.locator('[data-vf-backup-action="restore-backup"]').isDisabled(),true,'restore must require confirmation');
    mark('BACKUP_RESTORE_CONFIRM_GATE_'+width);
    await r.locator('[data-vf-backup-confirm]').fill('RESTORE');
    assert.equal(await r.locator('[data-vf-backup-action="restore-backup"]').isDisabled(),false,'RESTORE should enable only after preflight');
    await backup.close();

    const convert=await context.newPage();res=await convert.goto(base+'/m3u8-to-mp4/',{waitUntil:'networkidle'});assert.equal(res.status(),200);
    r=rootFor(convert,'converter');await r.waitFor({timeout:12000});
    await convert.route('**/broken.m3u8',route=>route.fulfill({status:404,body:'not found',headers:{'content-type':'text/plain','access-control-allow-origin':'*'}}));
    await r.locator('[data-converter-url]').fill('https://fixture.example.invalid/broken.m3u8');
    await r.locator('[data-converter-generate]').first().click();
    await waitFor(convert,()=>{const e=document.querySelector('[data-vf-module="converter"]');return e && ['blocked','failed','completed'].includes(e.dataset.vfConverterTaskState)},'converter-invalid-url',25000);
    let state=await r.getAttribute('data-vf-converter-task-state');
    assert.notEqual(state,'completed','unreachable input must not produce a completed file');
    mark('CONVERTER_NETWORK_FAILURE_'+width,{state});
    await r.locator('[data-converter-clear]').first().click();
    await r.locator('[data-load-converter-sample]').first().click();
    await waitFor(convert,()=>{const e=document.querySelector('[data-vf-module="converter"]');return e&&['blocked','failed','completed'].includes(e.dataset.vfConverterTaskState)},'converter-sample',65000);
    state=await r.getAttribute('data-vf-converter-task-state');
    const ready=await r.getAttribute('data-vf-converter-output-ready');
    if(state!=='completed'||ready!=='1')throw new Error('CONVERTER_SAMPLE_REAL_OUTPUT_NOT_READY '+JSON.stringify(await r.evaluate(e=>({state:e.dataset.vfConverterTaskState,ready:e.dataset.vfConverterOutputReady,recovery:(e.querySelector('[data-converter-recovery]')||{}).textContent?.slice(0,800),status:(e.querySelector('[data-conversion-status]')||{}).textContent?.slice(0,400)}))));
    const save=convert.waitForEvent('download',{timeout:15000});
    await r.locator('[data-converter-save-again]').first().click();
    const mediaFile=await save;const info=fs.statSync(await mediaFile.path());
    assert.ok(info.size>0,'converter output empty');
    mark('CONVERTER_REAL_SAVED_FILE_'+width,{name:mediaFile.suggestedFilename(),bytes:info.size});
    await convert.close();
   }finally{await context.close();}
  }
  fs.writeFileSync('s01-r8-business-evidence.json',JSON.stringify(report,null,2));
 }catch(e){
  fs.writeFileSync('s01-r8-business-evidence.json',JSON.stringify({...report,failed:String(e.stack||e)},null,2));
  throw e;
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
