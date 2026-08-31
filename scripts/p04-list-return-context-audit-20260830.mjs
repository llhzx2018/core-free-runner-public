import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const base=process.env.VF_E2E_BASE_URL||'http://127.0.0.1:19057';
const evidence=process.env.EVIDENCE,candidate=process.env.CANDIDATE,webRoot=process.env.WEB_ROOT,productRoot=process.env.PRODUCT_ROOT||path.join(process.cwd(),'product');
if(!evidence||!candidate||!webRoot)throw new Error('list return context audit environment missing');
const password='Vf'+crypto.randomUUID().replaceAll('-','')+'Aa1';
const report={schema:'p04-list-return-context-audit/v3',source_sha:candidate,status:'FAIL',domain:{},server:{},mobile:{},page_errors:[],console_errors:[],production_actions_executed:false,synthetic_test_data_only:true};
const browser=await chromium.launch({headless:true});
const context=await browser.newContext({viewport:{width:1365,height:900}});
const page=await context.newPage();
page.on('pageerror',e=>report.page_errors.push(String(e?.stack||e)));
page.on('console',m=>{if(m.type()==='error')report.console_errors.push(m.text())});
const clean=s=>String(s||'').replace(/\s+/g,' ').trim();
const waitList=async(kind)=>{
  const toolbar=page.locator(`[data-v275-toolbar="${kind}"]`);
  await toolbar.waitFor({state:'visible',timeout:15000});
  const input=toolbar.locator('[data-v275-query]');
  await input.waitFor({state:'visible',timeout:10000});
  return{toolbar,input};
};
const currentCount=async(toolbar)=>clean(await toolbar.locator('[data-v275-count]').innerText().catch(()=>''));
const openDomainDetail=async()=>{
  const trigger=page.locator('table.domain-table .v275-more-button:visible').first();
  await trigger.waitFor({state:'visible',timeout:10000});
  const id=await trigger.getAttribute('data-v275-domain-actions');
  await trigger.click();
  const open=page.locator('.v275-quick-menu [data-action="open"]:visible');
  await open.waitFor({state:'visible',timeout:10000});
  await open.click();
  await page.waitForFunction(value=>location.hash===`#domain/${encodeURIComponent(value)}`,id,{timeout:10000});
  return id;
};

