const {chromium}=require('playwright'),fs=require('fs'),assert=require('node:assert/strict');
const phase=process.argv[2],fixed=phase==='after',base='http://127.0.0.1:18880',out={pages:{},players:{}},rows=[];
const norm=s=>s.replaceAll('1.35.215','1.35.213').replaceAll('135215','135213');
(async()=>{
 const b=await chromium.launch(),c=await b.newContext({viewport:{width:1440,height:1000}}),errors=[];
 for(const path of ['/','/zh/','/sitemap/','/zh/sitemap/','/m3u8-playlist-checker/','/zh/m3u8-backup-restore/','/m3u8-downloader/','/zh/m3u8-to-mp4/']){
  const p=await c.newPage();await p.goto(base+path,{waitUntil:'networkidle'});out.pages[path]=norm(await p.locator('#content').innerHTML());await p.close();
 }
 for(const lang of ['en','zh']){
  const path=(lang==='zh'?'/zh':'')+'/m3u8-player/',p=await b.newPage({viewport:{width:1440,height:1000}});p.on('pageerror',e=>errors.push(e.message));const media=[];
  p.on('request',r=>{if(/\.(m3u8|m4s|ts|mp4)(?:\?|$)/.test(r.url()))media.push(r.url());});
  await p.goto(base+path,{waitUntil:'networkidle'});
  await p.evaluate(()=>{const root=document.querySelector('[data-vf-module="player"]');window.VFM3U8PlayerHistory.write(Array.from({length:6},(_,i)=>({name:i===0?'Long authorized sample — original master playlist':'Sample stream '+(i+1),url:'https://streams.example.invalid/synthetic/'+i+'/index.m3u8',type:'HLS',tag:'player-history',favorite:i===5,savedAt:'2026-10-28T00:00:00Z'})),root);});
  await p.reload({waitUntil:'networkidle'});
  const root=p.locator('[data-vf-module="player"]'),input=root.locator('[data-vf-player-url]'),video=root.locator('video'),host=p.locator('[data-vf-player-presentation]'),toggle=p.locator('[data-vf-player-library-toggle]');
  out.players[lang]={h1:await p.locator('h1').allTextContents(),head:await p.locator('title,link[rel=canonical],link[rel=alternate][hreflang],meta[name=robots],meta[name=description]').evaluateAll(es=>es.map(e=>e.outerHTML)),header:norm(await p.locator('[data-vf-theme-shell=header]').innerHTML()),footer:norm(await p.locator('[data-vf-theme-shell=footer]').innerHTML()),controls:await root.locator('input,button,select,video').evaluateAll(es=>es.map(e=>({tag:e.tagName,attrs:[...e.attributes].filter(a=>a.name.startsWith('data-vf-')||['type','controls','preload'].includes(a.name)).map(a=>[a.name,a.value])})))};
  assert.equal(media.length,0);assert.equal(await video.getAttribute('preload'),'none');
  if(fixed){await host.waitFor({state:'visible'});assert.equal(await host.getAttribute('data-vf-player-enhanced'),'1');assert.equal(await host.getAttribute('data-vf-player-stock-ready'),'1','known neutral default prompt concealed in both languages');assert.equal(await host.getAttribute('data-vf-player-stock-empty-detail'),'1','stock implementation detail is secondary to playback');assert.equal(await toggle.count(),1);assert.ok(await toggle.isVisible());assert.equal(await root.locator('.vf-user-card').isVisible(),false);assert.equal(await toggle.getAttribute('aria-expanded'),'false');assert.equal(await root.locator('[data-vf-player-simple-panel]').getAttribute('hidden'),null,'Theme never changes Provider hidden policy');assert.ok(await p.locator('#'+await toggle.getAttribute('aria-controls')).count());}
  for(const width of [1440,1024]){
   await p.setViewportSize({width,height:1000});
   await p.screenshot({path:`proof/${fixed?'':'before-'}player-${lang}-${width}.png`,fullPage:true});
   if(fixed){
    const f=await p.locator('.vf-tool-runtime-stage-frame').boundingBox(),h=await p.locator('h1').boundingBox(),i=await input.boundingBox(),stage=await root.locator('.vf-stage').boundingBox(),command=await root.locator('.vf-player-command').boundingBox();
    fs.writeFileSync(`proof/layout-${lang}-${width}.json`,JSON.stringify({f,h,i,stage,command,identity:await host.getAttribute('data-vf-player-stock-identity'),ready:await host.getAttribute('data-vf-player-stock-ready')},null,2));
    assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
    assert.ok(Math.abs((h.x+h.width/2)-(f.x+f.width/2))<2,'hero centered over complete media rail');
    assert.ok(stage.width>=f.width-2,'video retains the entire content width');assert.ok(Math.abs(stage.x-command.x)<2);assert.ok(Math.abs(stage.y-(command.y+command.height))<2,'input connects directly to video');
    assert.ok(i.y<400,'primary input in first viewport');assert.ok(stage.y<500,'media begins before half viewport');
    assert.equal(await p.locator('.vf-m3u8-launchbar').isVisible(),false);assert.equal(await p.locator('.vf-data-cta').count(),0,'default duplicate CTA omitted when related routes exist');
    for(const sel of ['.vf-player-support-disclosure','.vf-player-workflow-disclosure']){assert.equal(await p.locator(sel).getAttribute('open'),null);assert.ok(await p.locator(sel+'>summary').isVisible());}
    for(const summary of await p.locator('.vf-tool-faq-list summary').all()){const box=await summary.boundingBox();assert.ok(box.height<130,'FAQ text must use the complete row after decorative index removal');}
    assert.ok(await root.locator('[data-vf-player-view="simple"]').isVisible());assert.ok(await root.locator('[data-vf-player-view="pro"]').isVisible());
    rows.push({kind:'full-width-layout',lang,width,inputY:i.y,stage,status:'PASS'});
   }
  }
  if(fixed){
   const before=JSON.parse(fs.readFileSync('proof/before-public.json'));assert.deepEqual(out.players[lang],before.players[lang],'canonical Head/shared shell/Provider controls and DOM order retained');
   await toggle.press('Enter');assert.equal(await toggle.getAttribute('aria-expanded'),'true');assert.ok(await root.locator('.vf-user-card').isVisible());assert.equal(await root.locator('.vf-recent-item:visible').count(),5);assert.equal(await root.locator('.vf-row-actions:visible button').count(),20);
   const stage=await root.locator('.vf-stage').boundingBox(),lib=await root.locator('.vf-user-card').boundingBox();assert.ok(lib.y>=stage.y+stage.height);assert.ok(lib.width>=stage.width-2,'history is below full-width media');
   await p.screenshot({path:`proof/player-${lang}-library.png`,fullPage:true});
   const history=root.locator('[data-vf-player-recent-list]'),rename=history.locator('[data-vf-player-rename-url]').first(),renameURL=await rename.getAttribute('data-vf-player-rename-url');
   const dialogPromise=p.waitForEvent('dialog'),renameClick=rename.click(),dialog=await dialogPromise;assert.equal(dialog.type(),'prompt');await dialog.accept('QA-53172');await renameClick;
   await history.getByText('QA-53172',{exact:true}).waitFor({state:'visible',timeout:15000});
   const renamed=await p.evaluate(url=>window.VFM3U8PlayerHistory.find(url,document.querySelector('[data-vf-module="player"]')),renameURL);assert.equal(renamed.name,'QA-53172','the actual persisted row has the authored name');
   await history.locator('[data-vf-player-toggle-favorite-url]').first().click();await root.locator('[data-vf-player-list-tab="favorites"]').click();assert.equal(await root.locator('[data-vf-player-favorite-list] .vf-recent-item').count(),2);
   await root.locator('[data-vf-player-favorite-list] [data-vf-player-toggle-favorite-url]').first().click();await root.locator('[data-vf-player-list-tab="recent"]').click();const count=await history.locator('.vf-recent-item').count();await history.locator('[data-vf-player-remove-url]').first().click();assert.equal(await history.locator('.vf-recent-item').count(),count-1);
   const download=p.waitForEvent('download');await root.locator('[data-vf-player-export]').click();assert.equal(JSON.parse(fs.readFileSync(await(await download).path(),'utf8')).streams.length,5);
   await toggle.press('Space');assert.equal(await root.locator('.vf-user-card').isVisible(),false);assert.equal(await root.locator('[data-vf-player-simple-panel]').getAttribute('hidden'),null);
   await p.reload({waitUntil:'networkidle'});assert.equal(await history.locator('.vf-recent-item').count(),4);assert.equal(await toggle.getAttribute('aria-expanded'),'false');assert.equal(await root.locator('.vf-user-card').isVisible(),false);
   await p.setViewportSize({width:1440,height:1000});
   await root.locator('[data-vf-player-play]').click();await p.waitForTimeout(100);assert.equal(media.length,0);assert.ok(await root.locator('[data-vf-player-status]').isVisible(),'real missing-input feedback cannot be concealed');
   await input.fill(base+'/synthetic-missing.m3u8');await root.locator('[data-vf-player-play]').click();await p.waitForFunction(()=>/error|failed|404|失败|错误/i.test(document.querySelector('[data-vf-module="player"]').innerText),null,{timeout:20000});assert.ok(await root.locator('[data-vf-player-status]').isVisible());
   await root.locator('[data-vf-player-reset]').click();assert.equal(await input.inputValue(),'');
   await root.locator('[data-vf-player-view="pro"]').click();await toggle.waitFor({state:'hidden'});assert.equal(await root.locator('.vf-user-card').isVisible(),false);assert.ok((await root.locator('.vf-pro-tools').boundingBox()).width>1000);await root.locator('[data-vf-player-check]').click();
   await root.locator('[data-vf-player-view="simple"]').click();await toggle.waitFor({state:'visible'});
   await root.locator('[data-vf-player-sample]').first().click();await p.waitForFunction(()=>{const v=document.querySelector('[data-vf-player-video]');return v.readyState>=2&&v.currentTime>0;},null,{timeout:30000});
   const playback=await video.evaluate(v=>({readyState:v.readyState,time:v.currentTime,width:v.videoWidth,height:v.videoHeight,error:v.error?.code||0}));assert.ok(playback.width>0);assert.equal(playback.error,0);assert.ok((await video.boundingBox()).height<=(await root.locator('.vf-screen').boundingBox()).height+1);await p.screenshot({path:`proof/player-${lang}-playing.png`,fullPage:true});
   await root.locator('[data-vf-player-reset]').click();assert.equal(await input.inputValue(),'');assert.equal(await video.getAttribute('src'),null);
   for(const sel of ['.vf-player-support-disclosure','.vf-player-workflow-disclosure']){await p.locator(sel+'>summary').press('Enter');assert.equal(await p.locator(sel).getAttribute('open'),'');assert.ok((await p.locator(sel).innerText()).length>100);await p.locator(sel+'>summary').press('Enter');assert.equal(await p.locator(sel).getAttribute('open'),null);}
   const faq=p.locator('.vf-tool-faq-list details').nth(1);await faq.locator('summary').press('Enter');assert.equal(await faq.getAttribute('open'),'');
   // Separate Theme host contract: authored Provider projection is input, not
   // an edit to the running Provider's canonical configuration. Domain actions
   // above use the complete, unmodified Provider runtime on real WordPress.
   const probe=await b.newPage({viewport:{width:1440,height:1000}});
   await probe.route('**/wp-content/plugins/vf-tool-m3u8/**',route=>route.request().resourceType()==='script'?route.abort():route.continue());
   await probe.route(base+path,async route=>{const response=await route.fetch();let html=await response.text();const description=/(<[^>]+data-vf-tool-description[^>]*>)[^<]*/,detail=/(<[^>]+data-vf-player-empty-detail[^>]*>)[^<]*/;assert.ok(description.test(html)&&detail.test(html));html=html.replace(description,'$1QA-Description-53172').replace(detail,'$1QA-Empty-53172');await route.fulfill({response,body:html});});
   await probe.goto(base+path,{waitUntil:'networkidle'});await probe.locator('[data-vf-player-presentation][data-vf-player-enhanced="1"]').waitFor();
   await probe.getByText('QA-Description-53172',{exact:true}).waitFor({state:'visible'});await probe.getByText('QA-Empty-53172',{exact:true}).waitFor({state:'visible'});
   fs.writeFileSync(`proof/host-custom-copy-${lang}.json`,JSON.stringify({status:'PASS',scope:'Theme host consumes authored Provider DOM projection; Provider JS intentionally omitted only in this separate fixture',description:'VISIBLE_UNCHANGED',emptyDetail:'VISIBLE_UNCHANGED',providerBusinessProof:'COMPLETE_UNMODIFIED_RUNTIME_ABOVE'}));await probe.close();
   await p.evaluate(()=>{const h=window.VFM3U8PlayerHistory;localStorage.removeItem(h.store);localStorage.removeItem(h.lastInputStore);});await p.reload({waitUntil:'networkidle'});await toggle.waitFor({state:'hidden'});assert.equal(await root.locator('.vf-user-card').isVisible(),false);assert.ok((await root.locator('.vf-stage').boundingBox()).width>1000);await p.screenshot({path:`proof/player-${lang}-empty.png`,fullPage:true});
   rows.push({kind:'disclosure-keyboard-library-actions-persistence-export-real-feedback-pro-playback-custom-copy',lang,playback,status:'PASS'});
  }
  await p.close();
 }
 if(fixed)assert.deepEqual(out.pages,JSON.parse(fs.readFileSync('proof/before-public.json')).pages,'eight neighboring outputs unchanged');
 assert.deepEqual(errors,[]);fs.writeFileSync('proof/'+phase+'-public.json',JSON.stringify(out));fs.writeFileSync('proof/'+phase+'-results.json',JSON.stringify({status:'PASS',phase,rows,production:'UNTOUCHED'},null,2));console.log('PLAYER_'+phase.toUpperCase()+'_PASS');await b.close();
})().catch(e=>{console.error(e);process.exit(1)});
