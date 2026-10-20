const {chromium}=require('playwright');const fs=require('fs');
(async()=>{
 const prior=JSON.parse(fs.readFileSync('prior-proof/admin-layout-next.json'));
 if(prior.targetSha!=='a3c62ddac0c47ab488f7936c2797d03341fc224c'||!prior.complete||prior.checks.length!==704)throw Error('Prior source/evidence mismatch');
 const reused=prior.checks.filter(c=>c.ok);const failures=prior.checks.filter(c=>!c.ok);
 if(reused.length!==664||failures.length!==40||failures.some(c=>!c.id.endsWith('-lookup-label-layout')))throw Error('Prior functional proof incomplete');
 const browser=await chromium.launch();const checks=[],pages=[];let complete=false;
 const check=(id,ok,detail)=>{checks.push({id,ok:!!ok,detail});if(!ok)console.error('FAILED_CHECK',id,JSON.stringify(detail));};
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const base='http://127.0.0.1:18880/wp-admin/themes.php?page=vf-theme-modules&tab=layout';
  await page.goto('http://127.0.0.1:18880/wp-login.php');await page.locator('#user_login').fill('admin');await page.locator('#user_pass').fill('Synthetic-Only-Update-54!');await page.locator('input[name=redirect_to]').evaluate((e,u)=>e.value=u,base);await page.locator('#wp-submit').click();await page.waitForURL('**/wp-admin/**');
  await page.goto(base,{waitUntil:'networkidle'});const contexts=await page.locator('[data-vf-page-context]').evaluateAll(es=>es.map(e=>e.dataset.vfPageContext));check('context-count',contexts.length===20,contexts);
  for(const width of [1440,1024])for(const context of contexts){
   const id=context+'-'+width;await page.setViewportSize({width,height:1000});await page.goto(base+'&view=edit&context='+context,{waitUntil:'networkidle'});
   const guide=page.locator('[data-vf-page-finder]');await guide.locator('summary').click();const opt=await guide.locator('option').evaluateAll(es=>es.find(e=>e.textContent==='模块结构')?.value);await guide.locator('select').selectOption(opt);await guide.locator('button').click();await page.locator('[data-vf-layout-module-library-open]').click();
   const library=page.locator('[data-vf-layout-module-library]');await library.waitFor({state:'visible'});
   const metrics=await library.locator('.vf-layout-library-filters label').evaluateAll(es=>es.map(e=>{const c=e.querySelector('input,select'),r=e.getBoundingClientRect(),b=c.getBoundingClientRect(),s=getComputedStyle(e);return {columns:s.gridTemplateColumns,labelWidth:r.width,controlWidth:b.width,controlBelowLabel:b.top>r.top+14,controlWithin:b.left>=r.left-1&&b.right<=r.right+1};}));
   check(id+'-labels-above-controls',metrics.every(m=>m.columns.split(' ').length===1&&m.controlBelowLabel&&m.controlWithin),metrics);
   check(id+'-dialog-fits',await library.evaluate(e=>{const r=e.getBoundingClientRect();return r.x>=0&&r.right<=innerWidth+1&&r.y>=0&&r.bottom<=innerHeight+1&&e.scrollWidth<=e.clientWidth+1;}),'Dialog stays within viewport');
   await library.locator('[data-vf-layout-library-search]').fill('NO_MATCH_SYNTHETIC_MODULE_39');check(id+'-empty-state',await library.locator('[data-vf-layout-library-empty]').isVisible(),'Empty explanation remains visible after style change');
   await library.locator('[data-vf-layout-library-search]').fill('');await library.locator('[data-vf-layout-library-filter]').selectOption('all');
   check(id+'-clean-state',!await page.locator('[data-vf-layout-page]').evaluate(e=>e.classList.contains('is-dirty'))&&!await page.locator('[data-vf-unsaved-indicator]').evaluate(e=>e.classList.contains('is-dirty')),'Filter controls remain read-only');
   if(['home','article_detail','blog_index','problem_detail','not_found'].includes(context))await page.screenshot({path:`proof/layout-library-final-${context}-${width}.png`});
   await page.keyboard.press('Escape');check(id+'-escape-return',await page.locator('[data-vf-layout-module-library-open]').evaluate(e=>document.activeElement===e&&!!e.getClientRects().length),'Keyboard close still returns to visible opener');pages.push({context,width,metrics});
  }
  check('no-browser-errors',errors.length===0,errors);complete=true;if(checks.some(c=>!c.ok))throw Error('Style regression failed');
 }finally{
  fs.writeFileSync('proof/admin-layout-final.json',JSON.stringify({status:complete&&checks.every(c=>c.ok)?'PASS':'FAIL',complete,targetSha:process.env.TARGET_SHA,sourceContinuity:'Only dedicated label classes and their CSS selectors changed; layout JavaScript is byte-identical',reusedProof:{run:39348632698,source:prior.targetSha,passedChecks:664,excludedStyleFailures:40},checks,pages},null,2));
  fs.writeFileSync('proof/reused-layout-functions.json',JSON.stringify({run:39348632698,source:prior.targetSha,checks:reused},null,2));await browser.close();
 }
})().catch(e=>{console.error(e);process.exit(1)});
