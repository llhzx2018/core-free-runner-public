import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const base=process.env.VF_E2E_BASE_URL||'http://127.0.0.1:19057';
const evidence=process.env.EVIDENCE,candidate=process.env.CANDIDATE,webRoot=process.env.WEB_ROOT,productRoot=process.env.PRODUCT_ROOT||path.join(process.cwd(),'product');
if(!evidence||!candidate||!webRoot)throw new Error('list return context audit environment missing');
const password='Vf'+crypto.randomUUID().replaceAll('-','')+'Aa1';
const report={schema:'p04-list-return-context-audit/v1',source_sha:candidate,status:'FAIL',domain:{},server:{},mobile:{},page_errors:[],console_errors:[],production_actions_executed:false,synthetic_test_data_only:true};
const browser=await chromium.launch({headless:true});
const context=await browser.newContext({viewport:{width:1365,height:900}});
const page=await context.newPage();
page.on('pageerror',e=>report.page_errors.push(String(e?.stack||e)));
page.on('console',m=>{if(m.type()==='error')report.console_errors.push(m.text())});
const waitList=async(kind)=>{const toolbar=page.locator(`[data-v275-toolbar="${kind}"]`);await toolbar.waitFor({state:'visible',timeout:15000});const input=toolbar.locator('input[type="search"],input[data-v275-query]').first();await input.waitFor({state:'visible',timeout:10000});return{toolbar,input};};
const clean=s=>String(s||'').replace(/\s+/g,' ').trim();
try{
  await page.goto(`${base}/setup.php`,{waitUntil:'domcontentloaded'});
  await page.locator('#site_name').fill('VF Infra List Return Context Audit');
  await page.locator('#password').fill(password);await page.locator('#password_confirm').fill(password);
  await Promise.all([page.waitForURL(/login\.php\?installed=1/),page.getByRole('button',{name:'安装并进入系统'}).click()]);
  await page.locator('#admin-password').fill(password);
  await Promise.all([page.waitForURL(/index\.php(?:#.*)?$/),page.getByRole('button',{name:'登录'}).click()]);
  const fixture=execFileSync('php',['tests/fixtures/v260-user-task-fixture.php',webRoot],{cwd:productRoot,encoding:'utf8'});
  if(!fixture.includes('P04_V260_USER_TASK_FIXTURE_PASS'))throw new Error('fixture failed');

  // Domain search -> detail -> browser Back.
  await page.goto(`${base}/index.php#domains`,{waitUntil:'domcontentloaded'});
  let domainList=await waitList('domains');
  await domainList.input.fill('infra-home');
  await page.waitForTimeout(350);
  report.domain.before={query:await domainList.input.inputValue(),count:clean(await domainList.toolbar.locator('[data-v275-count]').innerText().catch(()=>''))};
  const domainAction=page.locator('table.domain-table [data-v270-action="domain"]:visible').first();
  await domainAction.waitFor({state:'visible',timeout:10000});
  const domainId=await domainAction.getAttribute('data-id');
  await domainAction.click();
  await page.waitForFunction(id=>location.hash===`#domain/${encodeURIComponent(id)}`,domainId,{timeout:10000});
  report.domain.detail_hash=await page.evaluate(()=>location.hash);
  await page.goBack();
  await page.waitForFunction(()=>location.hash==='#domains',null,{timeout:10000});
  domainList=await waitList('domains');
  await page.waitForTimeout(350);
  report.domain.after_browser_back={query:await domainList.input.inputValue(),count:clean(await domainList.toolbar.locator('[data-v275-count]').innerText().catch(()=>''))};
  await page.screenshot({path:`${evidence}/01-domains-after-browser-back.png`,fullPage:true,animations:'disabled'});

  // Domain search -> detail -> in-page breadcrumb.
  await domainList.input.fill('infra-home');
  await page.waitForTimeout(250);
  const domainAction2=page.locator('table.domain-table [data-v270-action="domain"]:visible').first();
  await domainAction2.click();
  await page.locator('.v270-breadcrumb').waitFor({state:'visible',timeout:10000});
  await page.locator('.v270-breadcrumb [data-v270-action="goto"]').first().click();
  await page.waitForFunction(()=>location.hash==='#domains',null,{timeout:10000});
  domainList=await waitList('domains');
  await page.waitForTimeout(300);
  report.domain.after_breadcrumb={query:await domainList.input.inputValue(),count:clean(await domainList.toolbar.locator('[data-v275-count]').innerText().catch(()=>''))};

  // Server search -> detail -> browser Back.
  await page.goto(`${base}/index.php#servers`,{waitUntil:'domcontentloaded'});
  let serverList=await waitList('servers');
  await serverList.input.fill('v260-edge-01');
  await page.waitForTimeout(300);
  report.server.before={query:await serverList.input.inputValue(),count:clean(await serverList.toolbar.locator('[data-v275-count]').innerText().catch(()=>''))};
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
  report.server.after_browser_back={query:await serverList.input.inputValue(),count:clean(await serverList.toolbar.locator('[data-v275-count]').innerText().catch(()=>''))};
  await page.screenshot({path:`${evidence}/02-servers-after-browser-back.png`,fullPage:true,animations:'disabled'});

  // 390px server return behavior.
  await page.setViewportSize({width:390,height:844});
  await page.goto(`${base}/index.php#servers`,{waitUntil:'domcontentloaded'});
  serverList=await waitList('servers');
  await serverList.input.fill('v260-edge-01');
  await page.waitForTimeout(250);
  const mobileAction=page.locator('.server-card [data-v270-action="server"]:visible').first();
  await mobileAction.click();
  await page.waitForFunction(id=>location.hash===`#server/${encodeURIComponent(id)}`,serverId,{timeout:10000});
  await page.goBack();
  await page.waitForFunction(()=>location.hash==='#servers',null,{timeout:10000});
  serverList=await waitList('servers');
  await page.waitForTimeout(300);
  report.mobile.server_after_back={query:await serverList.input.inputValue(),overflow:await page.evaluate(()=>Math.max(document.documentElement.scrollWidth,document.body.scrollWidth)-window.innerWidth)};
  await page.screenshot({path:`${evidence}/03-servers-mobile-after-back.png`,fullPage:true,animations:'disabled'});

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
