import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const base=process.env.VF_E2E_BASE_URL||'http://127.0.0.1:19052';
const evidence=process.env.EVIDENCE, source=process.env.SOURCE_SHA, webRoot=process.env.WEB_ROOT, productRoot=process.env.PRODUCT_ROOT||path.join(process.cwd(),'product');
if(!evidence||!source||!webRoot)throw new Error('domain detail audit environment missing');
const password='Vf'+crypto.randomUUID().replaceAll('-','')+'Aa1';
const report={schema:'p04-domain-detail-current-audit/v1',source_sha:source,desktop:{},mobile:{},page_errors:[],console_errors:[],production_actions_executed:false,synthetic_test_data_only:true};
const browser=await chromium.launch({headless:true});const context=await browser.newContext({viewport:{width:1365,height:900}});const page=await context.newPage();
page.on('pageerror',e=>report.page_errors.push(String(e?.stack||e)));page.on('console',m=>{if(m.type()==='error')report.console_errors.push(m.text())});
try{
 await page.goto(`${base}/setup.php`,{waitUntil:'domcontentloaded'});await page.locator('#site_name').fill('VF Infra Domain Detail Audit');await page.locator('#password').fill(password);await page.locator('#password_confirm').fill(password);await Promise.all([page.waitForURL(/login\.php\?installed=1/),page.getByRole('button',{name:'安装并进入系统'}).click()]);await page.locator('#admin-password').fill(password);await Promise.all([page.waitForURL(/index\.php(?:#.*)?$/),page.getByRole('button',{name:'登录'}).click()]);
 const fixture=execFileSync('php',['tests/fixtures/v260-user-task-fixture.php',webRoot],{cwd:productRoot,encoding:'utf8'});if(!fixture.includes('P04_V260_USER_TASK_FIXTURE_PASS'))throw new Error('server fixture failed');
 const domain='daily-domain-audit.example';
 const saved=await page.evaluate(async(domain)=>{const csrf=document.querySelector('meta[name="csrf-token"]')?.content||'';const r=await fetch('api.php?action=domain_save',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify({domain,registrar:'Namecheap',renewal_price:'18.50',currency:'USD',renewal_policy:'manual',manual_expiry_date:'2026-09-18',notes:'Synthetic domain detail audit'})});return await r.json()},domain);
 if(!saved.ok||!saved.domain?.id)throw new Error(`domain save failed ${JSON.stringify(saved)}`);const domainId=String(saved.domain.id);
 const integration=execFileSync('php',['tests/fixtures/v270-integration-fixture.php',webRoot,domain],{cwd:productRoot,encoding:'utf8'});if(!integration.includes('P04_V270_INTEGRATION_FIXTURE_PASS'))throw new Error('domain integration fixture failed');
 await page.goto(`${base}/index.php#domain/${domainId}`,{waitUntil:'domcontentloaded'});await page.locator('.v270-context-head').waitFor({state:'visible',timeout:15000});await page.waitForTimeout(500);
 report.desktop=await page.evaluate(()=>{const metrics=[...document.querySelectorAll('.v270-ref-summary .v270-ref-metric')].map(n=>({label:n.querySelector('span')?.textContent?.trim()||'',value:n.querySelector('strong')?.textContent?.replace(/\s+/g,' ').trim()||''}));const next=document.querySelector('.v270-next');return{h1:document.querySelector('#v270-app h1')?.textContent?.trim()||'',metrics,next_heading:next?.querySelector('h2')?.textContent?.trim()||'',next_text:next?.querySelector('p')?.textContent?.trim()||'',side:(document.querySelector('.v270-side')?.innerText||'').replace(/\s+/g,' ').trim(),app_text:(document.querySelector('#v270-app')?.innerText||'').replace(/\n{3,}/g,'\n\n').slice(0,5000)}});
 await page.screenshot({path:`${evidence}/01-domain-detail-desktop.png`,fullPage:true,animations:'disabled'});
 await page.setViewportSize({width:390,height:844});await page.goto(`${base}/index.php#domain/${domainId}`,{waitUntil:'domcontentloaded'});await page.locator('.v270-context-head').waitFor({state:'visible',timeout:15000});await page.waitForTimeout(400);
 report.mobile=await page.evaluate(()=>({next_heading:document.querySelector('.v270-next h2')?.textContent?.trim()||'',page_overflow:Math.max(document.documentElement.scrollWidth,document.body.scrollWidth)-window.innerWidth,app_text:(document.querySelector('#v270-app')?.innerText||'').replace(/\n{3,}/g,'\n\n').slice(0,3500)}));
 await page.screenshot({path:`${evidence}/02-domain-detail-mobile-390.png`,fullPage:true,animations:'disabled'});
}finally{fs.mkdirSync(evidence,{recursive:true});fs.writeFileSync(`${evidence}/P04_DOMAIN_DETAIL_CURRENT_AUDIT.json`,JSON.stringify(report,null,2)+'\n');await browser.close()}
console.log('P04_DOMAIN_DETAIL_CURRENT_AUDIT=COMPLETE');
