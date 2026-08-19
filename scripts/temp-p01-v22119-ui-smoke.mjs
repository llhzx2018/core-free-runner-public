import fs from 'node:fs';
import { chromium } from 'playwright-core';

const base = 'http://127.0.0.1:18119';
const browser = await chromium.launch({headless:true, executablePath:'/usr/bin/google-chrome', args:['--no-sandbox']});
const context = await browser.newContext({viewport:{width:1440,height:1000}});
const page = await context.newPage();
const result = {front:{}, admin:{}, widths:{}};

await page.goto(base+'/', {waitUntil:'networkidle'});
await page.waitForSelector('.home-page', {timeout:12000});
result.front.attr = await page.evaluate(() => document.documentElement.getAttribute('data-vf-reference-ui'));
result.front.css = await page.evaluate(() => performance.getEntriesByType('resource').some(x => x.name.includes('reference-ui.css')));
result.front.command = await page.locator('.command-hero').evaluate(el => getComputedStyle(el).display).catch(()=>'missing');
result.front.quick = await page.locator('.quick-link').count();
result.front.roots = await page.locator('.root-card').count();
result.front.order = await page.evaluate(() => { const s=document.querySelector('.spaces'), h=document.querySelector('.home-columns'); return !!(s&&h&&(s.compareDocumentPosition(h)&Node.DOCUMENT_POSITION_FOLLOWING)); });
if(result.front.attr!=='1' || !result.front.css || !['none','missing'].includes(result.front.command) || result.front.roots<4 || !result.front.order) throw new Error('FRONT_GATE '+JSON.stringify(result.front));
await page.screenshot({path:process.env.RUNNER_TEMP+'/p01-home-desktop.png',fullPage:true});
for (const w of [1440,1280,1024,768,430,390,375]) {
  await page.setViewportSize({width:w,height:w<700?844:900}); await page.waitForTimeout(100);
  const v=await page.evaluate(()=>({client:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth,body:document.body.scrollWidth}));
  result.widths['front_'+w]=v; if(v.scroll>v.client || v.body>v.client) throw new Error('FRONT_OVERFLOW_'+w+' '+JSON.stringify(v));
}
await page.setViewportSize({width:390,height:844}); await page.screenshot({path:process.env.RUNNER_TEMP+'/p01-home-mobile.png',fullPage:true});

await page.setViewportSize({width:1440,height:1000});
await page.goto(base+'/login.php',{waitUntil:'domcontentloaded'});
await page.locator('input[type=password]').fill(process.env.ADMIN_PASS);
await page.locator('button[type=submit],input[type=submit]').first().click();
await page.waitForLoadState('networkidle');
await page.goto(base+'/links-admin.php',{waitUntil:'networkidle'});
await page.waitForSelector('#linksBody tr',{timeout:12000});
result.admin.rails=await page.locator('.vf-admin-rail').count();
result.admin.rows=await page.locator('#linksBody tr').count();
result.admin.css=await page.evaluate(()=>performance.getEntriesByType('resource').some(x=>x.name.includes('reference-ui.css')));
result.admin.batch0=await page.locator('#batchBar').evaluate(el=>getComputedStyle(el).display);
const checks=page.locator('#linksBody input[type=checkbox]');
if(await checks.count()>=2){ await checks.nth(0).check(); await checks.nth(1).check(); await page.waitForTimeout(100); }
result.admin.batch2=await page.locator('#batchBar').evaluate(el=>getComputedStyle(el).display);
if(result.admin.rails!==1 || result.admin.rows<8 || !result.admin.css || result.admin.batch0!=='none' || result.admin.batch2==='none') throw new Error('ADMIN_GATE '+JSON.stringify(result.admin));
await page.screenshot({path:process.env.RUNNER_TEMP+'/p01-admin-desktop.png',fullPage:true});
for (const w of [1440,1024,768,430,390,375]) {
  await page.setViewportSize({width:w,height:w<700?844:900}); await page.waitForTimeout(100);
  const v=await page.evaluate(()=>({client:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth,body:document.body.scrollWidth}));
  result.widths['admin_'+w]=v; if(v.scroll>v.client || v.body>v.client) throw new Error('ADMIN_OVERFLOW_'+w+' '+JSON.stringify(v));
}
await page.setViewportSize({width:390,height:844}); await page.screenshot({path:process.env.RUNNER_TEMP+'/p01-admin-mobile.png',fullPage:true});
fs.writeFileSync('/tmp/p01-ui-result.json',JSON.stringify(result,null,2));
await browser.close();
