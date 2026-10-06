'use strict';
const fs=require('fs'),assert=require('assert/strict'),{chromium}=require('playwright'),{execFileSync}=require('child_process');
const probeUrl=route=>execFileSync('docker',['exec','--user','www-data','vf-v8-'+process.env.GITHUB_RUN_ID+'-wp','php','/usr/local/bin/wp','eval','wp_set_current_user(1);vf_theme_bootstrap_require_many(["enqueue.php"]);echo vf_toolsite_browser_probe_url(home_url('+JSON.stringify(route)+'));','--path=/var/www/html'],{encoding:'utf8'}).trim();
(async()=>{const browser=await chromium.launch({headless:true}),context=await browser.newContext(),page=await context.newPage(),base='http://127.0.0.1:18880';
await page.goto(base+'/wp-login.php');await page.locator('#user_login').fill('admin');await page.locator('#user_pass').fill('Synthetic-Only-Update-54!');await Promise.all([page.waitForURL(/wp-admin/),page.locator('#wp-submit').click()]);
await page.goto(probeUrl('/tool-notes/m3u8-player/'));await page.waitForFunction(()=>typeof vfToolSiteRunBrowserProbe==='function');
const css=await page.evaluate(()=>{
 const run=()=>vfToolSiteRunBrowserProbe().checks['production-public-css-bundle-present'];
 const baseline=run(),styles=[...document.querySelectorAll('link[data-vf-runtime-css="stable"]')].map(n=>({id:n.id,path:new URL(n.href).pathname}));
 const main=document.querySelector('link#vf-theme-public-runtime-css');if(!main)throw Error('main stylesheet missing');
 const copy=main.cloneNode(true);copy.id='duplicate-proof';document.head.append(copy);const duplicate=run();copy.remove();const parent=main.parentNode,next=main.nextSibling;main.remove();const missing=run();parent.insertBefore(main,next);
 return {baseline,duplicate,missing,styles,header:getComputedStyle(document.querySelector('.vf-site-header')).backgroundColor,active:document.querySelector('.vf-primary-nav .is-active')?getComputedStyle(document.querySelector('.vf-primary-nav .is-active')).backgroundColor:null};
});assert.equal(css.baseline.status,'PASS');assert.equal(css.duplicate.status,'FAIL');assert.equal(css.missing.status,'FAIL');assert(css.styles.length>=2,'reading supplement not exercised');
await page.setViewportSize({width:390,height:960});await page.goto(probeUrl('/tools/'));await page.waitForFunction(()=>typeof vfToolSiteRunBrowserProbe==='function');
const clipped=await page.evaluate(()=>{
 const count=()=>Number(vfToolSiteRunBrowserProbe().checks['responsive-touch-targets'].detail.match(/undersized=(\d+)/)[1]);
 const before=count(),group=document.createElement('div');group.className='vf-directory-filter-group';const button=document.createElement('button');button.textContent='Diagnostic';button.style.cssText='position:absolute;width:1px;height:1px;padding:0;min-height:0;border:0;clip:rect(0px,0px,0px,0px);clip-path:inset(50%)';group.append(button);document.body.append(group);const hidden=count();button.style.clip='auto';button.style.clipPath='none';const visible=count();group.remove();return {before,hidden,visible};
});assert.equal(clipped.hidden,clipped.before);assert.equal(clipped.visible,clipped.before+1);
fs.mkdirSync('proof',{recursive:true});fs.writeFileSync('proof/diagnostic-regression.json',JSON.stringify({status:'PASS',css,clipped,production:'NOT_EXECUTED'},null,2));await browser.close();})().catch(e=>{console.error(e);process.exit(1)});
