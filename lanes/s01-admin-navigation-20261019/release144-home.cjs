const {chromium}=require('playwright'),fs=require('fs');
(async()=>{
 const browser=await chromium.launch(),checks=[],errors=[];let complete=false,saves=0;
 const check=(id,ok,detail)=>{checks.push({id,ok:!!ok,detail});if(!ok)throw Error(id+': '+JSON.stringify(detail));};
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
  page.on('request',r=>{if(r.method()==='POST'&&(r.postData()||'').includes('vf_theme_layout_save'))saves++;});
  const base='http://127.0.0.1:18880/wp-admin/themes.php?page=vf-theme-modules&tab=layout';
  await page.goto('http://127.0.0.1:18880/wp-login.php');
  await page.locator('#user_login').fill('admin');await page.locator('#user_pass').fill('Synthetic-Only-Update-54!');
  await page.locator('input[name=redirect_to]').evaluate((e,u)=>e.value=u,base);await page.locator('#wp-submit').click();await page.waitForURL('**/wp-admin/**');
  for(const width of [1440,1024]){
   await page.setViewportSize({width,height:1000});
   for(const context of ['home','blog_index']){
    const id=context+'-'+width,r=await page.goto(base+'&view=edit&context='+context,{waitUntil:'networkidle'});
    check(id+'-http',r.status()===200,r.status());
    const root=page.locator('[data-vf-layout-page]'),finder=page.locator('[data-vf-page-finder]');
    check(id+'-context',await root.getAttribute('data-vf-layout-context')===context,context);
    await finder.locator('summary').click();
    const opt=await finder.locator('option').evaluateAll(es=>es.find(e=>e.textContent==='模块结构')?.value);
    check(id+'-section-discoverable',opt!==undefined,opt);
    await finder.locator('select').selectOption(opt);await finder.locator('button').click();
    const list=root.locator('[data-vf-layout-list]'),rows=list.locator(':scope>li');
    check(id+'-module-list',await rows.count()>0,await rows.count());
    const header=root.locator('.vf-layout-card--module-list>.vf-layout-card__header');
    check(id+'-duplicate-heading',context==='home'?!await header.isVisible():await header.isVisible(),'Only home hides duplicate card header');
    if(context==='home'){
     check(id+'-single-page-heading',!await root.locator('.vf-layout-current-page__title').isVisible()&&await page.locator('h1').isVisible(),'Page heading remains visible');
     const metrics=await rows.evaluateAll(es=>es.map(e=>{const s=getComputedStyle(e);return {padding:s.paddingTop,height:e.getBoundingClientRect().height};}));
     check(id+'-compact-rows',metrics.every(x=>x.padding==='8px'),metrics);
    }
    for(const action of ['返回页面总览','切换页型','查看前台'])check(id+'-action-'+action,await root.getByRole(action==='切换页型'?'button':'link',{name:action,exact:true}).isVisible(),action);
    check(id+'-no-overflow',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Desktop width');
    await page.screenshot({path:'proof/home-polish-'+id+'.png',fullPage:true});
    const opener=root.locator('[data-vf-layout-module-library-open]');await opener.click();
    const library=root.locator('[data-vf-layout-module-library]');await library.waitFor({state:'visible'});
    check(id+'-library-opens',await library.isVisible(),'Existing module library');
    await page.keyboard.press('Escape');await library.waitFor({state:'hidden'});
    check(id+'-library-closes-focus',await opener.evaluate(e=>document.activeElement===e),'Escape returns to visible opener');
    const candidate=rows.locator('[data-vf-layout-move="down"]:not([disabled])').first();
    if(await candidate.count()){
     const key=await candidate.locator('xpath=ancestor::li').getAttribute('data-module');
     const before=await rows.evaluateAll(es=>es.map(e=>e.dataset.module));await candidate.click();
     const after=await rows.evaluateAll(es=>es.map(e=>e.dataset.module));
     check(id+'-reorder',after.indexOf(key)===before.indexOf(key)+1,{before,after});
     check(id+'-dirty-save-visible',await root.locator('[data-vf-layout-save-dock]').isVisible()&&await root.evaluate(e=>e.classList.contains('is-dirty')),'Candidate stays unsaved');
     await root.locator('.vf-layout-location [data-vf-layout-directory-link]').click();
     const guard=root.locator('[data-vf-layout-navigation-dialog]');await guard.waitFor({state:'visible'});
     await guard.locator('button[data-vf-layout-navigation-cancel]').last().click();
     check(id+'-return-cancel-preserves',await rows.evaluateAll(es=>es.map(e=>e.dataset.module).join(','))===after.join(','),'Candidate order preserved');
    }
    await page.reload({waitUntil:'networkidle'});
   }
  }
  check('no-unexpected-save',saves===0,saves);check('no-browser-errors',errors.length===0,errors);complete=true;
 }finally{
  fs.writeFileSync('proof/home-polish.json',JSON.stringify({status:complete?'PASS':'FAIL',source:process.env.TARGET_SHA,checks,scope:'Home editor plus shared-text blog editor, two desktop widths; browser-only edits; mobile deferred'},null,2));await browser.close();
 }
})().catch(e=>{console.error(e);process.exit(1)});
