import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const base=process.env.VF_E2E_BASE_URL||'http://127.0.0.1:19061';
const evidence=process.env.EVIDENCE,candidate=process.env.CANDIDATE,webRoot=process.env.WEB_ROOT,productRoot=process.env.PRODUCT_ROOT||path.join(process.cwd(),'product');
if(!evidence||!candidate||!webRoot)throw new Error('gate environment missing');
fs.mkdirSync(evidence,{recursive:true});
const password='Vf'+crypto.randomUUID().replaceAll('-','')+'Aa1';
const report={schema:'p04-list-search-click-stability-gate/v1',source_sha:candidate,status:'FAIL',domain:{},server:{},mobile:{},page_errors:[],console_errors:[],production_actions_executed:false,synthetic_test_data_only:true};
const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:1365,height:900}});
page.on('pageerror',e=>report.page_errors.push(String(e?.stack||e)));
page.on('console',m=>{if(m.type()==='error')report.console_errors.push(m.text())});
const clean=s=>String(s||'').replace(/\s+/g,' ').trim();
const pointerClick=async locator=>{
  await locator.waitFor({state:'visible',timeout:12000});
  await locator.scrollIntoViewIfNeeded();
  await page.waitForTimeout(60);
  const box=await locator.boundingBox();
  if(!box||box.width<=0||box.height<=0)throw new Error('pointer target has no box');
  if(box.x<0||box.y<0||box.x+box.width>page.viewportSize().width||box.y+box.height>page.viewportSize().height)throw new Error(`pointer target outside viewport ${JSON.stringify(box)}`);
  await page.mouse.move(box.x+box.width/2,box.y+box.height/2);
  await page.mouse.down();
  await page.waitForTimeout(35);
  await page.mouse.up();
};
const waitList=async kind=>{
  const toolbar=page.locator(`[data-v275-toolbar="${kind}"]`);
  await toolbar.waitFor({state:'visible',timeout:15000});
  const input=toolbar.locator('[data-v275-query]');
  await input.waitFor({state:'visible',timeout:10000});
  return{toolbar,input};
};
const countText=toolbar=>toolbar.locator('[data-v275-count]').innerText().catch(()=> '');
const openDomainByPointer=async()=>{
  const trigger=page.locator('table.domain-table .v275-more-button:visible').first();
  await pointerClick(trigger);
  const menu=page.locator('.v275-quick-menu:visible');
  await menu.waitFor({state:'visible',timeout:5000});
  const open=menu.locator('[data-action="open"]');
  await pointerClick(open);
  await page.waitForFunction(()=>location.hash.startsWith('#domain/'),null,{timeout:10000});
};

