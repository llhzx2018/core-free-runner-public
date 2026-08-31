import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const base=process.env.VF_E2E_BASE_URL||'http://127.0.0.1:19054';
const evidence=process.env.EVIDENCE, candidate=process.env.CANDIDATE, webRoot=process.env.WEB_ROOT, productRoot=process.env.PRODUCT_ROOT||path.join(process.cwd(),'product');
if(!evidence||!candidate||!webRoot)throw new Error('cross detail audit environment missing');
const password='Vf'+crypto.randomUUID().replaceAll('-','')+'Aa1';
const report={schema:'p04-cross-detail-human-language-audit/v1',source_sha:candidate,status:'FAIL',desktop:{},mobile:{},page_errors:[],console_errors:[],production_actions_executed:false,synthetic_test_data_only:true};
const browser=await chromium.launch({headless:true});
const context=await browser.newContext({viewport:{width:1365,height:900}});
const page=await context.newPage();
page.on('pageerror',e=>report.page_errors.push(String(e?.stack||e)));
page.on('console',m=>{if(m.type()==='error')report.console_errors.push(m.text())});
const clean=s=>String(s||'').replace(/\s+/g,' ').trim();
const technical=['OWNER','Provider','Capability','Impact','Freshness','Region','Reference-Locked','Personal Infrastructure Control'];
const scan=async()=>page.evaluate((tokens)=>{const app=document.querySelector('#v270-app');const text=(app?.innerText||'').replace(/\s+/g,' ').trim();const matches={};for(const token of tokens){const re=new RegExp(token.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'),'gi');const found=[...text.matchAll(re)].map(m=>m[0]);if(found.length)matches[token]=found.length;}return{text,matches,headings:[...app?.querySelectorAll('h1,h2,h3')||[]].map(n=>(n.textContent||'').replace(/\s+/g,' ').trim()).filter(Boolean),overflow:Math.max(document.documentElement.scrollWidth,document.body.scrollWidth)-window.innerWidth};},technical);
async function cold(hash){await page.goto('about:blank');await page.goto(`${base}/index.php#${hash}`,{waitUntil:'domcontentloaded'});await page.locator('#v270-app h1').waitFor({state:'visible',timeout:15000});await page.waitForTimeout(700);}
try{
  await page.goto(`${base}/setup.php`,{waitUntil:'domcontentloaded'});
  await page.locator('#site_name').fill('VF Infra Cross Detail Language Audit');
  await page.locator('#password').fill(password); await page.locator('#password_confirm').fill(password);
  await Promise.all([page.waitForURL(/login\.php\?installed=1/),page.getByRole('button',{name:'安装并进入系统'}).click()]);
  await page.locator('#admin-password').fill(password);
  await Promise.all([page.waitForURL(/index\.php(?:#.*)?$/),page.getByRole('button',{name:'登录'}).click()]);
  const fixture=execFileSync('php',['tests/fixtures/v260-user-task-fixture.php',webRoot],{cwd:productRoot,encoding:'utf8'});
  if(!fixture.includes('P04_V260_USER_TASK_FIXTURE_PASS'))throw new Error('fixture failed');

  await cold('servers');
  const serverAction=page.locator('table.server-table [data-v270-action="server"]').first();
  const serverId=await serverAction.getAttribute('data-id'); if(!serverId)throw new Error('server id missing');
  await cold(`server/${serverId}`);
  report.desktop.server=await scan();
  await page.screenshot({path:`${evidence}/01-server-detail-desktop.png`,fullPage:true,animations:'disabled'});

  await cold('providers');
  const providerAction=page.locator('[data-v271-action="provider-open"], [data-v270-action="provider"]').first();
  const providerId=await providerAction.getAttribute('data-id'); if(!providerId)throw new Error('provider id missing');
  await cold(`provider/${providerId}`);
  report.desktop.provider=await scan();
  await page.screenshot({path:`${evidence}/02-provider-detail-desktop.png`,fullPage:true,animations:'disabled'});

  await cold('settings');
  report.desktop.settings=await scan();
  await page.screenshot({path:`${evidence}/03-settings-desktop.png`,fullPage:true,animations:'disabled'});

  await page.setViewportSize({width:390,height:844});
  await cold(`server/${serverId}`); report.mobile.server=await scan(); await page.screenshot({path:`${evidence}/04-server-detail-mobile-390.png`,fullPage:true,animations:'disabled'});
  await cold(`provider/${providerId}`); report.mobile.provider=await scan(); await page.screenshot({path:`${evidence}/05-provider-detail-mobile-390.png`,fullPage:true,animations:'disabled'});
  await cold('settings'); report.mobile.settings=await scan(); await page.screenshot({path:`${evidence}/06-settings-mobile-390.png`,fullPage:true,animations:'disabled'});

  for(const view of [...Object.values(report.desktop),...Object.values(report.mobile)]){if(view.overflow>1)throw new Error(`page overflow ${view.overflow}`)}
  if(report.page_errors.length)throw new Error(`page errors ${JSON.stringify(report.page_errors)}`);
  if(report.console_errors.length)throw new Error(`console errors ${JSON.stringify(report.console_errors)}`);
  report.status='PASS';
}finally{
  fs.mkdirSync(evidence,{recursive:true});
  fs.writeFileSync(`${evidence}/P04_CROSS_DETAIL_HUMAN_LANGUAGE_AUDIT.json`,JSON.stringify(report,null,2)+'\n');
  await browser.close();
}
console.log(`P04_CROSS_DETAIL_HUMAN_LANGUAGE_AUDIT=${report.status}`);
