import { chromium } from 'playwright';

const origin=process.env.P01_TEST_ORIGIN || 'http://127.0.0.1:18621';
const password=process.env.P01_TEST_PASSWORD;
if(!password) throw new Error('BLOCKED_FIXTURE: synthetic owner password unavailable');
const passed=[],failed=[],notApplicable=[];
const expect=(ok,why)=>{if(!ok)throw new Error(why)};
const record=async(name,run)=>{
 try{await run();passed.push(name);console.log('BROWSER_PASS:'+name)}
 catch(e){failed.push({case:name,reason:String(e?.message||e).slice(0,300)});console.log('BROWSER_FAIL:'+name+':'+String(e?.message||e).slice(0,180))}
};
const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
try{
 const owner=await browser.newContext({viewport:{width:1440,height:900}});
 await owner.route(/https?:\/\/(?!127\.0\.0\.1)/,request=>request.abort());
 const login=await owner.request.post(origin+'/api.php?action=login',{data:{password}});
 expect(login.status()===200&&(await login.text()).includes('"ok":true'),'Synthetic Owner login failed');
 const page=await owner.newPage();
 const go=async(route)=>{const response=await page.goto(origin+'/'+route,{waitUntil:'domcontentloaded',timeout:30000});expect(response?.status()===200,'HTTP route '+route+' '+response?.status());await page.waitForFunction(()=>Boolean(window.VFLocalManagementReturn),null,{timeout:15000})};
 const modal=page.locator('dialog[data-vf-local-management]');
 const open=async()=>{
  const opener=page.locator('[data-vf-local-manage-open]');
  await opener.waitFor({state:'visible'});
  const before=new URL(page.url()).pathname;
  await opener.click();
  await modal.waitFor({state:'visible'});
  expect(await modal.evaluate(el=>el.open&&el.matches(':modal')),'single native modal not open');
  expect((await modal.locator('iframe').count())===0,'Iframe in management modal');
  expect(new URL(page.url()).pathname===before,'Unexpected navigation');
 };
 const task=async(id)=>{const b=modal.locator('[data-vf-local-task="'+id+'"]');await b.waitFor({state:'visible',timeout:10000});await b.click();expect((await b.getAttribute('aria-pressed'))==='true','Task not active: '+id)};
 const close=async()=>{await modal.locator('[data-vf-local-manage-close]').first().click();expect(!(await modal.evaluate(el=>el.open)),'Modal still open')};
 for(const width of [1440,768]){
  await page.setViewportSize({width,height:900});
  await record('start/'+width+'/compact-modal-and-sorting',async()=>{
   await go('start.php');
   await open();
   const dimensions=await modal.evaluate(el=>{const r=el.getBoundingClientRect();return{left:r.left,right:r.right,top:r.top,bottom:r.bottom,w:innerWidth,h:innerHeight}});
   expect(dimensions.left>=-2&&dimensions.right<=dimensions.w+2&&dimensions.top>=-2&&dimensions.bottom<=dimensions.h+2,'Dialog escapes viewport');
   const headings=await modal.locator('.vf-local-management-header,.vf-local-management-main>.vf-local-management-footer').evaluateAll(nodes=>nodes.map(n=>getComputedStyle(n).position));
   expect(headings.length===2&&headings.every(x=>x==='sticky'),'Title/footer not sticky');
   await task('category');
   expect((await modal.locator('[data-vf-local-current-title]').innerText()).includes('分类与排序'),'Task title hides sorting');
   expect(await modal.locator('[data-vf-local-category-order]').isVisible(),'Sorting action not discoverable');
   await close();
  });
  await record('start/'+width+'/paged-resources-search-and-bulk',async()=>{
   await go('start.php');
   await open();
   await task('resources');
   const rows=modal.locator('[data-vf-local-manage-list] li');
   expect(await rows.count()===12,'Initial list must render 12 rows, got '+await rows.count());
   const more=modal.locator('[data-vf-local-manage-more]');
   expect(await more.isVisible(),'Progressive-disclosure button missing');
   await more.click();
   expect(await rows.count()===24,'Show more must expand to 24');
   const search=modal.locator('[data-vf-local-manage-search]');
   await search.fill('Modal Fixture 27');
   expect(await rows.count()===1,'Search should reduce to 1 result');
   expect(!(await more.isVisible()),'Show-more should hide when no next page');
   await search.fill('');
   expect(await rows.count()===12,'Search reset should restore 12-row limit');
   await task('bulk');
   expect(await modal.locator('[data-vf-local-bulk-area]').isVisible(),'Bulk destination missing');
   const order=await modal.evaluate(el=>{
    const bulk=el.querySelector('[data-vf-local-bulk-area]');
    const list=el.querySelector('[data-vf-local-manage-list]');
    return bulk?.compareDocumentPosition(list)&Node.DOCUMENT_POSITION_FOLLOWING;
   });
   expect(Boolean(order),'Bulk controls must be before resource list');
   await close();
  });
 }
 await page.setViewportSize({width:1440,height:900});
 await record('channels/launcher-native-progress-retry-stop',async()=>{
  await go('channels.php?view=videos');
  const launcher=page.locator('[data-vf-channel-sync-open]');
  expect(await launcher.count()===1,'Synthetic YouTube channel launcher absent');
  expect(await launcher.isVisible(),'Channel sync launcher not visible');
  expect(!(await page.locator('[data-youtube-batch-runtime]').isVisible()),'Original batch controls leaked into browsing page');
  const before=new URL(page.url()).pathname;
  await launcher.click();
  await modal.waitFor({state:'visible'});
  expect(new URL(page.url()).pathname===before,'Channel sync navigated to backend');
  expect(await modal.locator('[data-vf-local-task="channel"]').getAttribute('aria-pressed')==='true','Channel task not active');
  expect(await modal.locator('[data-vf-local-channel-check]').isEnabled(),'Channel check action unavailable with synthetic source');
  await page.evaluate(()=>{
   const notice=document.querySelector('[data-youtube-batch-status]');
   notice.hidden=false;
   notice.textContent='SYNTHETIC_CHECK_PROGRESS 1 / 1';
   const retry=document.querySelector('[data-youtube-retry-failed]');
   retry.hidden=false;retry.disabled=false;
   const stop=document.querySelector('[data-youtube-stop]');
   stop.hidden=false;stop.disabled=false;
  });
  await page.waitForFunction(()=>document.querySelector('[data-vf-local-channel-status]')?.textContent?.includes('SYNTHETIC_CHECK_PROGRESS'),null,{timeout:5000});
  expect(await modal.locator('[data-vf-local-channel-status]').isVisible(),'Progress not mirrored in modal');
  expect(await modal.locator('[data-vf-local-channel-retry]').isVisible(),'Retry action not mirrored in modal');
  expect(await modal.locator('[data-vf-local-channel-stop]').isVisible(),'Stop action not mirrored in modal');
  // No real provider request: the source batch action is deliberately not clicked.
  await close();
 });
 for(const [label,route,launcher,taskId,source] of [
  ['topic','topics.php','[data-topic-sync-open]','topic','#vf-topic-sync-dialog'],
  ['course','courses.php','[data-course-govbook-open]','course','#vfCourseGovDialog'],
  ['project','projects.php','[data-project-git-review-open]','project','#vfProjectGitSourceDialog']]){
  await record(label+'/one-dialog-native-sync',async()=>{
   await go(route);
   const visible=page.locator(launcher).filter({visible:true}).first();
   if(await visible.count()!==1){
    if(label==='project'){
     notApplicable.push('project/sync-source-absent-in-clean-install');
     console.log('BROWSER_NA:project/source-sync requires approved Git catalog');
     return;
    }
    throw new Error(label+' launcher unavailable');
   }
   const before=new URL(page.url()).pathname;
   await visible.click();
   await modal.waitFor({state:'visible'});
   expect(new URL(page.url()).pathname===before,'Sync launcher navigated away');
   expect(await modal.locator('[data-vf-local-task="'+taskId+'"]').getAttribute('aria-pressed')==='true','Wrong sync task');
   const native=modal.locator(source);
   expect(await native.count()===1,'Canonical source not embedded in native hub');
   expect(await native.evaluate(el=>el.open&&!el.matches(':modal')),'Canonical source became nested modal');
   expect(await modal.locator('dialog:modal').count()===0,'Nested modal overlay');
   await close();
  });
 }
 const guest=await browser.newContext({viewport:{width:1440,height:900}});
 await guest.route(/https?:\/\/(?!127\.0\.0\.1)/,r=>r.abort());
 const g=await guest.newPage();
 await record('guest/private-owner-action-boundary',async()=>{
  for(const route of ['start.php','channels.php?view=videos','topics.php','courses.php','projects.php']){
   await g.goto(origin+'/'+route,{waitUntil:'domcontentloaded'});
   expect(await g.locator('[data-vf-local-manage-open]').count()===0,'Guest management launcher leaked: '+route);
   expect(await g.locator('dialog[data-vf-local-management]').count()===0,'Guest management form leaked: '+route);
   expect(await g.locator('[data-vf-channel-sync-open]').count()===0,'Guest video sync leaked: '+route);
  }
 });
 await guest.close();await owner.close();
}finally{await browser.close()}
console.log('P01_PR1825_BROWSER_SUMMARY='+JSON.stringify({passed:passed.length,failed:failed.length,failures:failed,notApplicable}));
if(failed.length)process.exit(1);
console.log('P01_PR1825_NATIVE_MODAL_PLAYWRIGHT=PASS');
