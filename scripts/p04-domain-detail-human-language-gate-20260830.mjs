import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const base=process.env.VF_E2E_BASE_URL||'http://127.0.0.1:19053';
const evidence=process.env.EVIDENCE, candidate=process.env.CANDIDATE, webRoot=process.env.WEB_ROOT, productRoot=process.env.PRODUCT_ROOT||path.join(process.cwd(),'product');
if(!evidence||!candidate||!webRoot)throw new Error('domain detail gate environment missing');
const password='Vf'+crypto.randomUUID().replaceAll('-','')+'Aa1';
const report={schema:'p04-domain-detail-human-language-gate/v1',source_sha:candidate,status:'FAIL',domain:{},dns:{},mobile:{},page_errors:[],console_errors:[],production_actions_executed:false,synthetic_test_data_only:true};
const browser=await chromium.launch({headless:true});
const context=await browser.newContext({viewport:{width:1365,height:900}});
const page=await context.newPage();
page.on('pageerror',e=>report.page_errors.push(String(e?.stack||e)));
page.on('console',m=>{if(m.type()==='error')report.console_errors.push(m.text())});
const fail=(message)=>{throw new Error(message)};
const clean=(value)=>String(value||'').replace(/\s+/g,' ').trim();
try{
  await page.goto(`${base}/setup.php`,{waitUntil:'domcontentloaded'});
  await page.locator('#site_name').fill('VF Infra Domain Language Gate');
  await page.locator('#password').fill(password);
  await page.locator('#password_confirm').fill(password);
  await Promise.all([page.waitForURL(/login\.php\?installed=1/),page.getByRole('button',{name:'安装并进入系统'}).click()]);
  await page.locator('#admin-password').fill(password);
  await Promise.all([page.waitForURL(/index\.php(?:#.*)?$/),page.getByRole('button',{name:'登录'}).click()]);

  const fixture=execFileSync('php',['tests/fixtures/v260-user-task-fixture.php',webRoot],{cwd:productRoot,encoding:'utf8'});
  if(!fixture.includes('P04_V260_USER_TASK_FIXTURE_PASS'))fail('server fixture failed');
  const domain='daily-domain-language.example';
  const saved=await page.evaluate(async(domain)=>{
    const csrf=document.querySelector('meta[name="csrf-token"]')?.content||'';
    const r=await fetch('api.php?action=domain_save',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify({domain,registrar:'Namecheap',renewal_price:'18.50',currency:'USD',renewal_policy:'manual',manual_expiry_date:'2026-09-18',notes:'Synthetic domain human language gate'})});
    return await r.json();
  },domain);
  if(!saved.ok||!saved.domain?.id)fail(`domain save failed ${JSON.stringify(saved)}`);
  const domainId=String(saved.domain.id);
  const integration=execFileSync('php',['tests/fixtures/v270-integration-fixture.php',webRoot,domain],{cwd:productRoot,encoding:'utf8'});
  if(!integration.includes('P04_V270_INTEGRATION_FIXTURE_PASS'))fail('domain integration fixture failed');

  await page.goto(`${base}/index.php#domain/${domainId}`,{waitUntil:'domcontentloaded'});
  await page.locator('.v270-context-head').waitFor({state:'visible',timeout:15000});
  await page.waitForTimeout(400);
  report.domain=await page.evaluate(()=>{
    const app=document.querySelector('#v270-app');
    const text=(app?.innerText||'').replace(/\s+/g,' ').trim();
    const metrics=[...document.querySelectorAll('.v270-ref-summary .v270-ref-metric')].map(n=>({label:n.querySelector('span')?.textContent?.trim()||'',value:n.querySelector('strong')?.textContent?.replace(/\s+/g,' ').trim()||''}));
    return {text,metrics,next_heading:document.querySelector('.v270-next h2')?.textContent?.trim()||'',dns_field:[...document.querySelectorAll('.v270-ref-field')].find(n=>n.querySelector('span')?.textContent?.trim()==='DNS')?.querySelector('strong')?.textContent?.replace(/\s+/g,' ').trim()||'',alert_badges:[...document.querySelectorAll('.v270-ref-actions .v270-status')].map(n=>n.textContent?.trim()||'')};
  });
  if(report.domain.text.includes('Unknown'))fail('domain still exposes Unknown');
  if(/\bactive\b/i.test(report.domain.text))fail('domain still exposes active');
  if(/\bmedium\b/i.test(report.domain.text))fail('domain still exposes medium');
  if(report.domain.text.includes('OWNER 下一步'))fail('domain still exposes OWNER 下一步');
  if(report.domain.next_heading!=='下一步')fail(`domain next heading mismatch: ${report.domain.next_heading}`);
  if(!report.domain.metrics.some(m=>m.label==='价格变化'&&m.value==='未记录'))fail('domain price-change missing 未记录');
  if(!report.domain.dns_field.includes('正常'))fail(`domain DNS status not humanized: ${report.domain.dns_field}`);
  if(!report.domain.alert_badges.includes('提醒'))fail(`domain alert severity not humanized: ${JSON.stringify(report.domain.alert_badges)}`);
  await page.screenshot({path:`${evidence}/01-domain-detail-desktop.png`,fullPage:true,animations:'disabled'});

  const dnsButton=page.getByRole('button',{name:'查看 DNS'}).first();
  await dnsButton.click();
  await page.waitForURL(/#dns\//);
  await page.locator('.v270-context-head').waitFor({state:'visible',timeout:15000});
  await page.waitForTimeout(250);
  report.dns=await page.evaluate(()=>({text:(document.querySelector('#v270-app')?.innerText||'').replace(/\s+/g,' ').trim(),next_heading:document.querySelector('.v270-next h2')?.textContent?.trim()||'',status:[...document.querySelectorAll('.v270-ref-summary .v270-ref-metric')].find(n=>n.querySelector('span')?.textContent?.trim()==='状态')?.querySelector('strong')?.textContent?.replace(/\s+/g,' ').trim()||''}));
  if(report.dns.text.includes('OWNER 下一步'))fail('DNS still exposes OWNER 下一步');
  if(/\bactive\b/i.test(report.dns.text))fail('DNS still exposes active');
  if(report.dns.next_heading!=='下一步')fail(`DNS next heading mismatch: ${report.dns.next_heading}`);
  if(!report.dns.status.includes('正常'))fail(`DNS status not humanized: ${report.dns.status}`);
  await page.screenshot({path:`${evidence}/02-dns-detail-desktop.png`,fullPage:true,animations:'disabled'});

  await page.setViewportSize({width:390,height:844});
  await page.goto(`${base}/index.php#domain/${domainId}`,{waitUntil:'domcontentloaded'});
  await page.locator('.v270-context-head').waitFor({state:'visible',timeout:15000});
  await page.waitForTimeout(300);
  report.mobile=await page.evaluate(()=>({text:(document.querySelector('#v270-app')?.innerText||'').replace(/\s+/g,' ').trim(),next_heading:document.querySelector('.v270-next h2')?.textContent?.trim()||'',page_overflow:Math.max(document.documentElement.scrollWidth,document.body.scrollWidth)-window.innerWidth}));
  if(report.mobile.text.includes('Unknown')||/\bactive\b/i.test(report.mobile.text)||/\bmedium\b/i.test(report.mobile.text)||report.mobile.text.includes('OWNER 下一步'))fail('mobile still exposes technical language');
  if(report.mobile.next_heading!=='下一步')fail(`mobile next heading mismatch: ${report.mobile.next_heading}`);
  if(report.mobile.page_overflow>1)fail(`mobile page overflow ${report.mobile.page_overflow}`);
  await page.screenshot({path:`${evidence}/03-domain-detail-mobile-390.png`,fullPage:true,animations:'disabled'});

  if(report.page_errors.length)fail(`page errors: ${report.page_errors.join(' | ')}`);
  if(report.console_errors.length)fail(`console errors: ${report.console_errors.join(' | ')}`);
  report.status='PASS';
}finally{
  fs.mkdirSync(evidence,{recursive:true});
  fs.writeFileSync(`${evidence}/P04_DOMAIN_DETAIL_HUMAN_LANGUAGE_REPORT.json`,JSON.stringify(report,null,2)+'\n');
  await browser.close();
}
console.log(`P04_DOMAIN_DETAIL_HUMAN_LANGUAGE_GATE=${report.status}`);
