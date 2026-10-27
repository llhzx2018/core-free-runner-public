const {chromium}=require('playwright'),fs=require('fs'),assert=require('node:assert/strict');
const phase=process.argv[2],fixed=phase==='after',base='http://127.0.0.1:18880',out={pages:{},players:{}},rows=[];
const norm=s=>s.replaceAll('1.35.213','1.35.211').replaceAll('135213','135211');
(async()=>{
 const b=await chromium.launch(),c=await b.newContext({viewport:{width:1440,height:1000}}),errors=[];
 for(const path of ['/','/zh/','/sitemap/','/zh/sitemap/','/m3u8-playlist-checker/','/zh/m3u8-backup-restore/']){
  const p=await c.newPage();await p.goto(base+path,{waitUntil:'networkidle'});out.pages[path]=norm(await p.locator('#content').innerHTML());await p.close();
 }
 for(const lang of ['en','zh']){
  const path=(lang==='zh'?'/zh':'')+'/m3u8-player/',p=await b.newPage({viewport:{width:1440,height:1000}});p.on('pageerror',e=>errors.push(e.message));const media=[];
  p.on('request',r=>{if(/\.(m3u8|m4s|ts|mp4)(?:\?|$)/.test(r.url()))media.push(r.url());});
  await p.goto(base+path,{waitUntil:'networkidle'});
  // Public synthetic fixture, including the populated state missed by the prior QA.
  await p.evaluate(()=>{
    const root=document.querySelector('[data-vf-module="player"]');
    const rows=Array.from({length:6},(_,i)=>({name:i===0?'A long authorized sample name — master playlist playback test':'Sample stream '+(i+1),url:'https://streams.example.invalid/synthetic/'+i+'/index.m3u8',type:'HLS',tag:'player-history',favorite:i===5,savedAt:'2026-10-27T00:00:00Z'}));
    window.VFM3U8PlayerHistory.write(rows,root);
  });
  await p.reload({waitUntil:'networkidle'});
  const root=p.locator('[data-vf-module="player"]'),input=root.locator('[data-vf-player-url]'),video=root.locator('video');
  out.players[lang]={
   h1:await p.locator('h1').allTextContents(),
   head:await p.locator('title,link[rel=canonical],link[rel=alternate][hreflang],meta[name=robots],meta[name=description]').evaluateAll(es=>es.map(e=>e.outerHTML)),
   header:norm(await p.locator('[data-vf-theme-shell=header]').innerHTML()),footer:norm(await p.locator('[data-vf-theme-shell=footer]').innerHTML()),
   controls:await root.locator('input,button,select,video').evaluateAll(es=>es.map(e=>({tag:e.tagName,attrs:[...e.attributes].filter(a=>a.name.startsWith('data-vf-')||['type','controls','preload'].includes(a.name)).map(a=>[a.name,a.value])})))
  };
  assert.equal(media.length,0,'no media requested on page load');assert.equal(await video.getAttribute('preload'),'none');
  for(const width of [1440,1024]){
   await p.setViewportSize({width,height:1000});
   if(fixed){
    assert.equal(await p.locator('.vf-tool-breadcrumb').count(),0);assert.equal(await p.locator('.vf-tool-hero-actions').count(),0);
    assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
    const h=await p.locator('h1').boundingBox(),f=await p.locator('.vf-tool-runtime-stage-frame').boundingBox(),i=await input.boundingBox();
    await p.screenshot({path:`proof/player-${lang}-${width}.png`,fullPage:true});
    fs.writeFileSync(`proof/layout-${lang}-${width}.json`,JSON.stringify({h,f,i,ancestors:await input.evaluate(e=>{const rows=[];for(let p=e;p&&p.tagName!=='BODY';p=p.parentElement){const s=getComputedStyle(p),r=p.getBoundingClientRect();rows.push({tag:p.tagName,cls:p.className,y:r.y,h:r.height,padding:s.padding,margin:s.margin,gap:s.gap,display:s.display});}return rows;})},null,2));
    assert.ok(Math.abs(h.x-f.x)<2,'title/workspace common baseline');const cta=await p.locator('.vf-data-cta>.container-wide').boundingBox();assert.ok(Math.abs(cta.x-f.x)<2,'CTA follows the same gutter and content rail');assert.ok(i.y<500,`input visible in first desktop viewport: ${i.y}`);
    const styles=await p.locator('.vf-tool-runtime-stage-frame').evaluate(e=>{const s=getComputedStyle(e);return{border:s.borderTopWidth,shadow:s.boxShadow,overflow:s.overflow,padding:s.padding}});
    assert.equal(styles.border,'0px');assert.equal(styles.shadow,'none');assert.equal(styles.padding,'0px');assert.equal(styles.overflow,'visible');
    assert.ok(await root.locator('[data-vf-player-view="simple"]').isVisible());assert.ok(await root.locator('[data-vf-player-view="pro"]').isVisible());
    for(const selector of ['.vf-tool-steps-list li>div','.vf-tool-related-card>div'])for(const el of await p.locator(selector).all()){assert.ok((await el.boundingBox()).width>200,'support copy must not occupy the old index column');}
    await p.screenshot({path:`proof/player-${lang}-${width}.png`,fullPage:true});
    const stage=await root.locator('.vf-stage').boundingBox(),library=await root.locator('.vf-user-card').boundingBox(),screen=await root.locator('.vf-screen').boundingBox();
    assert.ok(screen.height<=481,'video must not dominate the entire viewport');
    assert.equal(await root.locator('.vf-recent-item:visible').count(),5,'real populated five-row library');
    assert.equal(await root.locator('.vf-row-actions:visible button').count(),20,'all existing row actions remain discoverable');
    if(width===1440){assert.ok(library.x>stage.x+stage.width,'library is secondary right rail');assert.ok(Math.abs(library.y-stage.y)<2,'media and library share start');}
    else assert.ok(library.y>=stage.y+stage.height,'tablet library follows the media');
    assert.equal(await p.locator('.vf-m3u8-launchbar__steps').isVisible(),false,'avoid repeated steps before input');
    assert.ok(await p.locator('.vf-m3u8-launchbar__back').isVisible(),'all tools navigation retained');
    rows.push({kind:'desktop-layout',lang,width,inputY:i.y,rail:f.width,stage,library,screen,status:'PASS'});
   }else await p.screenshot({path:`proof/before-player-${lang}-${width}.png`,fullPage:true});
  }
  if(fixed){
   const before=JSON.parse(fs.readFileSync('proof/before-public.json'));assert.deepEqual(out.players[lang],before.players[lang],'canonical Head/shared shell/Provider control contract unchanged');
   // Exercise Provider-owned rows, prompts, persistence and export through real UI.
   const history=root.locator('[data-vf-player-recent-list]');
   p.once('dialog',d=>d.accept('Renamed synthetic stream'));
   await history.locator('[data-vf-player-rename-url]').first().click();
   assert.ok((await history.innerText()).includes('Renamed synthetic stream'));
   await history.locator('[data-vf-player-toggle-favorite-url]').first().click();
   await root.locator('[data-vf-player-list-tab="favorites"]').click();
   assert.equal(await root.locator('[data-vf-player-favorite-list] .vf-recent-item').count(),2);
   await root.locator('[data-vf-player-favorite-list] [data-vf-player-toggle-favorite-url]').first().click();
   await root.locator('[data-vf-player-list-tab="recent"]').click();
   const count=await history.locator('.vf-recent-item').count();
   await history.locator('[data-vf-player-remove-url]').first().click();
   assert.equal(await history.locator('.vf-recent-item').count(),count-1);
   const download=p.waitForEvent('download');await root.locator('[data-vf-player-export]').click();
   const exported=JSON.parse(fs.readFileSync(await (await download).path(),'utf8'));assert.equal(exported.streams.length,5);
   await p.reload({waitUntil:'networkidle'});assert.equal(await history.locator('.vf-recent-item').count(),4,'saved library persists');
   await p.setViewportSize({width:1440,height:1000});
   await p.screenshot({path:`proof/player-${lang}-library.png`,fullPage:true});
   await root.locator('[data-vf-player-play]').click();await p.waitForTimeout(250);assert.equal(media.length,0,'empty action must not fetch media');assert.ok((await root.innerText()).match(/URL|链接|地址/i));
   await input.fill(base+'/synthetic-missing.m3u8');await root.locator('[data-vf-player-play]').click();
   await p.waitForFunction(()=>{let r=document.querySelector('[data-vf-module="player"]');return /error|failed|404|失败|错误/i.test(r.innerText);},{timeout:20000});
   assert.ok(await root.locator('[data-vf-player-reset]').isEnabled());await root.locator('[data-vf-player-reset]').click();assert.equal(await input.inputValue(),'');
   await root.locator('[data-vf-player-view="pro"]').click();assert.equal(await root.locator('[data-vf-player-view="pro"]').getAttribute('aria-selected'),'true');
   assert.equal(await root.locator('.vf-user-card').isVisible(),false);
   const proStage=await root.locator('.vf-stage').boundingBox(),pro=await root.locator('.vf-pro-tools').boundingBox();
   assert.ok(proStage.width>1000&&pro.width>1000,'Pro evidence and video remain full width');
   await root.locator('[data-vf-player-check]').click();await p.waitForTimeout(300);assert.ok(await root.locator('[data-vf-player-check]').isEnabled());
   await root.locator('[data-vf-player-view="simple"]').click();assert.equal(await root.locator('[data-vf-player-view="simple"]').getAttribute('aria-selected'),'true');
   await root.locator('[data-vf-player-sample]').first().click();
   await p.waitForFunction(()=>{const v=document.querySelector('[data-vf-player-video]');return v&&v.readyState>=2&&v.currentTime>0;},null,{timeout:30000});
   const playback=await video.evaluate(v=>({readyState:v.readyState,time:v.currentTime,width:v.videoWidth,height:v.videoHeight,error:v.error?.code||0}));assert.ok(playback.width>0&&playback.height>0);assert.equal(playback.error,0);
   await p.screenshot({path:`proof/player-${lang}-playing.png`,fullPage:true});
   await root.locator('[data-vf-player-reset]').click();assert.equal(await input.inputValue(),'');assert.equal(await video.getAttribute('src'),null);
   const faq=p.locator('.vf-tool-faq-list details').nth(1);await faq.locator('summary').press('Enter');assert.equal(await faq.getAttribute('open'),'');
   // Empty-library view has no reserved sidebar; no state is written to WordPress.
   await p.evaluate(()=>{const h=window.VFM3U8PlayerHistory;localStorage.removeItem(h.store);localStorage.removeItem(h.lastInputStore);});
   await p.reload({waitUntil:'networkidle'});
   assert.equal(await root.locator('.vf-user-card').isVisible(),false);
   assert.ok((await root.locator('.vf-stage').boundingBox()).width>1000);
   await p.screenshot({path:`proof/player-${lang}-empty.png`,fullPage:true});
   rows.push({kind:'populated-library-actions-persistence-export-empty-error-reset-pro-capability-real-sample-faq-keyboard',lang,playback,status:'PASS'});
  }
  await p.close();
 }
 if(fixed){assert.deepEqual(out.pages,JSON.parse(fs.readFileSync('proof/before-public.json')).pages,'six neighboring public outputs remain unchanged');}
 assert.deepEqual(errors,[]);fs.writeFileSync('proof/'+phase+'-public.json',JSON.stringify(out));fs.writeFileSync('proof/'+phase+'-results.json',JSON.stringify({status:'PASS',phase,rows,production:'UNTOUCHED'},null,2));console.log('PLAYER_'+phase.toUpperCase()+'_PASS');await b.close();
})().catch(e=>{console.error(e);process.exit(1)});
