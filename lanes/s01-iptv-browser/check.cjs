const {chromium}=require('playwright'),fs=require('fs');
(async()=>{
 const b=await chromium.launch({headless:true});let checks=[];
 try{for(const lang of ['en','zh']){for(const width of [1024,1440]){
  const ctx=await b.newContext({viewport:{width,height:900},acceptDownloads:true});
  const p=await ctx.newPage();const url='http://127.0.0.1:18880'+(lang==='zh'?'/zh':'')+'/iptv-manager/';
  const response=await p.goto(url,{waitUntil:'networkidle'});if(!response.ok())throw Error('route '+url+' '+response.status());
  const root=p.locator('[data-vf-iptv-manager]').first();await root.waitFor();
  if(!await root.locator('[data-vf-iptv-import]').isVisible())throw Error('import hidden');
  if(await p.locator('.vf-m3u8-launchbar__current').isVisible())throw Error('duplicate launcher visible');
  if(await p.locator('.vf-tool-breadcrumb').isVisible())throw Error('breadcrumb visible');
  const sizes=await p.evaluate(()=>({scroll:document.documentElement.scrollWidth,client:document.documentElement.clientWidth}));
  if(sizes.scroll>sizes.client+1)throw Error('horizontal overflow '+JSON.stringify(sizes));
  await p.screenshot({path:'proof/iptv-'+lang+'-'+width+'-empty.png',fullPage:true});
  await root.locator('[data-vf-iptv-sample]').click();
  await p.waitForFunction(()=>Number(document.querySelector('[data-vf-iptv-count]')?.textContent)>0);
  const count=Number(await root.locator('[data-vf-iptv-count]').first().textContent());if(count<2)throw Error('sample incomplete');
  const before=(await root.locator('[data-vf-iptv-list]').innerText());if(!before.includes('News'))throw Error('sample rows missing');
  await root.locator('[data-vf-iptv-search]').fill('News');
  await p.waitForTimeout(400);const filtered=await root.locator('[data-vf-iptv-list]').innerText();if(!filtered.includes('News'))throw Error('search missing target');
  await root.locator('[data-vf-iptv-search]').fill('');
  const [dl]=await Promise.all([p.waitForEvent('download'),root.locator('[data-vf-iptv-export-m3u]').click()]);
  const contents=fs.readFileSync(await dl.path(),'utf8');if(!contents.includes('#EXTM3U')||!contents.includes('#EXTINF'))throw Error('invalid export');
  await p.screenshot({path:'proof/iptv-'+lang+'-'+width+'-sample.png',fullPage:true});
  checks.push({lang,width,count,search:'PASS',m3uExport:'PASS',overflow:'PASS'});await ctx.close();
 }}finally{await b.close()}
 fs.writeFileSync('proof/iptv-check.json',JSON.stringify({status:'PASS',checks},null,2));console.log(JSON.stringify({status:'PASS',checks}));
})().catch(e=>{console.error(e);process.exitCode=1});
