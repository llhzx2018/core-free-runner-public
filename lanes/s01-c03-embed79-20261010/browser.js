const {chromium}=require('playwright');
const fs=require('fs');
const phase=process.argv[2]||'candidate';
const base='http://127.0.0.1:18880';
const cases=[];
function gate(ok,name,detail){cases.push({name,pass:!!ok,detail});}
(async()=>{
 const browser=await chromium.launch({headless:true});
 const context=await browser.newContext({viewport:{width:1440,height:1000},permissions:['clipboard-read','clipboard-write']});
 const page=await context.newPage();
 const demo=base+'/wp-content/plugins/vf-tool-m3u8/public/media/player-demo/demo.m3u8';
 const endpoint=new URL(base+'/');endpoint.search=new URLSearchParams({vf_m3u8_embed:'1',mode:'embed',tool:'player',m:Buffer.from(demo).toString('base64url'),autoplay:'1',controls:'1',locale:'en'});
 let response=await page.goto(endpoint.href,{waitUntil:'networkidle'});
 const expectedVersion=['baseline','rollback'].includes(phase)?process.env.SOURCE_VERSION:process.env.TARGET_VERSION;
 for(let attempt=0;attempt<12;attempt++){
  if(await page.locator('body').getAttribute('data-vf-embed-endpoint-version')===expectedVersion)break;
  await page.waitForTimeout(1000);response=await page.reload({waitUntil:'networkidle'});
 }
 gate(await page.locator('body').getAttribute('data-vf-embed-endpoint-version')===expectedVersion,'actual HTTP runtime version matches installed source '+phase);
 const direct=await page.evaluate(()=>({url:location.href,title:document.title,endpoint:document.body.dataset.vfPublicEmbed,version:document.body.dataset.vfEmbedEndpointVersion,status:document.querySelector('[data-vf-embed-status]')?.innerText,video:document.querySelector('video')?{readyState:document.querySelector('video').readyState,duration:document.querySelector('video').duration,currentTime:document.querySelector('video').currentTime,error:document.querySelector('video').error?.code}:null}));
 await page.screenshot({path:'proof/'+phase+'-direct.png'});
 fs.writeFileSync('proof/'+phase+'-direct.json',JSON.stringify({direct,status:response.status(),headers:response.headers()},null,2));
 if(['baseline','rollback'].includes(phase)){
  const u=new URL(endpoint);u.pathname='/m3u8-player/';await page.goto(u.href,{waitUntil:'networkidle'});const toolPath=await page.evaluate(()=>({url:location.href,title:document.title,endpoint:document.body.dataset.vfPublicEmbed}));
  await page.goto(base+'/embed/',{waitUntil:'networkidle'});const defaultBase=await page.locator('[data-vf-embed-generator]').getAttribute('data-vf-embed-base-url');const shareBase=await page.locator('[data-vf-embed-generator]').getAttribute('data-vf-embed-share-base-url');
  fs.writeFileSync('proof/embed-'+phase+'.json',JSON.stringify({status:cases.every(x=>x.pass)?'OBSERVED':'FAIL',cases,direct,toolPath,defaultBase,shareBase},null,2));await browser.close();return;
 }
 gate(direct.endpoint==='1'&&direct.version===process.env.TARGET_VERSION,'standalone endpoint owns explicit root request',direct);
 gate(response.headers()['x-robots-tag']==='noindex, nofollow','embed excluded from search indexing');
 try{await page.waitForFunction(()=>document.querySelector('video')?.readyState>=2,{},{timeout:15000});}catch(e){}
 const media=await page.locator('video').evaluate(v=>({readyState:v.readyState,duration:v.duration,currentTime:v.currentTime,error:v.error?.code}));
 gate(media.readyState>=2&&media.duration>0&&!media.error,'actual embedded demo media ready',media);
 await page.goto(base+'/embed/',{waitUntil:'networkidle'});
 const messages=[];await page.exposeFunction('recordEmbed',x=>messages.push(x));
 await page.evaluate(()=>window.addEventListener('message',e=>{if(e.data?.type==='vf:m3u8:embed-player-ready')window.recordEmbed(e.data);}));
 await page.getByRole('button',{name:'Run bundled example',exact:true}).click();
 try{await page.waitForFunction(()=>document.querySelector('iframe')?.contentDocument?.body?.dataset.vfPublicEmbed==='1',{},{timeout:15000});}catch(e){}
 const preview=await page.evaluate(()=>Array.from(document.querySelectorAll('iframe')).map(f=>({src:f.src,endpoint:f.contentDocument?.body?.dataset.vfPublicEmbed,video:f.contentDocument?.querySelector('video')?.readyState})));
 gate(preview.some(f=>f.endpoint==='1'),'generator iframe renders endpoint',preview);
 gate(preview.some(f=>new URL(f.src).pathname==='/m3u8-player/'),'unconfigured embed consumes mounted player path',preview);
 gate((await page.locator('[data-vf-embed-generator]').getAttribute('data-vf-embed-share-base-url'))==='/m3u8-player/','unconfigured share consumes mounted player path');
 try{await page.waitForFunction(()=>document.querySelector('[data-vf-embed-generator]')?.getAttribute('data-vf-embed-preview-state')==='success',{},{timeout:15000});}catch(e){}
 gate(messages.some(x=>x.owner==='vf-tool-m3u8'&&x.stage==='endpoint-ready'),'actual parent endpoint-ready handshake',messages.slice());
 gate(messages.some(x=>x.stage==='media-ready'&&x.readyState>=2),'actual preview media-ready handshake',messages);
 gate(await page.locator('[data-vf-embed-generator]').getAttribute('data-vf-embed-preview-state')==='success','success waits for decoded media');
 await page.locator('[data-vf-embed-mode-button="pro"]').click();
 await page.locator('[data-vf-embed-preset-button="fixed"]').click();
 gate(await page.locator('[data-vf-embed-width]').inputValue()==='640'&&await page.locator('[data-vf-embed-height]').inputValue()==='360','fixed preset updates dimensions');
 await page.locator('[data-vf-embed-autoplay]').selectOption('1');await page.locator('[data-vf-embed-controls]').selectOption('0');await page.locator('[data-vf-embed-loading]').selectOption('eager');
 for(const format of ['iframe','responsive','video','hlsjs','link']){
  await page.locator('[data-vf-embed-result-tab="'+format+'"]').click();await page.locator('[data-vf-embed-copy]').click();const code=await page.evaluate(()=>navigator.clipboard.readText());
  gate(!!code&&({iframe:code.includes('<iframe')&&code.includes('width="640"')&&code.includes('autoplay=1')&&code.includes('controls=0')&&code.includes('loading="eager"'),responsive:code.includes('padding-top:56.25%'),video:code.includes('<video'),hlsjs:code.includes('Hls.isSupported'),link:code.includes('mode=watch')})[format],'actual clipboard output '+format,{length:code.length});
 }
 const downloadPromise=page.waitForEvent('download');await page.locator('[data-vf-embed-export]').click();const download=await downloadPromise;const exported=JSON.parse(fs.readFileSync(await download.path(),'utf8'));gate(exported.artifactType==='vf-m3u8-embed-package'&&exported.embed.width==='640'&&exported.embed.controls===false,'actual downloaded JSON preserves parameters');
 const currentBase=await page.locator('[data-vf-embed-player-path]').inputValue();await page.locator('[data-vf-embed-player-path]').fill('/');await page.locator('[data-vf-embed-player-path]').dispatchEvent('input');gate((await page.locator('[data-vf-embed-output]').inputValue()).includes('src="'+base+'/?'),'explicit custom root remains respected');await page.locator('[data-vf-embed-player-path]').fill(currentBase);await page.locator('[data-vf-embed-player-path]').dispatchEvent('input');
 await page.locator('[data-vf-embed-preset-button="responsive"]').click();
 await page.screenshot({path:'proof/'+phase+'-generator.png',fullPage:true});
 for(const width of [1920,1440,1319,1024,768,390]){await page.setViewportSize({width,height:1000});const s=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth}));gate(s.scroll<=s.width+1,'embed no horizontal overflow '+width,s);await page.screenshot({path:'proof/'+phase+'-embed-'+width+'.png',fullPage:true});}
 for(const path of ['/','/m3u8-player/','/embed/','/m3u8-browser-stream-test/','/m3u8-playlist-checker/','/m3u8-segment-viewer/','/m3u8-encryption-detector/','/m3u8-downloader/','/m3u8-to-mp4/','/iptv-manager/','/m3u8-test-links/','/m3u8-backup-restore/']){const r=await page.goto(base+path);const ordinary=await page.evaluate(()=>({endpoint:document.body.dataset.vfPublicEmbed,h1:document.querySelector('h1')?.innerText}));gate(r.status()===200&&!ordinary.endpoint&&!!ordinary.h1,'normal route preserved '+path,{status:r.status(),...ordinary});}
 for(const path of ['/','/en/','/zh/','/m3u8-player/']){const u=new URL(endpoint);u.pathname=path;u.searchParams.set('locale',path==='/zh/'?'zh':'en');const r=await page.goto(u.href);const state=await page.evaluate(()=>({endpoint:document.body.dataset.vfPublicEmbed,lang:document.documentElement.lang,controls:document.querySelector('video')?.controls}));gate(r.status()===200&&state.endpoint==='1','embed explicit route '+path,state);}
 const missing=new URL(endpoint);missing.searchParams.set('m',Buffer.from('javascript:alert(1)').toString('base64url'));await page.goto(missing.href);gate((await page.locator('[data-vf-embed-status]').getAttribute('data-state'))==='error','invalid source explicit error');
 if(phase==='clean'){
  await page.goto(base+'/wp-login.php');await page.locator('#user_login').fill('admin');await page.locator('#user_pass').fill('Synthetic-Only-Update-54!');await page.locator('#wp-submit').click();await page.waitForURL('**/wp-admin/**');
  const cookies=await context.cookies();const users=await page.goto(base+'/wp-admin/users.php');await page.locator('#wpbody-content').waitFor();gate(cookies.some(x=>x.name.startsWith('wordpress_logged_in_'))&&users.status()===200&&(await page.getByRole('heading',{name:'Users',exact:true}).count())===1,'fresh installation native authenticated admin access');
  await page.goto(base+'/wp-admin/install.php');gate((await page.locator('body').innerText()).includes('Already Installed'),'setup revisit safely locked');
 }
 const result={status:cases.every(x=>x.pass)?'PASS':'FAIL',phase,cases,source_sha:process.env.TARGET_SHA,source_tree:process.env.TARGET_TREE};fs.writeFileSync('proof/embed-'+phase+'.json',JSON.stringify(result,null,2));console.log(JSON.stringify({phase,status:result.status,failed:cases.filter(x=>!x.pass)}));await browser.close();
})().catch(e=>{fs.writeFileSync('proof/embed-'+phase+'-error.json',JSON.stringify({status:'FAIL',error:String(e)}));console.error(e);process.exitCode=1;});
