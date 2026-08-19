import fs from 'node:fs';
import { chromium } from 'playwright-core';

const base = process.env.BASE_URL || 'http://127.0.0.1:18521';
const browser = await chromium.launch({headless:true, executablePath:'/usr/bin/google-chrome', args:['--no-sandbox']});
const context = await browser.newContext({viewport:{width:1440,height:900}});
const page = await context.newPage();
const result = {front:{},admin:{},widths:{}};

await page.goto(base+'/',{waitUntil:'domcontentloaded',timeout:15000});
await page.waitForSelector('html[data-vf-reference-ui="2"]',{timeout:10000});
await page.waitForSelector('.home-page',{timeout:10000});
await page.waitForTimeout(180);
result.front=await page.evaluate(()=>({
  ref:document.documentElement.dataset.vfReferenceUi,
  css:[...document.styleSheets].some(x=>(x.href||'').includes('reference-ui.css')),
  roots:document.querySelectorAll('.ref-home-categories .root-card').length,
  categories:document.querySelectorAll('.ref-home-categories').length,
  hero:document.querySelector('.command-hero')?getComputedStyle(document.querySelector('.command-hero')).display:'missing'
}));
if(result.front.ref!=='2'||!result.front.css||result.front.roots<4||result.front.categories!==1||!['none','missing'].includes(result.front.hero))throw new Error('FRONT_GATE '+JSON.stringify(result.front));
for(const width of [1920,1440,1280,1024,768,480,430,390,375]){
  await page.setViewportSize({width,height:width<700?844:900});await page.waitForTimeout(120);
  const v=await page.evaluate(()=>({client:document.documentElement.clientWidth,html:document.documentElement.scrollWidth,body:document.body.scrollWidth,search:document.querySelector('.top-search')?.getBoundingClientRect().width||0}));
  if(v.html>v.client+1||v.body>v.client+1)throw new Error('FRONT_OVERFLOW '+width+' '+JSON.stringify(v));
  if(width<=700&&v.search>44)throw new Error('MOBILE_SEARCH '+width+' '+JSON.stringify(v));
  result.widths['front_'+width]=v;
}
await page.setViewportSize({width:1440,height:900});
const login=await page.evaluate(async pass=>{const r=await fetch('/api.php?action=login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:pass})});return {status:r.status,body:await r.json()};},process.env.ADMIN_PASS);
if(login.status!==200||!login.body.ok)throw new Error('LOGIN_GATE '+JSON.stringify(login));
await page.goto(base+'/links-admin.php',{waitUntil:'domcontentloaded',timeout:15000});
await page.waitForSelector('#linksBody tr',{timeout:10000});
await page.waitForSelector('html[data-vf-reference-ui="2"]',{timeout:5000});
result.admin=await page.evaluate(()=>({
  rails:document.querySelectorAll('.vf-admin-rail').length,
  rows:document.querySelectorAll('#linksBody tr').length,
  css:[...document.styleSheets].some(x=>(x.href||'').includes('reference-ui.css')),
  page:document.body.dataset.vfPage||'',
  batch:getComputedStyle(document.getElementById('batchBar')).display
}));
if(result.admin.rails!==1||result.admin.rows<8||!result.admin.css||result.admin.page!=='links-admin'||result.admin.batch!=='none')throw new Error('ADMIN_GATE '+JSON.stringify(result.admin));
const checks=page.locator('#linksBody input[type=checkbox]');
await checks.nth(0).check();await checks.nth(1).check();await page.waitForTimeout(80);
if(await page.locator('#batchBar').evaluate(el=>getComputedStyle(el).display==='none'))throw new Error('BATCH_GATE');
for(const width of [1440,1024,768,480,430,390,375]){
  await page.setViewportSize({width,height:width<700?844:900});await page.waitForTimeout(120);
  const v=await page.evaluate(()=>({client:document.documentElement.clientWidth,html:document.documentElement.scrollWidth,body:document.body.scrollWidth,rails:document.querySelectorAll('.vf-admin-rail').length}));
  if(v.html>v.client+1||v.body>v.client+1||v.rails!==1)throw new Error('ADMIN_RESPONSIVE '+width+' '+JSON.stringify(v));
  result.widths['admin_'+width]=v;
}
fs.writeFileSync('/tmp/p01-v22119-browser.json',JSON.stringify(result,null,2));
await browser.close();
console.log('P01_V22119_REFERENCE_UI=PASS');
