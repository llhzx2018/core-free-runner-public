const {chromium}=require('playwright');const fs=require('fs'),assert=require('assert/strict');
(async()=>{const browser=await chromium.launch({headless:true}),proof=[];try{
for(const lang of ['en','zh']){
 const ctx=await browser.newContext({viewport:{width:1440,height:1000}});
 await ctx.addInitScript(()=>{window.__copied='';window.__denyCopy=false;Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async t=>{if(window.__denyCopy)throw Error('denied');window.__copied=t;}}});document.execCommand=()=>false;});
 let requests=0;await ctx.route('https://fixture.example.test/blocked.m3u8',async route=>{requests++;await route.fulfill({status:403,headers:{'Access-Control-Allow-Origin':'*'},body:'forbidden'});});
 const page=await ctx.newPage();await page.goto('http://127.0.0.1:18880'+(lang==='zh'?'/zh/m3u8-playlist-checker/':'/m3u8-playlist-checker/'),{waitUntil:'networkidle'});
 const root=page.locator('.vf-playlist-checker[data-vf-tool-id]').first();await root.waitFor();
 assert.equal(await root.getAttribute('data-vf-playlist-has-result'),'0');assert.equal(requests,0);
 const manifest='#EXTM3U\n#EXT-X-TARGETDURATION:6\n#EXTINF:6,\none.ts\n#EXTINF:4,\ntwo.ts\n#EXT-X-ENDLIST\n';
 await root.locator('[data-vf-playlist-file]').setInputFiles({name:'sample.m3u8',mimeType:'application/vnd.apple.mpegurl',buffer:Buffer.from(manifest)});
 await page.waitForFunction(()=>document.querySelector('.vf-playlist-checker')?._vfPlaylistResult?.summary?.segmentCount===2);
 let x=await root.evaluate(r=>({type:r._vfPlaylistResult.type,segments:r._vfPlaylistResult.summary.segmentCount,duration:r._vfPlaylistResult.summary.totalDuration}));
 assert.deepEqual(x,{type:'media',segments:2,duration:10});
 await root.locator('[data-vf-playlist-action="copy-report"]').click();await page.waitForFunction(()=>window.__copied.length>0);assert.ok((await page.evaluate(()=>window.__copied)).length>20);
 await page.evaluate(()=>window.__denyCopy=true);await root.locator('[data-vf-playlist-action="copy-report"]').click();await page.waitForFunction(()=>document.querySelector('.vf-playlist-checker')?.dataset.vfRuntimeState==='error');
 assert.equal(await root.getAttribute('data-vf-playlist-has-result'),'1');assert.ok(await root.locator('[data-vf-playlist-status]').isVisible());
 await root.locator('[data-vf-playlist-action="clear"]').click();await root.locator('[data-vf-playlist-url]').fill('https://fixture.example.test/blocked.m3u8');assert.equal(requests,0);
 await root.locator('[data-vf-playlist-action="analyze"]').click();await page.waitForFunction(()=>document.querySelector('.vf-playlist-checker')?._vfPlaylistFetchMeta?.httpStatus===403);
 assert.equal(requests,1);assert.equal(await root.getAttribute('data-vf-playlist-has-result'),'0');assert.ok(await root.locator('[data-vf-playlist-recovery]').isVisible());
 await root.locator('[data-vf-playlist-recovery-sample]').click();await page.waitForFunction(()=>document.querySelector('.vf-playlist-checker')?.getAttribute('data-vf-playlist-has-result')==='1');
 assert.equal(await root.locator('[data-vf-playlist-recovery]').isVisible(),false);
 proof.push({language:lang,file:x,copy:'simulated clipboard success and denial',http403:'intercepted, one attempt',recovery:'bundled sample'});
 await ctx.close();
}fs.writeFileSync('proof/checker-inputs.json',JSON.stringify({status:'PASS',proof,scope:'synthetic WordPress; simulated clipboard and intercepted HTTP',production:'UNTOUCHED'},null,2));console.log(JSON.stringify(proof));
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
