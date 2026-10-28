'use strict';
// One-time read-only live station PLAY probe, user-agent Chrome.
// A metadata/HTTP/CORS success is NOT considered playing. Output is metadata
// only, no stream capture/storage/download or rebroadcast.
const fs=require('node:fs');
const assert=require('node:assert/strict');
const {chromium}=require('playwright-core');
const [reportPath,bundlePath]=process.argv.slice(2);
const report=JSON.parse(fs.readFileSync(reportPath,'utf8'));
assert.ok(fs.statSync(bundlePath).size>300000);
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true,
  args:['--no-sandbox','--autoplay-policy=no-user-gesture-required']});
 try{
  const ctx=await browser.newContext({viewport:{width:800,height:600}});
  const page=await ctx.newPage();
  page.on('pageerror',err=>console.error('RADIO_CHROME_PAGE_ERROR',err.message.slice(0,180)));
  await page.goto('http://127.0.0.1:18818/',{waitUntil:'domcontentloaded'});
  await page.addScriptTag({path:bundlePath});
  assert.equal(await page.evaluate(()=>window.Hls?.isSupported?.()),true);
  for(const entry of report.results){
    const items=(entry.checked||[]).filter(x=>x.stream_url&&x.stream_probe==='http-ok').slice(0,2);
    for(const station of items){
     const result=await page.evaluate(async station=>{
      const audio=document.createElement('audio');audio.preload='none';
      audio.autoplay=false;audio.muted=true;
      document.body.append(audio);
      const errors=[];let hls=null,ready=false;
      const note=x=>{if(errors.length<4)errors.push(String(x).slice(0,190));};
      let progress=0,started=false,result='timeout',code=0;
      audio.addEventListener('error',()=>{note('audio_error_'+(audio.error?.code||'unknown'));});
      audio.addEventListener('playing',()=>{started=true;});
      try{
       if(station.stream_kind==='HLS'){
        if(!window.Hls.isSupported())return {result:'no-MSE'};
        hls=new window.Hls({enableWorker:false,lowLatencyMode:false,maxBufferLength:6,
          maxMaxBufferLength:12,backBufferLength:3});
        hls.on(window.Hls.Events.ERROR,(_name,data)=>{
          if(data?.fatal)note('fatal_'+data.type+'_'+data.details);
        });
        hls.on(window.Hls.Events.MEDIA_ATTACHED,()=>hls.loadSource(station.stream_url));
        hls.on(window.Hls.Events.MANIFEST_PARSED,()=>{ready=true;audio.play().catch(e=>note('play_'+e.name));});
        hls.attachMedia(audio);
       }else{
        audio.src=station.stream_url;ready=true;
        audio.play().catch(e=>note('play_'+e.name));
       }
       const start=performance.now();
       while(performance.now()-start<12500){
        await new Promise(r=>setTimeout(r,250));
        progress=audio.currentTime;
        if(progress>0.75&&started&&!audio.paused){result='audible-timeline';break;}
        if(errors.some(x=>x.startsWith('fatal_'))){result='fatal';break;}
        if(audio.error){code=audio.error.code;result='media-error';break;}
       }
      }catch(e){result='exception';note(e.message);}
      finally{
       try{hls?.destroy();}catch(_){}
       audio.pause();audio.removeAttribute('src');audio.load();audio.remove();
      }
      return {result,manifestReady:ready,mediaPlayingEvent:started,
         currentTime:Number(progress.toFixed(3)),mediaErrorCode:code,errors};
     },station);
     console.log("RADIO_CHROME_PLAY",entry.case,JSON.stringify({
      name:station.name,kind:station.stream_kind,host:station.stream_host,...result
     }));
     entry.chrome=entry.chrome||[];
     entry.chrome.push({name:station.name,kind:station.stream_kind,
      host:station.stream_host,...result});
    }
  }
  fs.writeFileSync('p01-radio-chrome-evidence.json',JSON.stringify({
   utc:new Date().toISOString(),
   note:'Headless Chrome live external audio timeline; short single point-in-time check only',
   results:report.results.map(x=>({case:x.case,chrome:x.chrome||[]}))
  },null,2));
  console.log('RADIO_CHROME_REAL_AUDIO_CHECKS=COMPLETE');
 }finally{await browser.close();}
})().catch(e=>{console.error('RADIO_CHROME_INFRA_FAIL',e);process.exitCode=1;});
