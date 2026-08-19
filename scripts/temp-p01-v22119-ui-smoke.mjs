import fs from 'node:fs';
import { chromium } from 'playwright-core';

const base = 'http://127.0.0.1:18119';
const browser = await chromium.launch({headless:true, executablePath:'/usr/bin/google-chrome', args:['--no-sandbox']});
const context = await browser.newContext({viewport:{width:1440,height:1000}});
const page = await context.newPage();
const result = {front:{}, admin:{}, widths:{}};

await page.goto(base+'/', {waitUntil:'domcontentloaded',timeout:15000});
await page.waitForSelector('.home-page', {timeout:12000});
await page.waitForSelector('html[data-vf-reference-ui="2"]',{timeout:5000});
await page.waitForTimeout(250);
result.front.attr = await page.evaluate(() => document.documentElement.getAttribute('data-vf-reference-ui'));
result.front.css = await page.evaluate(() => [...document.styleSheets].some(x => (x.href||'').includes('reference-ui.css')));
result.front.command = await page.locator('.command-hero').evaluate(el => getComputedStyle(el).display).catch(()=>'missing');
result.front.quick = await page.locator('.quick-link').count();
result.front.roots = await page.locator('.ref-home-categories .root-card').count();
result.front.categorySections = await page.locator('.ref-home-categories').count();
if(result.front.attr!=='2' || !result.front.css || !['none','missing'].includes(result.front.command) || result.front.roots<4 || result.front.categorySections!==1) throw new Error('FRONT_GATE '+JSON.stringify(result.front));
await page.screenshot({path:process.env.RUNNER_TEMP+'/p01-home-desktop.png',fullPage:true});
for (const w of [1920,1440,1280,1024,768,480,430,390,375]) {
  await page.setViewportSize({width:w,height:w<700?844:900}); await page.waitForTimeout(140);
  const v=await page.evaluate(()=>({client:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth,body:document.body.scrollWidth,search:document.querySelector('.top-search')?.getBoundingClientRect().width||0}));
  result.widths['front_'+w]=v; if(v.scroll>v.client+1 || v.body>v.client+1) throw new Error('FRONT_OVERFLOW_'+w+' '+JSON.stringify(v));
  if(w<=700 && v.search>44) throw new Error('MOBILE_SEARCH_'+w+' '+JSON.stringify(v));
}
await page.setViewportSize({width:390,height:844}); await page.screenshot({path:process.env.RUNNER_TEMP+'/p01-home-mobile.png',fullPage:true});

const login=await context.request.post(base+'/api.php?action=login',{data:{password:process.env.ADMIN_PASS}});
if(!login.ok()) throw new Error('LOGIN_HTTP '+login.status()+' '+await login.text());
const loginJson=await login.json();if(!loginJson.ok)throw new Error('LOGIN_API '+JSON.stringify(loginJson));
await page.setViewportSize({width:1440,height:1000});
await page.goto(base+'/links-admin.php',{waitUntil:'domcontentloaded',timeout:15000});
await page.waitForSelector('#linksBody tr',{timeout:12000});
await page.waitForSelector('html[data-vf-reference-ui="2"]',{timeout:5000});
result.admin.rails=await page.locator('.vf-admin-rail').count();
result.admin.rows=await page.locator('#linksBody tr').count();
result.admin.css=await page.evaluate(()=>[...document.styleSheets].some(x=>(x.href||'').includes('reference-ui.css')));
result.admin.page=await page.evaluate(()=>document.body.dataset.vfPage||'');
result.admin.batch0=await page.locator('#batchBar').evaluate(el=>getComputedStyle(el).display);
const checks=page.locator('#linksBody input[type=checkbox]');
if(await checks.count()>=2){ await checks.nth(0).check(); await checks.nth(1).check(); await page.waitForTimeout(100); }
result.admin.batch2=await page.locator('#batchBar').evaluate(el=>getComputedStyle(el).display);
if(result.admin.rails!==1 || result.admin.rows<8 || !result.admin.css || result.admin.page!=='links-admin' || result.admin.batch0!=='none' || result.admin.batch2==='none') throw new Error('ADMIN_GATE '+JSON.stringify(result.admin));
await page.screenshot({path:process.env.RUNNER_TEMP+'/p01-admin-desktop.png',fullPage:true});
for (const w of [1440,1024,768,480,430,390,375]) {
  await page.setViewportSize({width:w,height:w<700?844:900}); await page.waitForTimeout(140);
  const v=await page.evaluate(()=>({client:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth,body:document.body.scrollWidth,rails:document.querySelectorAll('.vf-admin-rail').length}));
  result.widths['admin_'+w]=v; if(v.scroll>v.client+1 || v.body>v.client+1) throw new Error('ADMIN_OVERFLOW_'+w+' '+JSON.stringify(v)); if(v.rails!==1) throw new Error('ADMIN_RAIL_'+w);
}
await page.setViewportSize({width:390,height:844}); await page.screenshot({path:process.env.RUNNER_TEMP+'/p01-admin-mobile.png',fullPage:true});
fs.writeFileSync('/tmp/p01-ui-result.json',JSON.stringify(result,null,2));
await browser.close();
console.log('P01_REFERENCE_UI_BROWSER=PASS');
