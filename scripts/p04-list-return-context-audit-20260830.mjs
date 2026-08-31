import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const base=process.env.VF_E2E_BASE_URL||'http://127.0.0.1:19057';
const evidence=process.env.EVIDENCE,candidate=process.env.CANDIDATE,webRoot=process.env.WEB_ROOT,productRoot=process.env.PRODUCT_ROOT||path.join(process.cwd(),'product');
if(!evidence||!candidate||!webRoot)throw new Error('list return context audit environment missing');
const password='Vf'+crypto.randomUUID().replaceAll('-','')+'Aa1';
const report={schema:'p04-list-return-context-runtime-diagnostic/v1',source_sha:candidate,status:'FAIL',network:[],domain:{},server:{},page_errors:[],console_errors:[],production_actions_executed:false,synthetic_test_data_only:true};
const browser=await chromium.launch({headless:true});
const context=await browser.newContext({viewport:{width:1365,height:900}});
const page=await context.newPage();
page.on('pageerror',e=>report.page_errors.push(String(e?.stack||e)));
page.on('console',m=>{if(m.type()==='error')report.console_errors.push(m.text())});
page.on('response',response=>{const url=response.url();if(/v275-ua-workflow|v274-performance-bridge|v270-reference-lock/.test(url))report.network.push({url,status:response.status(),ok:response.ok()});});

async function inventory(kind){
  const selector=kind==='domain'?'table.domain-table':'table.server-table';
  await page.locator(selector).waitFor({state:'visible',timeout:15000});
  await page.waitForTimeout(1200);
  return await page.evaluate(({selector,kind})=>{
    const table=document.querySelector(selector);
    const rows=[...(table?.tBodies?.[0]?.rows||[])];
    const app=document.querySelector('#v270-app');
    const toolbar=document.querySelector('.v275-list-toolbar');
    const inputs=[...app.querySelectorAll('input,select')].filter(n=>{const s=getComputedStyle(n);return s.display!=='none'&&s.visibility!=='hidden'}).map(n=>({tag:n.tagName.toLowerCase(),type:n.getAttribute('type')||'',name:n.getAttribute('name')||'',class:n.className||'',dataQuery:n.hasAttribute('data-v275-query'),dataFilter:n.getAttribute('data-v275-filter')||'',placeholder:n.getAttribute('placeholder')||'',value:n.value||''}));
    return {
      hash:location.hash,
      body_class:document.body.className,
      table_exists:Boolean(table),
      table_class:table?.className||'',
      table_enhanced:table?.dataset?.v275Enhanced||'',
      row_count:rows.length,
      row_cell_counts:rows.slice(0,5).map(r=>r.cells.length),
      first_row_text:(rows[0]?.innerText||'').replace(/\s+/g,' ').trim(),
      action_count:table?.querySelectorAll(kind==='domain'?'[data-v270-action="domain"]':'[data-v270-action="server"]').length||0,
      toolbar_exists:Boolean(toolbar),
      toolbar_html:toolbar?.outerHTML?.slice(0,1600)||'',
      visible_controls:inputs,
      script_srcs:[...document.scripts].map(s=>s.src).filter(src=>/v275-ua-workflow|v274-performance-bridge|v270-reference-lock/.test(src)),
      app_text:(app?.innerText||'').replace(/\s+/g,' ').trim().slice(0,2400),
      local_storage:Object.fromEntries(Object.entries(localStorage).filter(([k])=>k.includes('vf-infra-v275'))),
    };
  },{selector,kind});
}

try{
  await page.goto(`${base}/setup.php`,{waitUntil:'domcontentloaded'});
  await page.locator('#site_name').fill('VF Infra List Return Context Diagnostic');
  await page.locator('#password').fill(password);await page.locator('#password_confirm').fill(password);
  await Promise.all([page.waitForURL(/login\.php\?installed=1/),page.getByRole('button',{name:'安装并进入系统'}).click()]);
  await page.locator('#admin-password').fill(password);
  await Promise.all([page.waitForURL(/index\.php(?:#.*)?$/),page.getByRole('button',{name:'登录'}).click()]);
  const fixture=execFileSync('php',['tests/fixtures/v260-user-task-fixture.php',webRoot],{cwd:productRoot,encoding:'utf8'});
  if(!fixture.includes('P04_V260_USER_TASK_FIXTURE_PASS'))throw new Error('server fixture failed');
  const savedDomain=await page.evaluate(async()=>{
    const csrf=document.querySelector('meta[name="csrf-token"]')?.content||'';
    const response=await fetch('api.php?action=domain_save',{method:'POST',credentials:'same-origin',headers:{Accept:'application/json','Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify({domain:'infra-home.net',registrar:'Namecheap',renewal_price:'18.50',currency:'USD',renewal_policy:'manual',manual_expiry_date:'2026-12-18',notes:'Synthetic runtime diagnostic'})});
    return await response.json();
  });
  if(!savedDomain?.ok||!savedDomain?.domain?.id)throw new Error(`domain fixture failed ${JSON.stringify(savedDomain)}`);

  report.network=[];
  await page.goto(`${base}/index.php#domains`,{waitUntil:'domcontentloaded'});
  report.domain=await inventory('domain');
  await page.screenshot({path:`${evidence}/01-domains-runtime.png`,fullPage:true,animations:'disabled'});

  await page.goto(`${base}/index.php#servers`,{waitUntil:'domcontentloaded'});
  report.server=await inventory('server');
  await page.screenshot({path:`${evidence}/02-servers-runtime.png`,fullPage:true,animations:'disabled'});

  report.status='PASS';
}finally{
  fs.mkdirSync(evidence,{recursive:true});
  fs.writeFileSync(`${evidence}/P04_LIST_RETURN_CONTEXT_AUDIT.json`,JSON.stringify(report,null,2)+'\n');
  await browser.close();
}
console.log(`P04_LIST_RETURN_CONTEXT_DIAGNOSTIC=${report.status}`);
