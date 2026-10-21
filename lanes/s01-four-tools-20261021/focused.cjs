const {chromium}=require('playwright'),fs=require('fs');
const fixtures=JSON.parse(fs.readFileSync('proof/cases.json','utf8')).cases;
const checks=[];
function check(name,ok,detail){checks.push({name,pass:!!ok,detail});}
async function open(p,url){await p.goto(url,{waitUntil:'load'});await p.evaluate(()=>document.fonts.ready);}
async function run(p,api,action){return p.evaluate(async ({api,action})=>{const f=window[api];return {exists:!!f,result:f?.run?await f.run(action):null}},{api,action});}
async function grab(p,trigger,key){let d;try{[d]=await Promise.all([p.waitForEvent('download',{timeout:20000}),trigger()]);const path=await d.path(),content=fs.readFileSync(path);fs.writeFileSync('proof/'+key+'-'+d.suggestedFilename(),content);check(key+' browser downloaded nonempty file',content.length>20,{bytes:content.length,file:d.suggestedFilename()});return {name:d.suggestedFilename(),content:content.toString('utf8')};}catch(e){check(key+' real download',false,String(e));return null;}}
async function validate(p,label){const result=await p.evaluate(()=>({h1:document.querySelectorAll('main h1').length,overflow:document.documentElement.scrollWidth>innerWidth+2,jsModule:!!document.querySelector('[data-vf-module]'),heading:document.querySelector('main h1')?.textContent}));check(label+' visible primary heading',result.h1===1,result);check(label+' desktop no horizontal overflow',!result.overflow,result);}
(async()=>{const browser=await chromium.launch();try{
for(const lang of ['en','zh']){
const context=await browser.newContext({viewport:{width:1440,height:950},acceptDownloads:true,permissions:['clipboard-read','clipboard-write']});
const p=await context.newPage();p.setDefaultTimeout(12000);
await open(p,fixtures[lang].tool_hub);
const links=await p.locator('.vf-directory-tool-card .vf-directory-card-action').evaluateAll(xs=>xs.map(x=>x.href));
const slugs={encryption:'m3u8-encryption-detector',iptv:'iptv-manager',links:'m3u8-test-links',backup:'m3u8-backup-restore'};
const urls={};for(const [k,slug] of Object.entries(slugs)){urls[k]=links.find(u=>new URL(u).pathname.endsWith('/'+slug+'/'));check(lang+' '+k+' present in real tool directory',!!urls[k],urls[k]||null);}
if(Object.values(urls).some(v=>!v)){await context.close();continue;}
if(process.env.FOCUS_CASE!=='test-links')try{
await open(p,urls.encryption);await validate(p,lang+' encryption');
let st=await run(p,'VFM3U8EncryptionDetectorLab','selfTest');check(lang+' encryption selfTest',st.result?.ok,st.result?.checks?.filter(x=>!x.ok));
let protectedResult=await run(p,'VFM3U8EncryptionDetectorLab','sample-protected');
check(lang+' encryption bundled protected sample parsed',protectedResult.result?.ok,protectedResult.result?.state);
let data=await p.evaluate(()=>{let r=window.VFM3U8EncryptionDetectorLab.roots()[0];return {result:!!r.__vfEncryption,keys:r.__vfEncryption?.keys?.length??null,session:r.__vfEncryption?.sessionKeys?.length??null,hasResult:r.dataset.vfEncryptionHasResult};});check(lang+' encryption protected metadata exposed',data.hasResult==='1'&&((data.keys||0)+(data.session||0)>0),data);
const j=await grab(p,()=>p.locator('[data-vf-encryption-action="export"]').click(),lang+' encryption JSON');
if(j){try{let o=JSON.parse(j.content);check(lang+' encryption JSON has actual keys',Array.isArray(o.keys)&&o.keys.length>0,{keyCount:o.keys?.length});}catch(e){check(lang+' encryption JSON parses',false,String(e));}}
const csv=await grab(p,()=>p.locator('[data-vf-encryption-action="export-csv"]').click(),lang+' encryption CSV');
if(csv)check(lang+' encryption CSV actual header',csv.content.startsWith('"tag","index","method"'),csv.content.slice(0,110));
const clear=await run(p,'VFM3U8EncryptionDetectorLab','sample-clear');check(lang+' encryption clear sample completed',!!clear.result?.ok,clear.result?.state);
}catch(e){check(lang+' encryption scenario',false,String(e));}
if(process.env.FOCUS_CASE!=='test-links')try{
await open(p,urls.iptv);await validate(p,lang+' IPTV');
const st=await run(p,'VFM3U8IPTVLab','selfTest');check(lang+' IPTV selfTest',st.result?.ok,st.result?.checks?.filter(x=>!x.ok));
const sample=await run(p,'VFM3U8IPTVLab','sample');check(lang+' IPTV sample imported',sample.result?.ok,sample.result);
const rows=await p.evaluate(()=>window.VFM3U8IPTVLab.read().map(x=>({url:x.url,name:x.name,group:x.group,favorite:x.favorite})));check(lang+' IPTV real imported channel rows',rows.length>=3&&rows.every(x=>/^https?:\/\//.test(x.url)),rows.slice(0,4));
const jf=await grab(p,()=>p.evaluate(()=>window.VFM3U8IPTVLab.run('exportJson')),lang+' IPTV JSON');if(jf){try{const o=JSON.parse(jf.content);check(lang+' IPTV JSON channels',Array.isArray(o.channels)&&o.channels.length===rows.length,{count:o.channels?.length,expected:rows.length});}catch(e){check(lang+' IPTV JSON parses',false,String(e));}}
const mf=await grab(p,()=>p.evaluate(()=>window.VFM3U8IPTVLab.run('exportM3u')),lang+' IPTV M3U');if(mf)check(lang+' IPTV M3U content',mf.content.startsWith('#EXTM3U')&&mf.content.includes('#EXTINF'),mf.content.slice(0,120));
await p.reload({waitUntil:'load'});const after=await p.evaluate(()=>window.VFM3U8IPTVLab?.read()?.length??-1);check(lang+' IPTV browser refresh persists sample channels',after===rows.length,{before:rows.length,after});
}catch(e){check(lang+' IPTV scenario',false,String(e));}
try{
await open(p,urls.links);await validate(p,lang+' test links');
const st=await run(p,'VFM3U8TestLinksLab','selfTest');check(lang+' test links selfTest',st.result?.ok,st.result?.checks?.filter(x=>!x.ok));
const sample=await run(p,'VFM3U8TestLinksLab','sample');check(lang+' test links sample loaded',sample.result?.ok,sample.result);
const verified=await run(p,'VFM3U8TestLinksLab','verify');check(lang+' test links actual verification returned',verified.result?.ok,verified.result);
const data=await p.evaluate(()=>window.VFM3U8TestLinksLab.exportPayload());check(lang+' test links export carries source and library',data&&Array.isArray(data.all)&&data.all.length>=3&&new URL(data.current,p.url()).protocol.startsWith('http'),{count:data?.all?.length,current:data?.current});
await p.locator('[data-vf-test-links-mode-button="pro"]').click();await p.locator('.vf-tl-pro').evaluate(n=>{if(n.tagName==='DETAILS')n.open=true});const jc=await grab(p,()=>p.locator('[data-vf-test-links-download-json]').click(),lang+' test links JSON');
if(jc){try{const o=JSON.parse(jc.content);check(lang+' test links JSON actual library',o.app==='vf-m3u8-test-links'&&Array.isArray(o.all)&&o.all.length>=3,{app:o.app,count:o.all?.length});}catch(e){check(lang+' test links JSON parses',false,String(e));}}
}catch(e){check(lang+' test links scenario',false,String(e));}
if(process.env.FOCUS_CASE!=='test-links')try{
await open(p,urls.backup);await validate(p,lang+' backup');
const st=await run(p,'VFM3U8BackupRestoreLab','selfTest');check(lang+' backup selfTest',st.result?.ok,st.result?.checks?.filter(x=>!x.ok));
const b=await grab(p,()=>p.evaluate(()=>window.VFM3U8BackupRestoreLab.run('export-json')),lang+' backup JSON');
if(b){try{let j=JSON.parse(b.content);check(lang+' backup full JSON schema',j.app==='vf-m3u8'&&j.backup_schema_version===1,{app:j.app,schema:j.backup_schema_version});}catch(e){check(lang+' backup JSON parses',false,String(e));}}
const sample=await run(p,'VFM3U8BackupRestoreLab','load-sample-backup');check(lang+' backup sample entered',sample.result?.ok,sample.result);
const pre=await run(p,'VFM3U8BackupRestoreLab','preview-import');check(lang+' backup preview real conflict diff',pre.result?.ok&&pre.result.diff?.requiredConfirm==='RESTORE',pre.result?.diff?{stores:pre.result.diff.stores?.length,confirm:pre.result.diff.requiredConfirm}:pre.result);
const denied=await run(p,'VFM3U8BackupRestoreLab','restore-backup');check(lang+' backup confirmation rejects unapproved restore',!denied.result?.ok,denied.result);
}catch(e){check(lang+' backup scenario',false,String(e));}
if(['deep','restore'].includes(process.env.FOCUS_CASE)){
if(process.env.FOCUS_CASE==='deep')try{
await open(p,urls.iptv);
const sample=await run(p,'VFM3U8IPTVLab','sample');check(lang+' IPTV deep sample',sample.result?.ok,sample.result);
const rows=await p.evaluate(()=>window.VFM3U8IPTVLab.read());
check(lang+' IPTV group and favorite metadata preserved',rows.some(x=>x.favorite)&&rows.some(x=>x.group),rows.map(x=>({name:x.name,group:x.group,favorite:x.favorite})).slice(0,5));
const exported=await grab(p,()=>p.evaluate(()=>window.VFM3U8IPTVLab.run('exportM3u')),lang+' IPTV deep M3U');
if(exported){await p.locator('[data-vf-iptv-import]').fill(exported.content);const imported=await run(p,'VFM3U8IPTVLab','import');const after=await p.evaluate(()=>window.VFM3U8IPTVLab.read());check(lang+' IPTV export and reimport same channels without duplicates',imported.result?.ok&&after.length===rows.length,{before:rows.length,after:after.length,imported:imported.result});}
await p.screenshot({path:'proof/'+lang+'-iptv-deep.png',fullPage:true});
}catch(e){check(lang+' IPTV deep scenario',false,String(e));}
if(process.env.FOCUS_CASE==='deep')try{
await open(p,urls.links);
const sample=await run(p,'VFM3U8TestLinksLab','sample');check(lang+' test links deep sample',sample.result?.ok);
await p.locator('[data-vf-test-links-mode-button="pro"]').click();await p.locator('.vf-tl-pro').evaluate(n=>{if(n.tagName==='DETAILS')n.open=true});
const csv=await grab(p,()=>p.locator('[data-vf-test-links-download-csv]').click(),lang+' test links deep CSV');
if(csv)check(lang+' test links CSV real entries',csv.content.includes('name')&&csv.content.includes('url')&&csv.content.split('\n').length>=4,{rows:csv.content.split('\n').length});
const txt=await grab(p,()=>p.locator('[data-vf-test-links-download-txt]').click(),lang+' test links deep TXT');
if(txt)check(lang+' test links TXT has real sample paths',txt.content.includes('.m3u8'),txt.content.slice(0,250));
await p.evaluate(()=>{window.__vfBatchPromise=window.VFM3U8TestLinksLab.batchTest()});
await p.waitForTimeout(50);
const cancelled=await p.evaluate(()=>window.VFM3U8TestLinksLab.cancel());
check(lang+' test links cancellation is available',cancelled!==undefined,cancelled);
await p.evaluate(()=>window.__vfBatchPromise);
check(lang+' test links batch settled',await p.locator('[data-vf-module="test-links"]').getAttribute('data-vf-test-links-batch-running')!=='1');
await p.screenshot({path:'proof/'+lang+'-test-links-deep.png',fullPage:true});
}catch(e){check(lang+' test links deep scenario',false,String(e));}
try{
await open(p,urls.backup);
const root=p.locator('[data-vf-module="backup-restore"]'); const collect=()=>p.evaluate(async()=>window.VFM3U8BackupRestoreLab.collect());
const before=await collect();
const original=await p.evaluate(async()=>{const l=window.VFM3U8BackupRestoreLab;return l.workspaceFingerprint(await l.collect())});
const guard=await p.evaluate(()=>{const lab=window.VFM3U8BackupRestoreLab,source=lab.sampleBackup(),row=structuredClone(source);row.playlists[0].updated_at='2030-01-01T00:00:00Z';const metadataOnly=lab.verifyRestored(row,source,'replace');row.playlists[0].name='INTENTIONAL_TAMPER';const corrupted=lab.verifyRestored(row,source,'replace');return{metadataOnly:metadataOnly.ok,materialTamperBlocked:!corrupted.ok,errors:corrupted.failures};});check(lang+' backup ignores storage-owned timestamp but detects altered content',guard.metadataOnly&&guard.materialTamperBlocked,guard);
const sample=await run(p,'VFM3U8BackupRestoreLab','load-sample-backup');
const preview=await run(p,'VFM3U8BackupRestoreLab','preview-import');
check(lang+' backup deep preflight before restore',sample.result?.ok&&preview.result?.ok,{sample:sample.result,pre:preview.result?.ok});
await p.locator('[data-vf-backup-confirm]').fill('RESTORE');
const restored=await run(p,'VFM3U8BackupRestoreLab','restore-backup');
const restorationDiagnostics=await p.evaluate(()=>({report:document.querySelector('[data-vf-backup-output]')?.textContent,recovery:document.querySelector('[data-vf-backup-recovery-text]')?.textContent,status:document.querySelector('[data-vf-backup-status]')?.textContent,workspaceAvailable:!!window.VFM3U8Workspace}));fs.writeFileSync('proof/'+lang+'-restore-diagnostics.json',JSON.stringify(restorationDiagnostics,null,2));check(lang+' backup deep actual restore and verification',restored.result?.ok===true&&restored.result?.verification?.ok===true,{result:restored.result,diagnostics:restorationDiagnostics});
if(restored.result?.ok){
const next=await collect();check(lang+' backup deep restored real sample data',Array.isArray(next.channels)&&next.channels.some(x=>x.name.includes('Demo')||x.name.includes('示例')),{channels:next.channels?.length});
const rollback=await run(p,'VFM3U8BackupRestoreLab','rollback-last-change');
check(lang+' backup deep rollback completed',rollback.result?.ok===true,rollback.result);
if(rollback.result?.ok){const confirmed=await p.evaluate(async(before)=>{const l=window.VFM3U8BackupRestoreLab;return l.verifyRestored(await l.collect(),before,'replace')},before);check(lang+' backup deep original material workspace verified after rollback',confirmed.ok,confirmed);}
}
await p.screenshot({path:'proof/'+lang+'-backup-deep.png',fullPage:true});
}catch(e){check(lang+' backup deep scenario',false,String(e));}
}
await context.close();
}
}finally{await browser.close();}
fs.writeFileSync('proof/four-tools-results.json',JSON.stringify({count:checks.length,passed:checks.filter(x=>x.pass).length,failed:checks.filter(x=>!x.pass),checks},null,2));
console.log('FOUR_TOOLS_CHECKS '+checks.length+' FAIL '+JSON.stringify(checks.filter(x=>!x.pass)).slice(0,12000));
if(checks.some(x=>!x.pass))process.exitCode=1;
})().catch(e=>{console.error(e);process.exitCode=1;});