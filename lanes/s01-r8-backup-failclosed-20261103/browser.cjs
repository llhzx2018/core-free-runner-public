'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {chromium}=require('playwright');
const url='http://127.0.0.1:18882/m3u8-backup-restore/';
const report={scope:'S01 R8 exact-head isolated IndexedDB synthetic recovery',cases:[],errors:[]};
async function check(page,name,fn){const r=await page.evaluate(fn);assert.equal(r.ok,true,name+' '+JSON.stringify(r));report.cases.push({name,...r});console.log(name+'=PASS');}
(async()=>{
 const browser=await chromium.launch({headless:true});
 const context=await browser.newContext({viewport:{width:1440,height:1000},locale:'en-US'});
 const page=await context.newPage();
 page.on('pageerror',e=>report.errors.push(e.message));
 try{
  await page.goto(url,{waitUntil:'domcontentloaded',timeout:45000});
  await page.waitForFunction(()=>!!window.VFM3U8BackupRestoreLab&&!!window.VFM3U8IndexedDB&&document.querySelector('[data-vf-module="backup-restore"]')?.dataset.vfBackupBooted==='1',{timeout:30000});
  await check(page,'S01_R8_BROWSER_IDB_PARTIAL_WRITE_ROLLBACK',async()=>{
   const root=document.querySelector('[data-vf-module="backup-restore"]');
   const lab=window.VFM3U8BackupRestoreLab,idb=window.VFM3U8IndexedDB;
   const normalize=rows=>rows.map(row=>{const x={...row};delete x.updated_at;return x;}).sort((a,b)=>JSON.stringify(a).localeCompare(JSON.stringify(b)));
   await idb.clear('test_links');await idb.clear('settings');
   await idb.put('test_links',{link_id:'vf-synthetic-original',url:'https://example.invalid/original.m3u8'});
   await idb.put('settings',{key:'non_prefixed_opaque_setting',value:{sentinel:'preserve'}});
   localStorage.setItem('vf_m3u8_synthetic_owner_canary',JSON.stringify({keep:'exact'}));
   const prior=normalize(await idb.getAll('test_links'));
   const setting=normalize(await idb.getAll('settings'));
   const raw=localStorage.getItem('vf_m3u8_synthetic_owner_canary');
   const original=idb.bulkPut;let partial=0;
   idb.bulkPut=function(store,rows){if(store==='test_links'){partial++;return original.call(idb,store,rows.slice(0,1)).then(()=>Promise.reject(Error('SYNTHETIC_MID_WRITE')));}return original.call(idb,store,rows);};
   let result;
   try{result=await lab.run('restore-defaults',root);}finally{idb.bulkPut=original;}
   const post=normalize(await idb.getAll('test_links'));
   const postSettings=normalize(await idb.getAll('settings'));
   const rawAfter=localStorage.getItem('vf_m3u8_synthetic_owner_canary');
   return {ok:result?.ok===false && result.rollbackVerified===true && partial===1 && JSON.stringify(prior)===JSON.stringify(post) && JSON.stringify(setting)===JSON.stringify(postSettings) && raw===rawAfter,
    result,partial,before:prior.length,after:post.length,settingsPreserved:JSON.stringify(setting)===JSON.stringify(postSettings),rawPreserved:raw===rawAfter};
  });
  await check(page,'S01_R8_BROWSER_IDB_SNAPSHOT_REJECT_NO_WRITE',async()=>{
   const root=document.querySelector('[data-vf-module="backup-restore"]');
   const lab=window.VFM3U8BackupRestoreLab,idb=window.VFM3U8IndexedDB;
   const before=JSON.stringify(await idb.getAll('test_links'));
   const originalPut=idb.put,originalBulk=idb.bulkPut;let writeCalled=0;
   idb.put=function(store,...rest){if(store==='backups')return Promise.reject(Error('SYNTHETIC_SAFETY_SNAPSHOT_REJECT'));return originalPut.call(idb,store,...rest);};
   idb.bulkPut=function(...args){writeCalled++;return originalBulk.apply(idb,args);};
   let result;try{result=await lab.run('restore-defaults',root);}finally{idb.put=originalPut;idb.bulkPut=originalBulk;}
   const after=JSON.stringify(await idb.getAll('test_links'));
   return {ok:result?.ok===false&&writeCalled===0&&before===after,result,writeCalled,dataUnchanged:before===after};
  });
  await check(page,'S01_R8_BROWSER_ROLLBACK_FALSE_GREEN_GUARD',async()=>{
   const root=document.querySelector('[data-vf-module="backup-restore"]');
   const lab=window.VFM3U8BackupRestoreLab,idb=window.VFM3U8IndexedDB;
   const backup=root.__vfLastSafetySnapshot;
   if(!backup)return{ok:false,reason:'no prior verified snapshot'};
   await idb.put('test_links',{link_id:'vf-synthetic-extra',url:'https://example.invalid/changed.m3u8'});
   const original=idb.importAll;let attempts=0;
   idb.importAll=function(){attempts++;return Promise.resolve({});};
   let result;try{result=await lab.run('rollback-last-change',root);}finally{idb.importAll=original;}
   const remains=(await idb.getAll('test_links')).some(x=>x.link_id==='vf-synthetic-extra');
   return{ok:result?.ok===false&&attempts===1&&remains,attempts,remains,result};
  });
  assert.deepEqual(report.errors,[], 'no page JavaScript errors');
  console.log('S01_R8_REAL_BROWSER_INDEXEDDB_FAILURE_GATES=PASS 3/3');
 }finally{
  fs.writeFileSync('s01-r8-backup-failclosed-browser-evidence.json',JSON.stringify(report,null,2));
  await context.close();await browser.close();
 }
})().catch(err=>{console.error(err);process.exitCode=1});
