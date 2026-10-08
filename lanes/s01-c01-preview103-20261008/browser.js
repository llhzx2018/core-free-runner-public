'use strict';
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const {execFileSync}=require('child_process');
const base='http://127.0.0.1:18880',url=base+'/wp-admin/themes.php?page=vf-theme-modules&tab=preview';
const cli=php=>execFileSync('docker',['exec','--user','www-data',process.env.WP,'php','/usr/local/bin/wp','eval',php,'--path=/var/www/html'],{encoding:'utf8',maxBuffer:16*1024*1024});
const output=(file,data)=>fs.writeFileSync(path.join('proof',file),JSON.stringify(data,null,2));
async function login(page){await page.goto(base+'/wp-login.php');await page.locator('#user_login').fill('admin');await page.locator('#user_pass').fill('Synthetic-Only-Update-54!');await Promise.all([page.waitForURL(/wp-admin/),page.locator('#wp-submit').click()]);}
(async()=>{
 const browser=await chromium.launch({headless:true});
 const context=await browser.newContext({viewport:{width:1440,height:1000},timezoneId:'Asia/Shanghai',acceptDownloads:true});
 const page=await context.newPage();let errors=[];page.on('pageerror',e=>errors.push(e.message));
 try{
  await login(page);await page.goto(url);await page.waitForFunction(()=>document.querySelector('[data-vf-preview-page]')?.dataset.scriptReady==='1');
  const samples=[];
  await page.waitForLoadState('networkidle');
  for(let i=0;i<5;i++){
   await page.goto(url);await page.waitForLoadState('networkidle');
   samples.push(await page.evaluate(()=>({duration:performance.getEntriesByType('navigation')[0].duration,requests:performance.getEntriesByType('resource').length,nodes:document.querySelectorAll('*').length})));
  }
  const median=key=>samples.map(s=>s[key]).sort((a,b)=>a-b)[2];
  const performanceRow={duration_ms:median('duration'),requests:median('requests'),nodes:median('nodes'),samples};
  if(process.argv[2]==='baseline'){
   await page.locator('[data-vf-preview-workflow-step="preview"]').click();
   assert.equal(await page.locator('[data-vf-preview-load]').count(),0);
   assert(await page.locator('[data-vf-preview-canvas]').isHidden());
   output('preview-baseline.json',{status:'REPRODUCED',version:process.env.SOURCE_VERSION,independent_preview_action:'MISSING',iframe:'EMPTY_UNTIL_ACCEPTANCE_TASK',performance:performanceRow,production:'NOT_EXECUTED'});
   await page.screenshot({path:'proof/preview-baseline.png',fullPage:true});return;
  }
  const reference=JSON.parse(fs.readFileSync('proof/preview-baseline.json','utf8')).performance;
  assert(performanceRow.requests<=reference.requests+1,'extra initial background work');
  assert(performanceRow.nodes<=reference.nodes+5,'unexpected DOM growth');
  assert(performanceRow.duration_ms<=Math.max(reference.duration_ms*1.5,reference.duration_ms+400),'significant initial-load regression');
  output('performance.json',{status:'PASS',environment:'SAME_DISPOSABLE_WORDPRESS_AND_SEEDED_DATA',method:'one warmup and five warm navigation samples per version; medians',baseline:reference,current:performanceRow,initial_requests_added:performanceRow.requests-reference.requests,duration_delta_ms:performanceRow.duration_ms-reference.duration_ms});
  const controls=require('../target/tests/preview-controls-browser-check.js');
  const independent=require('../target/tests/preview-independent-browser-check.js');
  const canonical=()=>cli('global $wpdb;echo hash("sha256",serialize($wpdb->get_results("SELECT option_name,option_value FROM {$wpdb->options} WHERE option_name LIKE \'vf_theme_%\' OR option_name LIKE \'vf_tools_theme_%\' ORDER BY option_name",ARRAY_A)));');
  const before=canonical(),rows=[];
  for(const width of [1440,1280,1024,768,390,360]){
   await page.setViewportSize({width,height:1000});await page.goto(url);const a=await controls(page,{width,out:'proof'});
   await page.goto(url);const b=await independent(page,{width,out:'proof'});rows.push({width,controls:a,independent:b});
  }
  assert.equal(canonical(),before,'manual preview mutated Theme canonical state');
  output('preview-controls.json',{status:'PASS',environment:'REAL_ISOLATED_WORDPRESS',rows,canonical_state_preserved:true,production:'NOT_EXECUTED'});
  await page.setViewportSize({width:1440,height:1000});await page.goto(url);
  const root=page.locator('[data-vf-preview-page]');const jobs=[];
  page.on('response',async r=>{if(r.url().includes('admin-ajax.php')){const p=await r.json().catch(()=>null);if(p?.data?.job)jobs.push(p.data.job);}});
  await root.locator('[data-vf-preview-mode]').selectOption('sample');
  await root.locator('.vf-preview-v510__execution-options > summary').click();await root.locator('[data-vf-preview-speed]').selectOption('fast');
  await root.locator('[data-vf-preview-run]').click();
  assert(await root.locator('[data-vf-preview-load]').isDisabled(),'manual preview interferes with real run');
  await page.waitForFunction(()=>document.querySelector('[data-vf-preview-page]').getAttribute('aria-busy')==='false',{}, {timeout:480000});
  await root.locator('[data-vf-preview-workflow-step="results"]').click();
  const [download]=await Promise.all([page.waitForEvent('download'),root.locator('[data-vf-preview-download]').click()]);
  const artifact=JSON.parse(fs.readFileSync(await download.path(),'utf8'));assert.equal(artifact.evidenceState.browser,'complete');
  assert(jobs.some(j=>j.runId===artifact.runId&&j.artifactHash===artifact.hash&&j.stateIntegrity.verified));
  const initialArtifact=artifact.hash;await root.locator('[data-vf-preview-workflow-step="preview"]').click();await root.locator('[data-vf-preview-load]').click();
  await page.waitForFunction(()=>document.querySelector('[data-vf-preview-page]').getAttribute('aria-busy')==='false',{}, {timeout:45000});
  await root.locator('[data-vf-preview-workflow-step="results"]').click();
  const [second]=await Promise.all([page.waitForEvent('download'),root.locator('[data-vf-preview-download]').click()]);
  assert.equal(JSON.parse(fs.readFileSync(await second.path(),'utf8')).hash,initialArtifact,'manual viewing replaced genuine evidence');
  output('preview-artifact-preservation.json',{status:'PASS',run_id:artifact.runId,hash:artifact.hash,actual_verdict:artifact.status,manual_preview_preserves_download:true});
  await root.locator('[data-vf-preview-workflow-step="preview"]').click();
  await require('../target/tests/preview-workflow-browser-check.js')(page,{url,out:'proof',previousArtifact:artifact,cli});
  output('preview-browser-errors.json',{status:errors.length?'FAIL':'PASS',errors});assert.deepEqual(errors,[]);
 }catch(error){output('preview-browser-failure.json',{status:'FAIL',message:error.message,stack:error.stack,errors});await page.screenshot({path:'proof/preview-browser-failure.png',fullPage:true}).catch(()=>{});throw error;}
 finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