try{
  await page.goto(`${base}/setup.php`,{waitUntil:'domcontentloaded'});
  await page.locator('#site_name').fill('VF Infra List Search Click Stability Gate');
  await page.locator('#password').fill(password);await page.locator('#password_confirm').fill(password);
  await Promise.all([page.waitForURL(/login\.php\?installed=1/),page.getByRole('button',{name:'安装并进入系统'}).click()]);
  await page.locator('#admin-password').fill(password);
  await Promise.all([page.waitForURL(/index\.php(?:#.*)?$/),page.getByRole('button',{name:'登录'}).click()]);

  const fixture=execFileSync('php',['tests/fixtures/v260-user-task-fixture.php',webRoot],{cwd:productRoot,encoding:'utf8'});
  if(!fixture.includes('P04_V260_USER_TASK_FIXTURE_PASS'))throw new Error('server fixture failed');
  const savedDomain=await page.evaluate(async()=>{
    const csrf=document.querySelector('meta[name="csrf-token"]')?.content||'';
    const response=await fetch('api.php?action=domain_save',{method:'POST',credentials:'same-origin',headers:{Accept:'application/json','Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify({domain:'infra-home.net',registrar:'Namecheap',renewal_price:'18.50',currency:'USD',renewal_policy:'manual',manual_expiry_date:'2026-12-18',notes:'Synthetic pointer stability gate'})});
    return await response.json();
  });
  if(!savedDomain?.ok||!savedDomain?.domain?.id)throw new Error(`domain fixture failed ${JSON.stringify(savedDomain)}`);

  // Fresh document so the Current v270 in-memory snapshot sees fixture writes.
  await page.goto(`${base}/index.php?gate=${Date.now()}#domains`,{waitUntil:'domcontentloaded'});
  let domain=await waitList('domains');
  await domain.input.fill('infra-home');
  await page.waitForTimeout(220);
  report.domain.before={query:await domain.input.inputValue(),count:clean(await countText(domain.toolbar)),active:await page.evaluate(()=>document.activeElement?.matches?.('[data-v275-query]')||false)};
  if(report.domain.before.query!=='infra-home'||!report.domain.before.active)throw new Error(`domain search setup failed ${JSON.stringify(report.domain.before)}`);

  await openDomainByPointer();
  report.domain.detail_after_pointer=await page.evaluate(()=>location.hash);
  await page.goBack();
  await page.waitForFunction(()=>location.hash==='#domains',null,{timeout:10000});
  domain=await waitList('domains');await page.waitForTimeout(220);
  report.domain.after_browser_back={query:await domain.input.inputValue(),count:clean(await countText(domain.toolbar))};
  await page.screenshot({path:`${evidence}/01-domain-after-browser-back.png`,fullPage:true,animations:'disabled'});

  await domain.input.fill('infra-home');await page.waitForTimeout(180);
  await openDomainByPointer();
  const backbar=page.locator('[data-v275-context-backbar]');await backbar.waitFor({state:'visible',timeout:10000});
  const back=backbar.locator('[data-v275-go="#domains"]');await pointerClick(back);
  await page.waitForFunction(()=>location.hash==='#domains',null,{timeout:10000});
  domain=await waitList('domains');await page.waitForTimeout(220);
  report.domain.after_context_back={query:await domain.input.inputValue(),count:clean(await countText(domain.toolbar))};

  await page.goto(`${base}/index.php?gate=${Date.now()}#servers`,{waitUntil:'domcontentloaded'});
  let server=await waitList('servers');
  await server.input.fill('v260-edge-01');await page.waitForTimeout(220);
  report.server.before={query:await server.input.inputValue(),count:clean(await countText(server.toolbar)),active:await page.evaluate(()=>document.activeElement?.matches?.('[data-v275-query]')||false)};
  const serverAction=page.locator('table.server-table [data-v270-action="server"]:visible').first();
  await pointerClick(serverAction);
  await page.waitForFunction(()=>location.hash.startsWith('#server/'),null,{timeout:10000});
  report.server.detail_after_pointer=await page.evaluate(()=>location.hash);
  await page.goBack();await page.waitForFunction(()=>location.hash==='#servers',null,{timeout:10000});
  server=await waitList('servers');await page.waitForTimeout(220);
  report.server.after_browser_back={query:await server.input.inputValue(),count:clean(await countText(server.toolbar))};
  await page.screenshot({path:`${evidence}/02-server-after-browser-back.png`,fullPage:true,animations:'disabled'});

  await page.setViewportSize({width:390,height:844});
  await page.goto(`${base}/index.php?gate=${Date.now()}#servers`,{waitUntil:'domcontentloaded'});
  server=await waitList('servers');await server.input.fill('v260-edge-01');await page.waitForTimeout(220);
  const mobileAction=page.locator('.server-card [data-v270-action="server"]:visible').first();
  await pointerClick(mobileAction);
  await page.waitForFunction(()=>location.hash.startsWith('#server/'),null,{timeout:10000});
  await page.goBack();await page.waitForFunction(()=>location.hash==='#servers',null,{timeout:10000});
  server=await waitList('servers');await page.waitForTimeout(220);
  report.mobile.server_after_back={query:await server.input.inputValue(),overflow:await page.evaluate(()=>Math.max(document.documentElement.scrollWidth,document.body.scrollWidth)-innerWidth)};
  await page.screenshot({path:`${evidence}/03-server-mobile-after-back.png`,fullPage:true,animations:'disabled'});

  if(report.domain.after_browser_back.query!=='infra-home')throw new Error(`domain browser Back lost query: ${report.domain.after_browser_back.query}`);
  if(report.domain.after_context_back.query!=='infra-home')throw new Error(`domain context back lost query: ${report.domain.after_context_back.query}`);
  if(report.server.after_browser_back.query!=='v260-edge-01')throw new Error(`server browser Back lost query: ${report.server.after_browser_back.query}`);
  if(report.mobile.server_after_back.query!=='v260-edge-01')throw new Error(`mobile server Back lost query: ${report.mobile.server_after_back.query}`);
  if(report.mobile.server_after_back.overflow>1)throw new Error(`mobile overflow ${report.mobile.server_after_back.overflow}`);
  if(report.page_errors.length)throw new Error(`page errors ${JSON.stringify(report.page_errors)}`);
  if(report.console_errors.length)throw new Error(`console errors ${JSON.stringify(report.console_errors)}`);
  report.status='PASS';
}finally{
  fs.writeFileSync(`${evidence}/P04_LIST_SEARCH_CLICK_STABILITY_GATE.json`,JSON.stringify(report,null,2)+'\n');
  await browser.close();
}
console.log(`P04_LIST_SEARCH_CLICK_STABILITY_GATE=${report.status}`);
