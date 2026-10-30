const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert/strict');
(async()=>{const browser=await chromium.launch({headless:true}),results=[];try{
for(const lang of ['en','zh'])for(const width of [1024,1440]){
const page=await browser.newPage({viewport:{width,height:1000},acceptDownloads:true});
await page.goto('http://127.0.0.1:18880'+(lang==='zh'?'/zh/m3u8-segment-viewer/':'/m3u8-segment-viewer/'),{waitUntil:'networkidle'});
const root=page.locator('.vf-segment-viewer[data-vf-tool-id]').first();await root.waitFor();
assert.equal(await page.locator('h1').count(),1);
assert.equal(await root.locator('[data-vf-segment-result]').isVisible(),false,'result starts hidden');
assert.ok(await root.locator('[data-vf-segment-input]').isVisible());
const steps=await page.locator('.vf-tool-steps-list').innerText(),faq=await page.locator('.vf-tool-faq-list').innerText();
assert.ok(steps.includes(lang==='zh'?'媒体播放清单':'media playlist'));
assert.ok(faq.includes(lang==='zh'?'相对路径':'relative'));
assert.ok(!faq.includes(lang==='zh'?'频道':'channel'));
const size=await page.evaluate(()=>({w:document.documentElement.clientWidth,sw:document.documentElement.scrollWidth}));assert.ok(size.sw<=size.w+1,'horizontal overflow');
await root.locator('[data-vf-segment-input]').fill('#EXTM3U\n#EXT-X-TARGETDURATION:6\n#EXTINF:6,\nhttps://example.invalid/one.ts\n#EXTINF:4,\nhttps://example.invalid/two.ts\n#EXT-X-ENDLIST\n');
await root.locator('[data-vf-segment-action="analyze"]').click();
await root.locator('[data-vf-segment-result]').waitFor({state:'visible',timeout:15000});
const out=await root.locator('[data-vf-segment-result]').innerText();
assert.ok(out.includes('one.ts')&&out.includes('two.ts'),'two segments visible');
if(width===1440){const pending=page.waitForEvent('download',{timeout:10000});await root.locator('[data-vf-segment-action="txt"]').click();const dl=await pending;const text=fs.readFileSync(await dl.path(),'utf8');assert.ok(text.includes('one.ts')&&text.includes('two.ts'),'actual TXT export');}
await page.screenshot({path:`proof/segment-${lang}-${width}.png`,fullPage:true});
results.push({lang,width,parsed:'2 segment URLs',txt:width===1440?'PASS':'NOT_RUN'});await page.close();
}
fs.writeFileSync('proof/segment.json',JSON.stringify({status:'PASS',results},null,2));
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
