const {chromium}=require('playwright');const fs=require('fs'),assert=require('assert/strict');
(async()=>{const browser=await chromium.launch({headless:true});let proof=[];try{
for(const lang of ['en','zh'])for(const width of [1024,1440]){
const page=await browser.newPage({viewport:{width,height:1000}});await page.goto('http://127.0.0.1:18880'+(lang==='zh'?'/zh/m3u8-playlist-checker/':'/m3u8-playlist-checker/'),{waitUntil:'networkidle'});
const meta=await page.locator('meta[name="description"]').getAttribute('content');assert.equal(meta,lang==='zh'?'自定义中文检测页面描述。':'Custom English checker page description.','localized Rank Math description');
const root=page.locator('.vf-playlist-checker[data-vf-tool-id]').first();await root.waitFor();assert.equal(await page.locator('h1').count(),1);assert.ok(await root.locator('[data-vf-playlist-url]').isVisible());assert.ok(await root.locator('[data-vf-playlist-action="analyze"]').isVisible());
let g=await page.evaluate(()=>({w:document.documentElement.clientWidth,sw:document.documentElement.scrollWidth}));assert.ok(g.sw<=g.w+1);
await root.locator('[data-vf-playlist-action="sample-master"]').click();await page.waitForFunction(()=>document.querySelector('.vf-playlist-checker')?.getAttribute('data-vf-playlist-has-result')==='1');
const master=await root.evaluate(r=>r._vfPlaylistResult&&({type:r._vfPlaylistResult.type,variants:r._vfPlaylistResult.summary.variantCount}));assert.equal(master.type,'master');assert.equal(master.variants,3);
await root.locator('[data-vf-playlist-action="clear"]').click();
const input=root.locator('[data-vf-playlist-input]');await input.fill('#EXTM3U\n#EXT-X-TARGETDURATION:6\n#EXTINF:6,\none.ts\n#EXTINF:4,\ntwo.ts\n#EXT-X-ENDLIST\n');await root.locator('[data-vf-playlist-action="analyze"]').click();
const media=await root.evaluate(r=>r._vfPlaylistResult&&({type:r._vfPlaylistResult.type,segments:r._vfPlaylistResult.summary.segmentCount,duration:r._vfPlaylistResult.summary.totalDuration}));assert.deepEqual(media,{type:'media',segments:2,duration:10});
assert.equal(await page.locator('.vf-tool-steps-list>li>b').first().isVisible(),false);
const box=await page.locator('.vf-tool-steps-list>li>div').first().boundingBox();assert.ok(box&&box.width>=120,'workflow text column must remain readable');
if(width===1440){const pending=page.waitForEvent('download',{timeout:10000});await root.locator('[data-vf-playlist-action="export-json"]').click();const download=await pending;const data=JSON.parse(fs.readFileSync(await download.path(),'utf8'));assert.equal(data.summary.segmentCount,2);assert.equal(data.summary.totalDuration,10);}
await page.screenshot({path:`proof/checker-${lang}-${width}.png`,fullPage:true});proof.push({language:lang,width,master,media});await page.close();}
fs.writeFileSync('proof/checker.json',JSON.stringify({status:'PASS',cases:proof,production:'UNTOUCHED'},null,2));
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
