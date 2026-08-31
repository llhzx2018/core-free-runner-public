import { chromium } from 'playwright';
import fs from 'node:fs';

const base=process.env.VF_E2E_BASE_URL||'http://127.0.0.1:19057';
const evidence=process.env.EVIDENCE,candidate=process.env.CANDIDATE;
if(!evidence||!candidate)throw new Error('diagnostic environment missing');
const password='Vf'+crypto.randomUUID().replaceAll('-','')+'Aa1';
const report={schema:'p04-domain-quick-menu-runtime-diagnostic/v3',source_sha:candidate,status:'FAIL',before:{},pointer:{after_down:{},after_up:{}},dom_click:{},page_errors:[],console_errors:[],production_actions_executed:false,synthetic_test_data_only:true};
const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:1365,height:900}});
page.on('pageerror',e=>report.page_errors.push(String(e?.stack||e)));
page.on('console',m=>{if(m.type()==='error')report.console_errors.push(m.text())});
const installTrace=()=>page.evaluate(()=>{
  const key='p04-quick-menu-trace';sessionStorage.setItem(key,'[]');
  const read=()=>{try{return JSON.parse(sessionStorage.getItem(key)||'[]')}catch{return[]}};
  const push=(type,extra={})=>{const rows=read();rows.push({type,at:Date.now(),href:location.href,hash:location.hash,scrollY,...extra});sessionStorage.setItem(key,JSON.stringify(rows));};
  const matchQuick=node=>node instanceof Element&&(node.classList.contains('v275-more-button')||node.classList.contains('v275-quick-menu')||node.querySelector?.('.v275-more-button,.v275-quick-menu'));
  const observer=new MutationObserver(records=>records.forEach(record=>{
    record.addedNodes.forEach(node=>{if(matchQuick(node))push('quick-dom-added',{node:node instanceof Element?node.outerHTML.slice(0,900):node.nodeName});});
    record.removedNodes.forEach(node=>{if(matchQuick(node))push('quick-dom-removed',{node:node instanceof Element?node.outerHTML.slice(0,900):node.nodeName});});
  }));observer.observe(document.body,{childList:true,subtree:true});
  for(const type of ['pointerdown','mousedown','pointerup','mouseup','click','pointercancel']) document.addEventListener(type,event=>push(`${type}-capture`,{target:event.target?.className||event.target?.tagName||''}),true);
  window.addEventListener('scroll',()=>push('scroll-capture'),true);window.addEventListener('hashchange',()=>push('hashchange'),true);window.addEventListener('beforeunload',()=>push('beforeunload'),true);
  push('trace-installed');
});
const collect=(x,y)=>page.evaluate(({x,y})=>{
  const menu=document.querySelector('.v275-quick-menu'),open=menu?.querySelector('[data-action="open"]')||null,hit=document.elementFromPoint(x,y),active=document.activeElement;
  let trace=[];try{trace=JSON.parse(sessionStorage.getItem('p04-quick-menu-trace')||'[]')}catch{}
  return{url:location.href,hash:location.hash,menu_exists:Boolean(menu),open_exists:Boolean(open),button_count:document.querySelectorAll('.v275-more-button').length,hit:{tag:hit?.tagName||'',className:hit?.className||'',text:hit?.textContent?.trim()||''},active:{tag:active?.tagName||'',className:active?.className||'',text:active?.textContent?.trim()||''},trace};
},{x,y});
const readyDomain=async()=>{
  await page.goto(`${base}/index.php?audit=${Date.now()}#domains`,{waitUntil:'domcontentloaded'});
  const toolbar=page.locator('[data-v275-toolbar="domains"]');await toolbar.waitFor({state:'visible',timeout:15000});
  const input=toolbar.locator('[data-v275-query]');await input.fill('infra-home');await page.waitForTimeout(300);
  const trigger=page.locator('table.domain-table .v275-more-button:visible').first();await trigger.waitFor({state:'visible',timeout:10000});return{input,trigger};
};
try{
  await page.goto(`${base}/setup.php`,{waitUntil:'domcontentloaded'});await page.locator('#site_name').fill('VF Infra Quick Menu Diagnostic');await page.locator('#password').fill(password);await page.locator('#password_confirm').fill(password);
  await Promise.all([page.waitForURL(/login\.php\?installed=1/),page.getByRole('button',{name:'安装并进入系统'}).click()]);await page.locator('#admin-password').fill(password);await Promise.all([page.waitForURL(/index\.php(?:#.*)?$/),page.getByRole('button',{name:'登录'}).click()]);
  const saved=await page.evaluate(async()=>{const csrf=document.querySelector('meta[name="csrf-token"]')?.content||'';const response=await fetch('api.php?action=domain_save',{method:'POST',credentials:'same-origin',headers:{Accept:'application/json','Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify({domain:'infra-home.net',registrar:'Namecheap',renewal_price:'18.50',currency:'USD',renewal_policy:'manual',manual_expiry_date:'2026-12-18',notes:'Synthetic quick-menu audit'})});return await response.json();});if(!saved?.ok||!saved?.domain?.id)throw new Error(`domain seed failed ${JSON.stringify(saved)}`);

  let {input,trigger}=await readyDomain();const box=await trigger.boundingBox(),x=box.x+box.width/2,y=box.y+box.height/2,handle=await trigger.elementHandle();
  report.before={url:page.url(),query:await input.inputValue(),trigger_box:box,trigger_id:await trigger.getAttribute('data-v275-domain-actions'),connected:await handle.evaluate(el=>el.isConnected)};
  await installTrace();await page.mouse.move(x,y);await page.mouse.down();await page.waitForTimeout(120);
  report.pointer.after_down={...(await collect(x,y)),original:await handle.evaluate(el=>({connected:el.isConnected,className:el.className,outer:el.outerHTML.slice(0,700)})).catch(e=>({evaluate_error:String(e)}))};
  await page.mouse.up();await page.waitForTimeout(180);
  report.pointer.after_up={...(await collect(x,y)),original:await handle.evaluate(el=>({connected:el.isConnected,className:el.className,outer:el.outerHTML.slice(0,700)})).catch(e=>({evaluate_error:String(e)}))};
  await page.screenshot({path:`${evidence}/01-domain-quick-menu-pointer-lifecycle.png`,fullPage:true,animations:'disabled'});

  ({input,trigger}=await readyDomain());await installTrace();await page.evaluate(()=>document.querySelector('table.domain-table .v275-more-button')?.click());await page.waitForTimeout(180);report.dom_click=await collect((await trigger.boundingBox()).x+19,(await trigger.boundingBox()).y+19);
  await page.screenshot({path:`${evidence}/02-domain-quick-menu-dom-click.png`,fullPage:true,animations:'disabled'});report.status='PASS';
}finally{fs.mkdirSync(evidence,{recursive:true});fs.writeFileSync(`${evidence}/P04_LIST_RETURN_CONTEXT_AUDIT.json`,JSON.stringify(report,null,2)+'\n');await browser.close();}
console.log(`P04_LIST_RETURN_CONTEXT_AUDIT=${report.status}`);
