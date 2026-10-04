'use strict';
const fs=require('fs'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true}),page=await browser.newPage();
 await page.goto('http://127.0.0.1:18092/wp-login.php');
 await page.locator('#user_login').fill('admin');await page.locator('#user_pass').fill('Synthetic-Title-Fixture-Only!');
 await Promise.all([page.waitForNavigation(),page.locator('#wp-submit').click()]);
 const failures=[],cases=[];
 for(const width of [2560,1920,1600,1440,1366,1024,768,390]){
  await page.setViewportSize({width,height:1100});
  await page.goto('http://127.0.0.1:18092/wp-admin/admin.php?page=vf-toolsite-content&tab=workflow&section=queue',{waitUntil:'networkidle'});
  const m=await page.evaluate(()=>{
   const visible=e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden';};
   return {titles:[...document.querySelectorAll('.vf-v6-shell-main h1')].filter(visible).map(e=>e.textContent.trim()),kicker:[...document.querySelectorAll('.vf-r18-pagehead-kicker')].filter(visible).length,overflow:document.documentElement.scrollWidth>document.documentElement.clientWidth+2};
  });
  if(m.titles.length!==1||m.titles[0]!=='内容与 SEO 概览'||m.kicker||m.overflow)failures.push({width,...m});cases.push({width,...m});
 }
 await browser.close();
 const result={pass:failures.length===0,cases,failures,owner_product_pass:false,production:'NOT_TOUCHED'};
 fs.writeFileSync('evidence/native-browser.json',JSON.stringify(result,null,2));
 console.log(JSON.stringify(result));if(failures.length)process.exit(1);
})().catch(e=>{console.error(e);process.exit(1);});
