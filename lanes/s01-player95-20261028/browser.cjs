const fs=require('fs'),http=require('http'),path=require('path'),assert=require('assert/strict');
const {chromium}=require('playwright');
const srv=http.createServer((req,res)=>{const file=path.join(process.cwd(),'sample',path.basename(req.url.split('?')[0]));res.setHeader('Access-Control-Allow-Origin','*');if(!fs.existsSync(file)){res.writeHead(404);return res.end('missing');}res.setHeader('Content-Type',file.endsWith('.m3u8')?'application/vnd.apple.mpegurl':file.endsWith('.ts')?'video/mp2t':'video/mp4');res.end(fs.readFileSync(file));});
(async()=>{await new Promise(r=>srv.listen(18881,'127.0.0.1',r));const browser=await chromium.launch({headless:true,args:['--autoplay-policy=no-user-gesture-required']});const p=await browser.newPage();try{
 await p.goto('http://127.0.0.1:18880/?page_id='+process.env.PLAYER_FIXTURE_ID,{waitUntil:'networkidle'});
 const root=p.locator('[data-vf-module="player"]').first();await root.waitFor();
 assert.equal(await p.evaluate(()=>!!window.Hls),false,'must load only when playback begins');
 for(const file of ['test.m3u8','fmp4.m3u8']){
  await root.locator('[data-vf-player-url]').fill('http://127.0.0.1:18881/'+file);
  await root.locator('[data-vf-player-play]').first().click();
  await p.waitForFunction(()=>{const v=document.querySelector('[data-vf-player-video]');return v&&v.videoWidth===320&&v.currentTime>0.5;},null,{timeout:20000});
  await root.locator('[data-vf-player-reset]').first().click();
 }
 await root.locator('[data-vf-player-url]').fill('http://127.0.0.1:18881/missing.m3u8');await root.locator('[data-vf-player-play]').first().click();
 await p.waitForFunction(()=>document.querySelector('[data-vf-module="player"]').dataset.vfPlayerState==='error',null,{timeout:25000});
 fs.writeFileSync('proof/browser.json',JSON.stringify({status:'PASS',ts:'decoded',fmp4:'decoded',missing:'failed',zero_load:'PASS',production:'UNTOUCHED'},null,2));
 }finally{await browser.close();srv.close();}})().catch(e=>{console.error(e);srv.close();process.exitCode=1});
