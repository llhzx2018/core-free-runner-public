import { chromium } from 'playwright';
import fs from 'node:fs';

const base=process.env.VF_E2E_BASE_URL||'http://127.0.0.1:19057';
const evidence=process.env.EVIDENCE,candidate=process.env.CANDIDATE;
if(!evidence||!candidate)throw new Error('diagnostic environment missing');
const password='Vf'+crypto.randomUUID().replaceAll('-','')+'Aa1';
const report={schema:'p04-domain-quick-menu-runtime-diagnostic/v2',source_sha:candidate,status:'FAIL',before:{},mouse_click:{},dom_click:{},page_errors:[],console_errors:[],production_actions_executed:false,synthetic_test_data_only:true};
const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:1365,height:900}});
page.on('pageerror',e=>report.page_errors.push(String(e?.stack||e)));
page.on('console',m=>{if(m.type()==='error')report.console_errors.push(m.text())});
const installTrace=()=>page.evaluate(()=>{
  const key='p04-quick-menu-trace';sessionStorage.setItem(key,'[]');
  const read=()=>{try{return JSON.parse(sessionStorage.getItem(key)||'[]')}catch{return[]}};
  const push=(type,extra={})=>{const rows=read();rows.push({type,at:Date.now(),href:location.href,hash:location.hash,scrollY,...extra});sessionStorage.setItem(key,JSON.stringify(rows));};
  const observer=new MutationObserver(records=>records.forEach(record=>{
    record.addedNodes.forEach(node=>{if(node instanceof Element&&node.classList.contains('v275-quick-menu'))push('menu-added',{html:node.outerHTML.slice(0,1000)});});
    record.removedNodes.forEach(node=>{if(node instanceof Element&&node.classList.contains('v275-quick-menu'))push('menu-removed');});
  }));observer.observe(document.body,{childList:true});
  document.addEventListener('pointerdown',event=>push('pointerdown-capture',{target:event.target?.className||event.target?.tagName||''}),true);
  document.addEventListener('click',event=>push('click-capture',{target:event.target?.className||event.target?.tagName||''}),true);
  window.addEventListener('scroll',()=>push('scroll-capture'),true);window.addEventListener('hashchange',()=>push('hashchange'),true);window.addEventListener('beforeunload',()=>push('beforeunload'),true);
  push('trace-installed');
});
const collect=()=>page.evaluate(()=>{
  const menu=document.querySelector('.v275-quick-menu'),open=menu?.querySelector('[data-action="open"]')||null;
  const mr=menu?.getBoundingClientRect()||null,or=open?.getBoundingClientRect()||null,style=menu?getComputedStyle(menu):null;
  let trace=[];try{trace=JSON.parse(sessionStorage.getItem('p04-quick-menu-trace')||'[]')}catch{}
  return{url:location.href,hash:location.hash,menu_exists:Boolean(menu),open_exists:Boolean(open),menu_box:mr?{x:mr.x,y:mr.y,width:mr.width,height:mr.height}:null,open_box:or?{x:or.x,y:or.y,width:or.width,height:or.height}:null,display:style?.display||'',visibility:style?.visibility||'',opacity:style?.opacity||'',trace};
});
const readyDomain=async()=>{
  await page.goto(`${base}/index.php?audit=${Date.now()}#domains`,{waitUntil:'domcontentloaded'});
  const toolbar=page.locator('[data-v275-toolbar="domains"]');await toolbar.waitFor({state:'visible',timeout:15000});
  const input=toolbar.locator('[data-v275-query]');await input.fill('infra-home');await page.waitForTimeout(300);
  const trigger=page.locator('table.domain-table .v275-more-button:visible').first();await trigger.waitFor({state:'visible',timeout:10000});
  return{input,trigger};
};
try{
  await page.goto(`${base}/setup.php`,{waitUntil:'domcontentloaded'});
  await page.locator('#site_name').fill('VF Infra Quick Menu Diagnostic');await page.locator('#password').fill(password);await page.locator('#password_confirm').fill(password);
  await Promise.all([page.waitForURL(/login\.php\?installed=1/),page.getByRole('button',{name:'安装并进入系统'}).click()]);
  await page.locator('#admin-password').fill(password);await Promise.all([page.waitForURL(/index\.php(?:#.*)?$/),page.getByRole('button',{name:'登录'}).click()]);
  const saved=await page.evaluate(async()=>{const csrf=document.querySelector('meta[name="csrf-token"]')?.content||'';const response=await fetch('api.php?action=domain_save',{method:'POST',credentials:'same-origin',headers:{Accept:'application/json','Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify({domain:'infra-home.net',registrar:'Namecheap',renewal_price:'18.50',currency:'USD',renewal_policy:'manual',manual_expiry_date:'2026-12-18',notes:'Synthetic quick-menu audit'})});return await response.json();});
  if(!saved?.ok||!saved?.domain?.id)throw new Error(`domain seed failed ${JSON.stringify(saved)}`);

  let {input,trigger}=await readyDomain();const box=await trigger.boundingBox();
  report.before={url:page.url(),hash:await page.evaluate(()=>location.hash),query:await input.inputValue(),trigger_box:box,trigger_id:await trigger.getAttribute('data-v275-domain-actions')};
  await installTrace();await page.mouse.click(box.x+box.width/2,box.y+box.height/2);await page.waitForTimeout(220);report.mouse_click=await collect();
  await page.screenshot({path:`${evidence}/01-domain-quick-menu-mouse-click.png`,fullPage:true,animations:'disabled'});

  ({input,trigger}=await readyDomain());await installTrace();
  await page.evaluate(()=>document.querySelector('table.domain-table .v275-more-button')?.click());await page.waitForTimeout(220);report.dom_click=await collect();
  await page.screenshot({path:`${evidence}/02-domain-quick-menu-dom-click.png`,fullPage:true,animations:'disabled'});
  report.status='PASS';
}finally{
  fs.mkdirSync(evidence,{recursive:true});fs.writeFileSync(`${evidence}/P04_LIST_RETURN_CONTEXT_AUDIT.json`,JSON.stringify(report,null,2)+'\n');await browser.close();
}
console.log(`P04_LIST_RETURN_CONTEXT_AUDIT=${report.status}`);
