import { chromium } from 'playwright';
import fs from 'node:fs';

const base=process.env.VF_E2E_BASE_URL||'http://127.0.0.1:19056';
const evidence=process.env.EVIDENCE,candidate=process.env.CANDIDATE;
if(!evidence||!candidate)throw new Error('settings ergonomics audit environment missing');
const password='Vf'+crypto.randomUUID().replaceAll('-','')+'Aa1';
const report={schema:'p04-settings-basic-ergonomics-audit/v1',source_sha:candidate,status:'FAIL',desktop:{},mobile:{},page_errors:[],console_errors:[],production_actions_executed:false,synthetic_test_data_only:true};
const browser=await chromium.launch({headless:true});
const context=await browser.newContext({viewport:{width:1365,height:900}});
const page=await context.newPage();
page.on('pageerror',e=>report.page_errors.push(String(e?.stack||e)));
page.on('console',m=>{if(m.type()==='error')report.console_errors.push(m.text())});
const inspect=async()=>page.evaluate(()=>{
  const fields=[...document.querySelectorAll('#v271-basic-form .v271-field')].map(field=>{const label=field.querySelector('label')?.textContent?.trim()||'';const control=field.querySelector('input,select,textarea');const listId=control?.getAttribute('list')||'';const options=listId?[...document.querySelectorAll(`#${CSS.escape(listId)} option`)].map(o=>o.value):[];return{label,tag:control?.tagName?.toLowerCase()||'',type:control?.getAttribute('type')||'',name:control?.getAttribute('name')||'',value:control?.value||'',placeholder:control?.getAttribute('placeholder')||'',list:listId,option_count:options.length,options:options.slice(0,12),autocomplete:control?.getAttribute('autocomplete')||'',inputmode:control?.getAttribute('inputmode')||'',min:control?.getAttribute('min')||'',max:control?.getAttribute('max')||'',maxlength:control?.getAttribute('maxlength')||'',help:field.querySelector('small')?.textContent?.replace(/\s+/g,' ').trim()||''};});
  const text=(document.querySelector('#v270-app')?.innerText||'').replace(/\s+/g,' ').trim();
  return{fields,text,save_label:document.querySelector('#v271-basic-form button[type="submit"]')?.textContent?.trim()||'',overflow:Math.max(document.documentElement.scrollWidth,document.body.scrollWidth)-window.innerWidth};
});
try{
  await page.goto(`${base}/setup.php`,{waitUntil:'domcontentloaded'});
  await page.locator('#site_name').fill('VF Infra Settings Ergonomics Audit');
  await page.locator('#password').fill(password);await page.locator('#password_confirm').fill(password);
  await Promise.all([page.waitForURL(/login\.php\?installed=1/),page.getByRole('button',{name:'安装并进入系统'}).click()]);
  await page.locator('#admin-password').fill(password);
  await Promise.all([page.waitForURL(/index\.php(?:#.*)?$/),page.getByRole('button',{name:'登录'}).click()]);
  await page.goto(`${base}/index.php#settings/basic`,{waitUntil:'domcontentloaded'});
  await page.locator('#v271-basic-form').waitFor({state:'visible',timeout:15000});
  await page.waitForTimeout(700);
  report.desktop=await inspect();
  await page.screenshot({path:`${evidence}/01-settings-basic-desktop.png`,fullPage:true,animations:'disabled'});
  await page.setViewportSize({width:390,height:844});
  await page.goto(`${base}/index.php#settings/basic`,{waitUntil:'domcontentloaded'});
  await page.locator('#v271-basic-form').waitFor({state:'visible',timeout:15000});
  await page.waitForTimeout(500);
  report.mobile=await inspect();
  await page.screenshot({path:`${evidence}/02-settings-basic-mobile-390.png`,fullPage:true,animations:'disabled'});
  if(report.desktop.overflow>1||report.mobile.overflow>1)throw new Error(`overflow desktop=${report.desktop.overflow} mobile=${report.mobile.overflow}`);
  if(report.page_errors.length)throw new Error(`page errors ${JSON.stringify(report.page_errors)}`);
  if(report.console_errors.length)throw new Error(`console errors ${JSON.stringify(report.console_errors)}`);
  report.status='PASS';
}finally{
  fs.mkdirSync(evidence,{recursive:true});
  fs.writeFileSync(`${evidence}/P04_SETTINGS_BASIC_ERGONOMICS_AUDIT.json`,JSON.stringify(report,null,2)+'\n');
  await browser.close();
}
console.log(`P04_SETTINGS_BASIC_ERGONOMICS_AUDIT=${report.status}`);
