const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert/strict');
(async()=>{const browser=await chromium.launch({headless:true});const results=[];try{
for(const lang of ['en','zh']){
 const page=await browser.newPage({viewport:{width:1440,height:1000},acceptDownloads:true});const urls=[];
 await page.route('https://fixture.invalid/**',async route=>{urls.push(route.request().url());if(route.request().url().endsWith('/manifest.m3u8'))await route.fulfill({status:200,headers:{'access-control-allow-origin':'*','content-type':'application/vnd.apple.mpegurl'},body:'#EXTM3U\n#EXT-X-KEY:METHOD=AES-128,URI="https://fixture.invalid/key.bin"\n#EXTINF:5,\nhttps://fixture.invalid/seg.ts\n#EXT-X-ENDLIST\n'});else await route.abort();});
 await page.goto('http://127.0.0.1:18880'+(lang==='zh'?'/zh/m3u8-encryption-detector/':'/m3u8-encryption-detector/'),{waitUntil:'networkidle'});
 const root=page.locator('.vf-encryption-detector[data-vf-tool-id]').first();await root.waitFor();
 await root.locator('[data-vf-encryption-action="detect"]').click();await root.locator('[data-vf-encryption-recovery]').waitFor({state:'visible'});
 assert.equal(await root.locator('[data-vf-encryption-result]').isVisible(),false,'empty should not show result');
 await root.locator('[data-vf-encryption-action="clear"]').click();
 await root.locator('[data-vf-encryption-url]').fill('https://fixture.invalid/manifest.m3u8');
 await root.locator('[data-vf-encryption-action="detect"]').click();await root.locator('[data-vf-encryption-result]').waitFor({state:'visible'});
 const network=await root.evaluate(r=>({aes:r.__vfEncryption?.aes128,network:r.__vfEncryption?.network}));assert.equal(network.aes,true);assert.deepEqual(urls,['https://fixture.invalid/manifest.m3u8']);
 const pending=page.waitForEvent('download',{timeout:10000});await root.locator('[data-vf-encryption-action="export"]').click();const dl=await pending;const report=JSON.parse(fs.readFileSync(await dl.path(),'utf8'));assert.equal(report.aes128,true);assert.equal(report.encrypted,true);
 await root.locator('[data-vf-encryption-action="clear"]').click();await root.locator('[data-vf-encryption-mode-button="pro"]').click();
 await root.locator('[data-vf-encryption-file]').setInputFiles({name:'sample.m3u8',mimeType:'text/plain',buffer:Buffer.from('#EXTM3U\n#EXT-X-KEY:METHOD=AES-128,URI="https://fixture.invalid/key.bin"\n#EXTINF:5,\none.ts\n#EXT-X-ENDLIST\n')});
 await page.waitForFunction(()=>document.querySelector('[data-vf-encryption-input]')?.value.includes('#EXT-X-KEY'));
 await root.locator('[data-vf-encryption-action="detect"]').click();await root.locator('[data-vf-encryption-result]').waitFor({state:'visible'});assert.equal(await root.evaluate(r=>r.__vfEncryption?.aes128),true);
 await root.locator('[data-vf-encryption-input]').fill('not a valid playlist');
 await root.locator('[data-vf-encryption-action="detect"]').click();await root.locator('[data-vf-encryption-recovery]').waitFor({state:'visible'});
 assert.equal(await root.locator('[data-vf-encryption-result]').isVisible(),false,'invalid manifest must not show success');
 assert.deepEqual(urls,['https://fixture.invalid/manifest.m3u8'],'no key or media requests');
 results.push({lang,empty:'PASS',url:'PASS',json:'PASS',file:'PASS',invalid:'PASS',noKeyOrSegmentFetch:'PASS'});await page.close();
}
fs.writeFileSync('proof/encryption-extra.json',JSON.stringify({status:'PASS',results},null,2));
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});