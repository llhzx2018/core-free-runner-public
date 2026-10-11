'use strict';
const { chromium } = require('playwright');
const fs = require('node:fs');
const BASE='https://www3.m3u8.one';
const cases=[];
async function check(page,name,ok){cases.push({name,pass:Boolean(ok)});}
async function inspect(browser,slug,locale) {
 const page=await browser.newPage({viewport:{width:1440,height:900}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message.slice(0,130)));
 const res=await page.goto(BASE+slug,{waitUntil:'domcontentloaded',timeout:45000});
 await check(page,locale+' status',res.status()===200);
 await page.waitForFunction(()=>document.querySelector('[data-vf-module="playlist-checker"]')?.getAttribute('data-vf-playlist-checker-ready'),null,{timeout:25000});
 const root=page.locator('[data-vf-module="playlist-checker"]').first();
 await check(page,locale+' single module',await root.count()===1);
 await check(page,locale+' version',await root.getAttribute('data-vf-tool-version')==='1.25.82');
 await root.locator('[data-vf-playlist-action="sample-master"]').click();
 await page.waitForFunction(()=>document.querySelector('[data-vf-module="playlist-checker"]')?.getAttribute('data-vf-playlist-has-result')==='1',null,{timeout:30000});
 await check(page,locale+' real master sample',await root.locator('[data-vf-playlist-variants]').innerText()!=='0');
 await root.locator('[data-vf-playlist-mode-switch="pro"]').click();
 await check(page,locale+' professional mode',await root.getAttribute('data-vf-playlist-mode')==='pro');
 await check(page,locale+' professional labeled cells',await root.locator('[data-vf-playlist-pane="variants"] td[data-label]').count()>=5);
 await root.locator('[data-vf-playlist-action="sample-media"]').click();
 await page.waitForFunction(()=>document.querySelector('[data-vf-module="playlist-checker"]')?._vfPlaylistResult?.type==='media',null,{timeout:30000});
 await check(page,locale+' real media sample',Number(await root.locator('[data-vf-playlist-segments]').innerText())>0);
 for(const width of [768,390]){
   await page.setViewportSize({width,height:850});
   const dims=await page.evaluate(()=>({scroll:document.documentElement.scrollWidth,viewport:innerWidth,button:document.querySelector('[data-vf-playlist-action="analyze"]').getBoundingClientRect().height}));
   await check(page,locale+' '+width+'px no overflow',dims.scroll<=dims.viewport+2);
   await check(page,locale+' '+width+'px action >=44px',dims.button>=44);
 }
 await root.locator('[data-vf-playlist-action="clear"]').click();
 await check(page,locale+' clear resets result',await root.getAttribute('data-vf-playlist-has-result')!=='1');
 await check(page,locale+' no JS errors',errors.length===0);
 await page.close();
}
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{await inspect(browser,'/m3u8-playlist-checker/','en');await inspect(browser,'/zh/m3u8-playlist-checker/','zh');}
 finally{await browser.close();}
 const result={status:cases.every(x=>x.pass)?'PASS':'FAIL',production_mutated:false,checks:cases};
 fs.mkdirSync('proof',{recursive:true});
 fs.writeFileSync('proof/s01-checker-live-browser.json',JSON.stringify(result,null,2));
 console.log('S01_C03_LIVE_BROWSER',JSON.stringify(result));
 if(result.status!=='PASS')process.exitCode=1;
})().catch(err=>{console.error('S01_C03_BROWSER_RUN_ERROR',err.message);process.exitCode=1;});
