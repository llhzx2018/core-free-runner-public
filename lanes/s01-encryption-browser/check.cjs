const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert/strict');
(async()=>{const browser=await chromium.launch({headless:true}),cases=[];try{
for(const lang of ['en','zh'])for(const width of [1024,1440]){
 const page=await browser.newPage({viewport:{width,height:1000}});const keys=[];page.on('request',req=>{if(req.url().includes('example.invalid'))keys.push(req.url());});
 await page.goto('http://127.0.0.1:18880'+(lang==='zh'?'/zh/m3u8-encryption-detector/':'/m3u8-encryption-detector/'),{waitUntil:'networkidle'});
 const root=page.locator('.vf-encryption-detector[data-vf-tool-id]').first();await root.waitFor();
 assert.equal(await page.locator('h1').count(),1);assert.equal(await root.locator('[data-vf-encryption-result]').isVisible(),false);
 assert.equal(await page.locator('.vf-tool-steps-list>li>div>span').count(),0);assert.equal(await page.locator('.vf-tool-steps-list>li>b').count(),3);
 const faq=await page.locator('.vf-tool-faq-section').innerText();assert.ok(!faq.includes('useful for search and real users')&&!faq.includes('服务搜索和真实用户'));
 const geom=await page.evaluate(()=>({w:document.documentElement.clientWidth,sw:document.documentElement.scrollWidth}));assert.ok(geom.sw<=geom.w+1);
 await root.locator('[data-vf-encryption-mode-button="pro"]').click();
 const input=root.locator('[data-vf-encryption-input]');await input.waitFor({state:'visible'});
 await input.fill('#EXTM3U\n#EXT-X-TARGETDURATION:6\n#EXT-X-KEY:METHOD=AES-128,URI="https://example.invalid/key.bin"\n#EXTINF:6,\nhttps://example.invalid/one.ts\n#EXT-X-ENDLIST\n');
 await root.locator('[data-vf-encryption-action="detect"]').click();
 await root.locator('[data-vf-encryption-result]').waitFor({state:'visible'});
 const encrypted=await root.evaluate(r=>({aes128:r.__vfEncryption?.aes128,encrypted:r.__vfEncryption?.encrypted,keyCount:r.__vfEncryption?.keyCount}));
 assert.equal(encrypted.aes128,true);assert.equal(encrypted.encrypted,true);assert.ok(encrypted.keyCount>=1);
 await page.screenshot({path:`proof/encryption-${lang}-${width}.png`,fullPage:true});
 await root.locator('[data-vf-encryption-action="clear"]').click();
 await root.locator('[data-vf-encryption-mode-button="pro"]').click().catch(()=>{});
 await input.fill('#EXTM3U\n#EXT-X-TARGETDURATION:6\n#EXTINF:6,\nhttps://example.invalid/one.ts\n#EXT-X-ENDLIST\n');
 await root.locator('[data-vf-encryption-action="detect"]').click();await root.locator('[data-vf-encryption-result]').waitFor({state:'visible'});
 const clear=await root.evaluate(r=>({encrypted:r.__vfEncryption?.encrypted,keyCount:r.__vfEncryption?.keyCount}));
 assert.equal(clear.encrypted,false);assert.equal(clear.keyCount,0);assert.equal(keys.length,0,'must not fetch key or segment');
 cases.push({lang,width,encrypted,clear,noKeyOrSegmentFetch:true});await page.close();
}
fs.writeFileSync('proof/encryption.json',JSON.stringify({status:'PASS',cases},null,2));
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