try{
  await page.goto(`${base}/setup.php`,{waitUntil:'domcontentloaded'});
  await page.locator('#site_name').fill('VF Infra List Return Context Audit');
  await page.locator('#password').fill(password);await page.locator('#password_confirm').fill(password);
  await Promise.all([page.waitForURL(/login\.php\?installed=1/),page.getByRole('button',{name:'安装并进入系统'}).click()]);
  await page.locator('#admin-password').fill(password);
  await Promise.all([page.waitForURL(/index\.php(?:#.*)?$/),page.getByRole('button',{name:'登录'}).click()]);

  const fixture=execFileSync('php',['tests/fixtures/v260-user-task-fixture.php',webRoot],{cwd:productRoot,encoding:'utf8'});
  if(!fixture.includes('P04_V260_USER_TASK_FIXTURE_PASS'))throw new Error('server fixture failed');
  const savedDomain=await page.evaluate(async()=>{
    const csrf=document.querySelector('meta[name="csrf-token"]')?.content||'';
    const response=await fetch('api.php?action=domain_save',{method:'POST',credentials:'same-origin',headers:{Accept:'application/json','Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify({domain:'infra-home.net',registrar:'Namecheap',renewal_price:'18.50',currency:'USD',renewal_policy:'manual',manual_expiry_date:'2026-12-18',notes:'Synthetic list-return audit'})});
    return await response.json();
  });
  if(!savedDomain?.ok||!savedDomain?.domain?.id)throw new Error(`domain fixture failed ${JSON.stringify(savedDomain)}`);

  // New document required after fixture writes because v270 caches the snapshot in-memory for the current document.
  await page.goto(`${base}/index.php?audit=${Date.now()}#domains`,{waitUntil:'domcontentloaded'});
  let domainList=await waitList('domains');
  report.domain.loaded={rows:await page.locator('table.domain-table tbody tr').count(),quick_actions:await page.locator('table.domain-table .v275-more-button').count()};
  if(report.domain.loaded.quick_actions<1)throw new Error(`domain fixture not visible ${JSON.stringify(report.domain.loaded)}`);

  await domainList.input.fill('infra-home');
  await page.waitForTimeout(350);
  report.domain.before={query:await domainList.input.inputValue(),count:await currentCount(domainList.toolbar)};
  const domainId=await openDomainDetail();
  report.domain.detail_hash=await page.evaluate(()=>location.hash);
  await page.goBack();
  await page.waitForFunction(()=>location.hash==='#domains',null,{timeout:10000});
  domainList=await waitList('domains');
  await page.waitForTimeout(350);
  report.domain.after_browser_back={query:await domainList.input.inputValue(),count:await currentCount(domainList.toolbar)};
  await page.screenshot({path:`${evidence}/01-domains-after-browser-back.png`,fullPage:true,animations:'disabled'});

  // Current product route: quick menu -> detail -> V2.75 explicit contextual return button.
  await domainList.input.fill('infra-home');
  await page.waitForTimeout(250);
  await openDomainDetail();
  const backbar=page.locator('[data-v275-context-backbar]');
  await backbar.waitFor({state:'visible',timeout:10000});
  const backButton=backbar.locator('[data-v275-go="#domains"]');
  await backButton.waitFor({state:'visible',timeout:10000});
  await backButton.click();
  await page.waitForFunction(()=>location.hash==='#domains',null,{timeout:10000});
  domainList=await waitList('domains');
  await page.waitForTimeout(300);
  report.domain.after_context_back={query:await domainList.input.inputValue(),count:await currentCount(domainList.toolbar)};
  report.domain.id=domainId;

  await page.goto(`${base}/index.php?audit=${Date.now()}#servers`,{waitUntil:'domcontentloaded'});
  let serverList=await waitList('servers');
  report.server.loaded={rows:await page.locator('table.server-table tbody tr').count(),actions:await page.locator('table.server-table [data-v270-action="server"]').count()};
  if(report.server.loaded.actions<1)throw new Error(`server fixture not visible ${JSON.stringify(report.server.loaded)}`);
  await serverList.input.fill('v260-edge-01');
  await page.waitForTimeout(300);
  report.server.before={query:await serverList.input.inputValue(),count:await currentCount(serverList.toolbar)};
  const serverAction=page.locator('table.server-table [data-v270-action="server"]:visible').first();
  await serverAction.waitFor({state:'visible',timeout:10000});
  const serverId=await serverAction.getAttribute('data-id');
  await serverAction.click();
  await page.waitForFunction(id=>location.hash===`#server/${encodeURIComponent(id)}`,serverId,{timeout:10000});
  report.server.detail_hash=await page.evaluate(()=>location.hash);
  await page.goBack();
  await page.waitForFunction(()=>location.hash==='#servers',null,{timeout:10000});
  serverList=await waitList('servers');
  await page.waitForTimeout(350);
  report.server.after_browser_back={query:await serverList.input.inputValue(),count:await currentCount(serverList.toolbar)};
  await page.screenshot({path:`${evidence}/02-servers-after-browser-back.png`,fullPage:true,animations:'disabled'});

  await page.setViewportSize({width:390,height:844});
  await page.goto(`${base}/index.php?audit=${Date.now()}#servers`,{waitUntil:'domcontentloaded'});
  serverList=await waitList('servers');
  await serverList.input.fill('v260-edge-01');
  await page.waitForTimeout(250);
  const mobileAction=page.locator('.server-card [data-v270-action="server"]:visible').first();
  await mobileAction.waitFor({state:'visible',timeout:10000});
  await mobileAction.click();
  await page.waitForFunction(id=>location.hash===`#server/${encodeURIComponent(id)}`,serverId,{timeout:10000});
  await page.goBack();
  await page.waitForFunction(()=>location.hash==='#servers',null,{timeout:10000});
  serverList=await waitList('servers');
  await page.waitForTimeout(300);
  report.mobile.server_after_back={query:await serverList.input.inputValue(),overflow:await page.evaluate(()=>Math.max(document.documentElement.scrollWidth,document.body.scrollWidth)-window.innerWidth)};
  await page.screenshot({path:`${evidence}/03-servers-mobile-after-back.png`,fullPage:true,animations:'disabled'});

  const expectedDomain='infra-home',expectedServer='v260-edge-01';
  if(report.domain.after_browser_back.query!==expectedDomain)throw new Error(`domain browser-back query lost: ${report.domain.after_browser_back.query}`);
  if(report.domain.after_context_back.query!==expectedDomain)throw new Error(`domain context-back query lost: ${report.domain.after_context_back.query}`);
  if(report.server.after_browser_back.query!==expectedServer)throw new Error(`server browser-back query lost: ${report.server.after_browser_back.query}`);
  if(report.mobile.server_after_back.query!==expectedServer)throw new Error(`mobile server query lost: ${report.mobile.server_after_back.query}`);
  if(report.mobile.server_after_back.overflow>1)throw new Error(`mobile overflow ${report.mobile.server_after_back.overflow}`);
  if(report.page_errors.length)throw new Error(`page errors ${JSON.stringify(report.page_errors)}`);
  if(report.console_errors.length)throw new Error(`console errors ${JSON.stringify(report.console_errors)}`);
  report.status='PASS';
}finally{
  fs.mkdirSync(evidence,{recursive:true});
  fs.writeFileSync(`${evidence}/P04_LIST_RETURN_CONTEXT_AUDIT.json`,JSON.stringify(report,null,2)+'\n');
  await browser.close();
}
console.log(`P04_LIST_RETURN_CONTEXT_AUDIT=${report.status}`);
