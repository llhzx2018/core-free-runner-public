const {chromium}=require('playwright-core'),fs=require('fs');
const base=`http://127.0.0.1:${process.env.PORT||'18518'}/`,ids=JSON.parse(fs.readFileSync(process.env.EVID+'/ids.json','utf8')),A=(v,m)=>{if(!v)throw Error(m)};
async function overflow(p,label){const n=await p.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth);A(n===0,label+' overflow='+n);return n}
const pixel='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=';
(async()=>{
  const b=await chromium.launch({headless:true,executablePath:process.env.CHROME,args:['--no-sandbox']});
  const admin=await b.newContext({viewport:{width:390,height:844}});
  const login=await admin.request.post(base+'api.php?action=login',{data:{password:process.env.ADMIN_PASS}});A(login.ok()&&(await login.json()).ok,'admin login');
  let refreshCalls=0;
  await admin.route('**/resource-cover-refresh.php',async route=>{refreshCalls++;await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({ok:true,processed:1,results:[{id:Number(ids.hydrate),success:true,cover:{url:pixel}}]})})});
  const p=await admin.newPage();p.setDefaultTimeout(10000);const out={source:process.env.SOURCE,base:process.env.BASE};
  await p.goto(base+'channels.php',{waitUntil:'domcontentloaded'});
  A(await p.getByText('VF 私人频道',{exact:true}).count()===1,'private channel missing admin');
  const tree=(await p.locator('.vf-category-section .vf-category-tree').textContent())||'';A(tree.includes('频道'),'channel semantic category missing');A(!tree.includes('YouTube'),'provider leaked into category tree '+tree);
  const row=p.locator(`[data-asset-row="${ids.channel}"]`);A(await row.count()===1,'channel row missing');const small=(await row.locator('.vf-asset-copy small').textContent())||'';A(small.includes('YouTube')&&small.includes('频道'),'channel provider/kind '+small);A(await row.locator('.vf-asset-icon img').count()===1,'channel cached cover missing');A((await p.locator('body').textContent()).includes('自动获取 · 可手工覆盖'),'auto cover copy missing');
  await p.waitForFunction(id=>!!document.querySelector(`[data-asset-row="${id}"] .vf-asset-icon img`),ids.hydrate,{timeout:10000});A(refreshCalls>0,'auto hydration endpoint not called');
  out.channels390={tree,rowMeta:small,refreshCalls,overflow:await overflow(p,'channels390')};await p.screenshot({path:process.env.EVID+'/channels-390.png',fullPage:true});
  await p.setViewportSize({width:1440,height:900});await p.goto(base+'channels.php',{waitUntil:'domcontentloaded'});out.channels1440={overflow:await overflow(p,'channels1440')};
  await p.setViewportSize({width:390,height:844});await p.goto(base+'watch.php',{waitUntil:'domcontentloaded'});const movie=p.locator(`[data-asset-row="${ids.watch}"]`);A(await movie.count()===1,'watch card missing');const meta=(await movie.locator('.vf-watch-copy small').textContent())||'';A(meta.includes('电影')&&meta.includes('爱一帆'),'movie kind/provider '+meta);A(await movie.locator('.vf-watch-poster img').count()===1,'movie cover missing');out.watch390={meta,overflow:await overflow(p,'watch390')};await p.screenshot({path:process.env.EVID+'/watch-390.png',fullPage:true});
  const pub=await b.newContext({viewport:{width:390,height:844}}),q=await pub.newPage();q.setDefaultTimeout(10000);
  await q.goto(base+'channels.php',{waitUntil:'domcontentloaded'});A(await q.getByText('VF 私人频道',{exact:true}).count()===0,'PRIVATE CHANNEL LEAK');A(await q.getByText('VF 自动触发频道',{exact:true}).count()===0,'PRIVATE HYDRATE CHANNEL LEAK');const pc=await pub.request.get(base+`resource-cover.php?id=${ids.channel}`);A(pc.status()!==200,'PRIVATE COVER LEAK '+pc.status());const rr=await pub.request.post(base+'resource-cover-refresh.php',{form:{ids:JSON.stringify([ids.channel]),csrf:'anonymous'}});A(rr.status()===403,'anonymous refresh status '+rr.status());
  await q.goto(base+'watch.php',{waitUntil:'domcontentloaded'});A(await q.getByText('VF 公开电影',{exact:true}).count()===1,'public movie missing');const wc=await pub.request.get(base+`resource-cover.php?id=${ids.watch}`);A(wc.status()===200,'public cover '+wc.status());A((wc.headers()['content-type']||'').startsWith('image/'),'public cover mime');
  out.privacy={privateChannel:'HIDDEN',privateCoverStatus:pc.status(),anonymousRefreshStatus:rr.status(),publicMovie:'VISIBLE',publicCoverStatus:wc.status(),overflow:await overflow(q,'public watch')};out.verdict='PASS';fs.writeFileSync(process.env.EVID+'/browser.json',JSON.stringify(out,null,2));console.log('P01_CONTENT_KINDS_AUTO_COVERS=PASS');console.log(JSON.stringify(out));
  await pub.close();await admin.close();await b.close();
})().catch(e=>{console.error(e);process.exit(1)});
